"""Reply and inline keyboards."""

from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import SERVICES, settings

BTN_BOOK = "📅 Book an appointment"
BTN_MY = "🗂 My bookings"
BTN_ABOUT = "ℹ️ About us"


class ServiceCb(CallbackData, prefix="svc"):
    code: str


class DayCb(CallbackData, prefix="day"):
    iso: str


class SlotCb(CallbackData, prefix="slot"):
    hhmm: str


class ConfirmCb(CallbackData, prefix="ok"):
    yes: bool


class CancelCb(CallbackData, prefix="cancel"):
    booking_id: int


class NavCb(CallbackData, prefix="nav"):
    to: str  # services | days


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_BOOK)], [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_ABOUT)]],
        resize_keyboard=True,
    )


def share_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share my phone number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Or type it, e.g. +44 7700 900123",
    )


def services():
    kb = InlineKeyboardBuilder()
    for s in SERVICES:
        kb.button(text=f"{s.title} · {s.duration_min} min · ${s.price}", callback_data=ServiceCb(code=s.code))
    kb.adjust(1)
    return kb.as_markup()


def days(options: list[date]):
    kb = InlineKeyboardBuilder()
    today = datetime.now(settings.tz).date()
    for d in options:
        label = "Today" if d == today else d.strftime("%a %d %b")
        kb.button(text=label, callback_data=DayCb(iso=d.isoformat()))
    kb.button(text="← Back", callback_data=NavCb(to="services"))
    kb.adjust(3)
    return kb.as_markup()


def slots(times: list[datetime]):
    kb = InlineKeyboardBuilder()
    for t in times:
        kb.button(text=t.strftime("%H:%M"), callback_data=SlotCb(hhmm=t.strftime("%H%M")))
    kb.adjust(4)
    kb.row()
    back = InlineKeyboardBuilder()
    back.button(text="← Other day", callback_data=NavCb(to="days"))
    kb.attach(back)
    return kb.as_markup()


def confirm():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Confirm", callback_data=ConfirmCb(yes=True))
    kb.button(text="✖️ Cancel", callback_data=ConfirmCb(yes=False))
    return kb.as_markup()


def cancel_booking(booking_id: int, text: str = "Cancel this booking"):
    kb = InlineKeyboardBuilder()
    kb.button(text=text, callback_data=CancelCb(booking_id=booking_id))
    return kb.as_markup()
