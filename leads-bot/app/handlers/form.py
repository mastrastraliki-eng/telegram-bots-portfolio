"""Lead form: name -> service -> budget -> timeline -> details -> contact -> review -> save."""

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import keyboards as kb
from ..config import BUDGETS, SERVICES, TIMELINES, settings
from ..storage import Lead, LeadStore

router = Router(name="form")

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")
CHOICES = {"service": SERVICES, "budget": BUDGETS, "timeline": TIMELINES}


class Form(StatesGroup):
    name = State()
    service = State()
    budget = State()
    timeline = State()
    details = State()
    contact = State()
    review = State()


# ---------- menu ----------

@router.message(CommandStart())
async def start(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    # Deep links like t.me/your_bot?start=instagram tell you which ad/channel the lead came from.
    await state.update_data(source=command.args or "direct")
    await message.answer(
        f"Hi, {html.escape(message.from_user.first_name)}! 👋\n"
        f"This is <b>{settings.company_name}</b>. Tell us about your project and we'll get back "
        "to you with an estimate within one business day.\n\n"
        "It takes about a minute.",
        reply_markup=kb.main_menu(),
    )


@router.message(F.text == kb.BTN_SERVICES)
async def services(message: Message) -> None:
    await message.answer(
        "<b>What we do</b>\n\n"
        "🌐 Websites and landing pages\n🤖 Telegram bots and mini apps\n📱 Mobile apps\n"
        "⚙️ Automations: CRM, Google Sheets, payments, notifications\n\n"
        "Tap “Leave a request” to get a free estimate."
    )


@router.message(F.text == kb.BTN_CONTACTS)
async def contacts(message: Message) -> None:
    await message.answer("📧 hello@pixelforge.example\n🌐 pixelforge.example\n🕘 Mon–Fri, 9:00–18:00")


# ---------- form ----------

@router.message(F.text == kb.BTN_REQUEST)
async def begin(message: Message, state: FSMContext) -> None:
    source = (await state.get_data()).get("source", "direct")
    await state.set_data({"source": source})
    await state.set_state(Form.name)
    await message.answer("Great! First, what's your name?", reply_markup=ReplyKeyboardRemove())


@router.message(Form.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 60:
        return await message.answer("Please send a name between 2 and 60 characters.")
    await state.update_data(name=name)
    await state.set_state(Form.service)
    await message.answer(f"Nice to meet you, {html.escape(name)}! What do you need?",
                         reply_markup=kb.options("service", SERVICES, 1))


async def _ask_next(call: CallbackQuery, state: FSMContext, field: str) -> None:
    if field == "service":
        await state.set_state(Form.budget)
        await call.message.answer("What's your approximate budget?", reply_markup=kb.options("budget", BUDGETS))
    elif field == "budget":
        await state.set_state(Form.timeline)
        await call.message.answer("When would you like to start?", reply_markup=kb.options("timeline", TIMELINES))
    else:
        await state.set_state(Form.details)
        await call.message.answer(
            "Describe the project in a few sentences: goals, features, links to examples you like.",
            reply_markup=kb.skip(),
        )


@router.callback_query(kb.PickCb.filter())
async def picked(call: CallbackQuery, callback_data: kb.PickCb, state: FSMContext) -> None:
    expected = {Form.service.state: "service", Form.budget.state: "budget", Form.timeline.state: "timeline"}
    if expected.get(await state.get_state()) != callback_data.field:
        return await call.answer("This question is already answered.")
    value = CHOICES[callback_data.field][callback_data.idx]
    await state.update_data(**{callback_data.field: value})
    await call.message.edit_text(f"{call.message.html_text}\n<b>→ {html.escape(value)}</b>")
    await call.answer()
    await _ask_next(call, state, callback_data.field)


async def _ask_contact(message: Message, state: FSMContext) -> None:
    await state.set_state(Form.contact)
    await message.answer("Last step: how can we reach you? Share your phone or type an email.",
                         reply_markup=kb.contact())


@router.message(Form.details, F.text)
async def got_details(message: Message, state: FSMContext) -> None:
    await state.update_data(details=message.text.strip()[:2000])
    await _ask_contact(message, state)


@router.callback_query(Form.details, kb.ActionCb.filter(F.name == "skip"))
async def skip_details(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(details="")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await _ask_contact(call.message, state)


@router.message(Form.contact, F.contact | F.text)
async def got_contact(message: Message, state: FSMContext) -> None:
    value = message.contact.phone_number if message.contact else message.text.strip()
    if not (EMAIL_RE.match(value) or PHONE_RE.match(value)):
        return await message.answer("That doesn't look like a phone or email. Try again, e.g. name@company.com")
    await state.update_data(contact=value)
    await state.set_state(Form.review)
    d = await state.get_data()
    await message.answer("Thanks!", reply_markup=ReplyKeyboardRemove())
    await message.answer("Please check your request:\n\n" + _summary(d), reply_markup=kb.review())


def _summary(d: dict) -> str:
    e = html.escape
    details = e(d.get("details") or "—")
    return (
        f"👤 <b>Name:</b> {e(d['name'])}\n"
        f"📞 <b>Contact:</b> {e(d['contact'])}\n"
        f"💼 <b>Service:</b> {e(d['service'])}\n"
        f"💰 <b>Budget:</b> {e(d['budget'])}\n"
        f"⏱ <b>Timeline:</b> {e(d['timeline'])}\n"
        f"📝 <b>Details:</b> {details}"
    )


@router.callback_query(Form.review, kb.ActionCb.filter(F.name == "restart"))
async def restart(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await begin(call.message, state)


@router.callback_query(Form.review, kb.ActionCb.filter(F.name == "send"))
async def send(call: CallbackQuery, state: FSMContext, store: LeadStore, bot: Bot) -> None:
    d = await state.get_data()
    user = call.from_user
    lead = Lead(
        created_at=datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d %H:%M"),
        name=d["name"], contact=d["contact"], service=d["service"], budget=d["budget"],
        timeline=d["timeline"], details=d.get("details", ""),
        telegram=f"@{user.username}" if user.username else str(user.id),
        source=d.get("source", "direct"),
    )
    number = await store.add(lead)
    await state.clear()

    await call.message.edit_text(f"✅ <b>Request #{number} received!</b>\n\n{_summary(d)}")
    await call.answer("Sent!")
    await call.message.answer(
        "Our manager will contact you within one business day. Meanwhile, feel free to send any files or links here.",
        reply_markup=kb.main_menu(),
    )

    text = f"🔥 <b>New lead #{number}</b> (source: {html.escape(lead.source)})\n\n{_summary(d)}\n\n📊 Saved to {store.name}"
    targets = set(settings.admin_ids) | ({settings.leads_chat_id} if settings.leads_chat_id else set())
    for chat_id in targets:
        await bot.send_message(chat_id, text, reply_markup=kb.open_chat(user.id, user.username))
