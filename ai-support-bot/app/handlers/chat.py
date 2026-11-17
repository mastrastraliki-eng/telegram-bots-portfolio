"""Customer chat with the AI assistant and hand-off to a human operator."""

import asyncio
import html
import re
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..ai import SupportAI
from ..config import settings
from ..memory import ChatMemory

QUICK_QUESTIONS = [
    "🚚 Shipping & delivery",
    "☕ Which coffee should I choose?",
    "🔁 How do subscriptions work?",
    "↩️ Returns & refunds",
]
USER_TAG = re.compile(r"#id(\d+)")

customers = Router(name="customers")
customers.message.filter(F.chat.type == "private")
operators = Router(name="operators")
operators.message.filter(F.chat.id == settings.support_chat_id)

_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


class QuickCb(CallbackData, prefix="q"):
    idx: int


class HandoffCb(CallbackData, prefix="human"):
    pass


def quick_kb():
    kb = InlineKeyboardBuilder()
    for i, q in enumerate(QUICK_QUESTIONS):
        kb.button(text=q, callback_data=QuickCb(idx=i))
    kb.adjust(1)
    return kb.as_markup()


def handoff_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Talk to a human", callback_data=HandoffCb())
    return kb.as_markup()


@customers.message(CommandStart())
async def start(message: Message, memory: ChatMemory) -> None:
    memory.reset(message.from_user.id)
    await message.answer(
        f"Hi {html.escape(message.from_user.first_name)}! ☕ I'm the {settings.business_name} assistant.\n\n"
        "Ask me anything about our coffee, delivery, subscriptions or returns — I reply instantly, 24/7. "
        "Pick a topic or just type your question:",
        reply_markup=quick_kb(),
    )


@customers.message(Command("reset"))
async def reset(message: Message, memory: ChatMemory) -> None:
    memory.reset(message.from_user.id)
    await message.answer("Conversation cleared. How can I help?")


@customers.callback_query(QuickCb.filter())
async def quick(call: CallbackQuery, callback_data: QuickCb, bot: Bot, ai: SupportAI, memory: ChatMemory) -> None:
    await call.answer()
    question = QUICK_QUESTIONS[callback_data.idx].split(" ", 1)[1]
    await call.message.answer(f"<i>{html.escape(question)}</i>")
    await _answer(bot, call.from_user.id, question, ai, memory)


@customers.message(F.text)
async def question(message: Message, bot: Bot, ai: SupportAI, memory: ChatMemory) -> None:
    await _answer(bot, message.from_user.id, message.text, ai, memory)


async def _answer(bot: Bot, user_id: int, text: str, ai: SupportAI, memory: ChatMemory) -> None:
    lock = _locks[user_id]
    if lock.locked():
        await bot.send_message(user_id, "One moment, still answering your previous message… ⏳")
        return
    async with lock:
        memory.add(user_id, "user", text[:4000])
        await bot.send_chat_action(user_id, ChatAction.TYPING)
        answer = await ai.reply(memory.get(user_id))
        memory.add(user_id, "assistant", answer.text)
        markup = handoff_kb() if answer.handoff else None
        # AI text is sent without parse_mode so stray symbols can never break HTML formatting.
        await bot.send_message(user_id, answer.text, parse_mode=None, reply_markup=markup)


@customers.callback_query(HandoffCb.filter())
async def handoff(call: CallbackQuery, bot: Bot, memory: ChatMemory) -> None:
    user = call.from_user
    await call.message.edit_reply_markup(reply_markup=None)
    if not settings.support_chat_id:
        await call.answer()
        await call.message.answer("Please email hello@brewlab.example — our team replies within one working day.")
        return

    transcript = "\n".join(
        f"{'🧑' if m['role'] == 'user' else '🤖'} {html.escape(m['content'][:300])}" for m in memory.get(user.id)[-6:]
    )
    who = f"{html.escape(user.full_name)}" + (f" (@{user.username})" if user.username else "")
    await bot.send_message(
        settings.support_chat_id,
        f"🙋 <b>{who} asks for a human</b>\n\n{transcript}\n\n"
        f"↩️ <i>Reply to this message to answer the customer.</i> #id{user.id}",
    )
    await call.answer()
    await call.message.answer("I've passed your question to our team 👤 A person will reply right here in this chat.")


@operators.message(F.reply_to_message.from_user.is_bot, F.text)
async def operator_reply(message: Message, bot: Bot, memory: ChatMemory) -> None:
    """An operator replied to a hand-off message in the support chat: relay it to the customer."""
    tag = USER_TAG.search(message.reply_to_message.text or "")
    if not tag:
        return
    user_id = int(tag.group(1))
    await bot.send_message(user_id, f"👤 <b>{html.escape(message.from_user.first_name)} from {settings.business_name}:</b>\n"
                                    f"{html.escape(message.text)}")
    memory.add(user_id, "assistant", f"(Human team member) {message.text}")
    await message.reply("✅ Sent to the customer")
