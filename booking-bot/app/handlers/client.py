"""Client-side flow: pick service -> day -> time -> name -> phone -> confirm."""

import re
from datetime import date, datetime, time

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import keyboards as kb
from ..config import SERVICES_BY_CODE, settings
from ..db import Booking, Database
from ..slots import bookable_days, free_slots, now

router = Router(name="client")

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")


class BookingForm(StatesGroup):
    service = State()
    day = State()
    slot = State()
    name = State()
    phone = State()
    confirm = State()


def describe(b: Booking) -> str:
    s = SERVICES_BY_CODE[b.service]
    local = b.starts_at.astimezone(settings.tz)
    return f"<b>{s.title}</b>\n🗓 {local:%A, %d %B}\n🕒 {local:%H:%M}–{b.ends_at.astimezone(settings.tz):%H:%M}"


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"Hi, {message.from_user.first_name}! 👋\n"
        f"I'm the booking assistant of <b>{settings.business_name}</b>.\n\n"
        "Book a visit in under a minute — no calls, no waiting.",
        reply_markup=kb.main_menu(),
    )


@router.message(F.text == kb.BTN_ABOUT)
async def about(message: Message) -> None:
    await message.answer(
        f"<b>{settings.business_name}</b>\n"
        f"🕙 Open daily {settings.open_hour}:00–{settings.close_hour}:00\n"
        "📍 221B Baker Street, London\n\n"
        "You'll get a reminder before your visit. Need to reschedule? Cancel in “My bookings” and book again."
    )


# ---------- booking flow ----------

@router.message(F.text == kb.BTN_BOOK)
async def choose_service(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BookingForm.service)
    await message.answer("Which service would you like?", reply_markup=kb.services())


@router.callback_query(kb.NavCb.filter(F.to == "services"))
async def back_to_services(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingForm.service)
    await call.message.edit_text("Which service would you like?", reply_markup=kb.services())
    await call.answer()


@router.callback_query(BookingForm.service, kb.ServiceCb.filter())
async def service_chosen(call: CallbackQuery, callback_data: kb.ServiceCb, state: FSMContext) -> None:
    await state.update_data(service=callback_data.code)
    await state.set_state(BookingForm.day)
    s = SERVICES_BY_CODE[callback_data.code]
    await call.message.edit_text(f"<b>{s.title}</b> — pick a day:", reply_markup=kb.days(bookable_days()))
    await call.answer()


