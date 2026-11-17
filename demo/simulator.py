"""Offline Telegram emulator for end-to-end tests and portfolio screenshots.

Runs a real aiogram Dispatcher against a fake Bot API session: every outgoing call
(sendMessage, editMessageText, ...) is recorded instead of hitting Telegram, and
incoming updates (text, button taps, shared contacts) are fed straight to the bot.
"""

from __future__ import annotations

import html
import itertools
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import Default, DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import (
    EditMessageReplyMarkup, EditMessageText, GetMe, SendMessage, TelegramMethod,
)
from aiogram.types import (
    CallbackQuery, Chat, Contact, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, Update, User,
)

BOT_USER = User(id=42, is_bot=True, first_name="Demo Bot", username="demo_bot")


@dataclass
class Bubble:
    side: str  # "bot" | "user"
    html: str
    chat_id: int
    message_id: int = 0
    inline: list[list[str]] = field(default_factory=list)
    reply_kb: list[list[str]] = field(default_factory=list)


def _text_to_html(text: str, parse_mode: Any) -> str:
    if parse_mode is None or (isinstance(parse_mode, str) and parse_mode.lower() != "html"):
        return html.escape(text)
    return text  # Default(...) or "HTML": already HTML


class FakeSession(BaseSession):
    def __init__(self, emulator: "Emulator"):
        super().__init__()
        self.em = emulator

    async def close(self) -> None:  # pragma: no cover
        pass

    async def stream_content(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None):
        return self.em.handle(method)


class Emulator:
    def __init__(self, dp: Dispatcher, user: User | None = None):
        self.dp = dp
        self.user = user or User(id=1001, is_bot=False, first_name="Emma", last_name="Clark", username="emma_c")
        self.bot = Bot("42:TEST", session=FakeSession(self),
                       default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.ids = itertools.count(1)
        self.update_ids = itertools.count(1)
        self.log: list[Bubble] = []          # everything, all chats
        self.messages: dict[int, Message] = {}
        self.reply_kb: dict[int, list[list[str]]] = {}
        self.frames: list[dict] = []  # chat snapshots for screenshots

    # ---------- outgoing (bot -> Telegram) ----------

    def handle(self, method: TelegramMethod):
        if isinstance(method, GetMe):
            return BOT_USER
        if isinstance(method, SendMessage):
            mid = next(self.ids)
            inline, rkb = self._markup(method.chat_id, method.reply_markup)
            self.log.append(Bubble("bot", _text_to_html(method.text, method.parse_mode), int(method.chat_id),
                                   mid, inline, rkb))
            msg = Message(message_id=mid, date=datetime.now(timezone.utc), from_user=BOT_USER,
                          chat=Chat(id=int(method.chat_id), type="private"), text=method.text,
                          reply_markup=method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None)
            self.messages[mid] = msg
            return msg.as_(self.bot)
        if isinstance(method, (EditMessageText, EditMessageReplyMarkup)):
            b = self._bubble(method.message_id)
            if isinstance(method, EditMessageText):
                b.html = _text_to_html(method.text, method.parse_mode)
            b.inline = self._markup(b.chat_id, method.reply_markup)[0]
            old = self.messages[method.message_id]
            new_markup = method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None
            self.messages[method.message_id] = old.model_copy(
                update={"reply_markup": new_markup, "text": getattr(method, "text", old.text)})
            return True
        return True  # answerCallbackQuery, sendChatAction, setMyCommands, ...

    def _markup(self, chat_id, markup) -> tuple[list[list[str]], list[list[str]]]:
        if isinstance(markup, InlineKeyboardMarkup):
            return [[b.text for b in row] for row in markup.inline_keyboard], []
        if isinstance(markup, ReplyKeyboardMarkup):
            rows = [[b.text for b in row] for row in markup.keyboard]
            self.reply_kb[int(chat_id)] = rows
            return [], rows
        if isinstance(markup, ReplyKeyboardRemove):
            self.reply_kb.pop(int(chat_id), None)
        return [], []

    def _bubble(self, mid: int) -> Bubble:
        return next(b for b in self.log if b.side == "bot" and b.message_id == mid)

    # ---------- incoming (user -> bot) ----------

    async def _feed(self, **kw) -> None:
        await self.dp.feed_update(self.bot, Update(update_id=next(self.update_ids), **kw))

    def _msg(self, chat_id: int | None = None, user: User | None = None, **kw) -> Message:
        user = user or self.user
        chat_id = chat_id or user.id
        chat = Chat(id=chat_id, type="private" if chat_id > 0 else "group")
        return Message(message_id=next(self.ids), date=datetime.now(timezone.utc), chat=chat, from_user=user, **kw)

    async def send(self, text: str, *, chat_id: int | None = None, user: User | None = None,
                   reply_to: int | None = None) -> None:
        reply = self.messages[reply_to] if reply_to else None
        m = self._msg(chat_id, user, text=text, reply_to_message=reply)
        self.log.append(Bubble("user", html.escape(text), m.chat.id, m.message_id))
        await self._feed(message=m)

    async def share_contact(self, phone: str) -> None:
        contact = Contact(phone_number=phone, first_name=self.user.first_name, user_id=self.user.id)
        m = self._msg(contact=contact)
        self.log.append(Bubble("user", f"📱 {html.escape(phone)}", m.chat.id, m.message_id))
        await self._feed(message=m)

    async def tap(self, button_text: str) -> None:
        """Tap an inline button (searching the newest bot messages first) in the user's chat."""
        for mid in sorted(self.messages, reverse=True):
            msg = self.messages[mid]
            if msg.chat.id != self.user.id or not msg.reply_markup:
                continue
            if not self._bubble(mid).inline:  # keyboard was removed by an edit
                continue
            for row in msg.reply_markup.inline_keyboard:
                for b in row:
                    if b.text == button_text and b.callback_data:
                        cq = CallbackQuery(id=str(next(self.ids)), from_user=self.user, chat_instance="1",
                                           message=msg, data=b.callback_data)
                        await self._feed(callback_query=cq)
                        return
        raise LookupError(f"No inline button {button_text!r}")

    # ---------- inspection ----------

    def chat(self, chat_id: int | None = None) -> list[Bubble]:
        cid = chat_id or self.user.id
        return [b for b in self.log if b.chat_id == cid]

    def snapshot(self, name: str, title: str, *, chat_id: int | None = None, subtitle: str = "bot",
                 last: int | None = None) -> None:
        """Freeze the chat as it looks right now (optionally only the last N bubbles)."""
        cid = chat_id or self.user.id
        bubbles = [asdict(b) for b in self.chat(cid)]
        self.frames.append({"name": name, "title": title, "subtitle": subtitle,
                            "bubbles": bubbles[-last:] if last else bubbles,
                            "reply_kb": self.reply_kb.get(cid, []) if cid == self.user.id else []})

    def last_bot_text(self, chat_id: int | None = None) -> str:
        return next(b.html for b in reversed(self.chat(chat_id)) if b.side == "bot")
