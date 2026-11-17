"""Keyboards for the lead form."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

BTN_REQUEST = "📝 Leave a request"
BTN_SERVICES = "💼 What we do"
BTN_CONTACTS = "📞 Contacts"


class PickCb(CallbackData, prefix="pick"):
    field: str  # service | budget | timeline
    idx: int


class ActionCb(CallbackData, prefix="act"):
    name: str  # skip | send | restart


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_REQUEST)], [KeyboardButton(text=BTN_SERVICES), KeyboardButton(text=BTN_CONTACTS)]],
        resize_keyboard=True,
    )


def options(field: str, items: list[str], columns: int = 2):
    kb = InlineKeyboardBuilder()
    for i, text in enumerate(items):
        kb.button(text=text, callback_data=PickCb(field=field, idx=i))
    kb.adjust(columns)
    return kb.as_markup()


def skip():
    kb = InlineKeyboardBuilder()
    kb.button(text="Skip →", callback_data=ActionCb(name="skip"))
    return kb.as_markup()


def contact() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share my phone number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="…or type an email / phone",
    )


def review():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Send request", callback_data=ActionCb(name="send"))
    kb.button(text="✏️ Start over", callback_data=ActionCb(name="restart"))
    return kb.as_markup()


def open_chat(user_id: int, username: str | None):
    kb = InlineKeyboardBuilder()
    url = f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
    kb.button(text="💬 Message the client", url=url)
    return kb.as_markup()