@router.callback_query(kb.NavCb.filter(F.to == "days"))
async def back_to_days(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if "service" not in data:
        await call.answer("Session expired, please start again.", show_alert=True)
        return
    await state.set_state(BookingForm.day)
    s = SERVICES_BY_CODE[data["service"]]
    await call.message.edit_text(f"<b>{s.title}</b> — pick a day:", reply_markup=kb.days(bookable_days()))
    await call.answer()


@router.callback_query(BookingForm.day, kb.DayCb.filter())
async def day_chosen(call: CallbackQuery, callback_data: kb.DayCb, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    service = SERVICES_BY_CODE[data["service"]]
    day = date.fromisoformat(callback_data.iso)
    times = await free_slots(db, day, service.duration_min)
    if not times:
        await call.answer("No free time left that day — try another one 🙏", show_alert=True)
        return
    await state.update_data(day=day.isoformat())
    await state.set_state(BookingForm.slot)
    await call.message.edit_text(f"<b>{service.title}</b>, {day:%A %d %B}\nChoose a time:", reply_markup=kb.slots(times))
    await call.answer()


@router.callback_query(BookingForm.slot, kb.SlotCb.filter())
async def slot_chosen(call: CallbackQuery, callback_data: kb.SlotCb, state: FSMContext) -> None:
    await state.update_data(hhmm=callback_data.hhmm)
    await state.set_state(BookingForm.name)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("Great choice! What name should I put the booking under?")
    await call.answer()


@router.message(BookingForm.name, F.text)
async def name_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 60:
        await message.answer("Please send a name between 2 and 60 characters.")
        return
    await state.update_data(name=name)
    await state.set_state(BookingForm.phone)
    await message.answer("And your phone number, so we can reach you if anything changes:", reply_markup=kb.share_phone())


@router.message(BookingForm.phone, F.contact | F.text)
async def phone_entered(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number if message.contact else message.text.strip()
    if not PHONE_RE.match(phone):
        await message.answer("That doesn't look like a phone number. Try again, e.g. +44 7700 900123")
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingForm.confirm)

    data = await state.get_data()
    s = SERVICES_BY_CODE[data["service"]]
    start = _start(data)
    await message.answer("Almost done!", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "Please check your booking:\n\n"
        f"💈 <b>{s.title}</b> · ${s.price}\n"
        f"🗓 {start:%A, %d %B} at {start:%H:%M}\n"
        f"👤 {data['name']}\n📱 {phone}",
        reply_markup=kb.confirm(),
    )


@router.callback_query(BookingForm.confirm, kb.ConfirmCb.filter())
async def confirmed(call: CallbackQuery, callback_data: kb.ConfirmCb, state: FSMContext,
                    db: Database, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    if not callback_data.yes:
        await call.message.edit_text("Booking cancelled.")
        await call.message.answer("No problem! Tap “Book an appointment” whenever you're ready.",
                                  reply_markup=kb.main_menu())
        return await call.answer()

    s = SERVICES_BY_CODE[data["service"]]
    start = _start(data)
    # Re-check: someone may have taken the slot while this user was typing.
    if start not in await free_slots(db, start.date(), s.duration_min):
        await call.message.edit_text("Sorry, that time was just taken 😕")
        await call.message.answer("Please tap “Book an appointment” and pick another time.",
                                  reply_markup=kb.main_menu())
        return await call.answer()

    booking_id = await db.create(user_id=call.from_user.id, client_name=data["name"], phone=data["phone"],
                                 service=s.code, starts_at=start, duration_min=s.duration_min)
    booking = await db.get(booking_id)
    await call.message.edit_text(f"✅ <b>You're booked!</b> #{booking_id}\n\n{describe(booking)}")
    await call.message.answer(
        f"I'll send you a reminder {settings.reminder_hours} hours before your visit. See you soon! 💈",
        reply_markup=kb.main_menu(),
    )
    await call.answer("Booked!")

    user = call.from_user
    username = f" (@{user.username})" if user.username else ""
    for admin_id in settings.admin_ids:
        await bot.send_message(
            admin_id,
            f"🆕 <b>New booking #{booking_id}</b>\n\n{describe(booking)}\n"
            f"👤 {data['name']}{username}\n📱 {data['phone']}",
            reply_markup=kb.cancel_booking(booking_id, "Cancel & notify client"),
        )


def _start(data: dict) -> datetime:
    hh, mm = int(data["hhmm"][:2]), int(data["hhmm"][2:])
    return datetime.combine(date.fromisoformat(data["day"]), time(hh, mm), settings.tz)


# ---------- my bookings ----------

@router.message(F.text == kb.BTN_MY)
async def my_bookings(message: Message, db: Database) -> None:
    items = await db.upcoming_for_user(message.from_user.id, now())
    if not items:
        await message.answer("You have no upcoming bookings. Tap “Book an appointment” to make one.")
        return
    for b in items:
        await message.answer(f"#{b.id}\n{describe(b)}", reply_markup=kb.cancel_booking(b.id))


@router.callback_query(kb.CancelCb.filter())
async def cancel(call: CallbackQuery, callback_data: kb.CancelCb, db: Database, bot: Bot) -> None:
    b = await db.get(callback_data.booking_id)
    is_admin = call.from_user.id in settings.admin_ids
    if not b or (b.user_id != call.from_user.id and not is_admin):
        return await call.answer("Booking not found.", show_alert=True)
    if b.status == "cancelled":
        return await call.answer("Already cancelled.")

    await db.cancel(b.id)
    await call.message.edit_text(f"❌ Cancelled #{b.id}\n{describe(b)}")
    await call.answer("Cancelled")

    if b.user_id == call.from_user.id:  # client cancelled -> tell the business
        for admin_id in settings.admin_ids:
            await bot.send_message(admin_id, f"↩️ Client cancelled booking #{b.id}\n{describe(b)}\n👤 {b.client_name}")
    else:  # business cancelled -> tell the client
        await bot.send_message(
            b.user_id,
            f"😔 Unfortunately we had to cancel your booking #{b.id}:\n{describe(b)}\n\nPlease pick another time.",
            reply_markup=kb.main_menu(),
        )
