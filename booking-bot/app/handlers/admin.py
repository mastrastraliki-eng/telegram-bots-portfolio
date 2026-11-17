"""Admin commands: daily schedule overview."""

from datetime import date, datetime, time, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..config import SERVICES_BY_CODE, settings
from ..db import Database

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(settings.admin_ids))


@router.message(Command("admin"))
async def admin_help(message: Message) -> None:
    await message.answer(
        "<b>Admin panel</b>\n\n"
        "/today — today's schedule\n"
        "/tomorrow — tomorrow's schedule\n"
        "/day 2026-12-24 — schedule for a date\n\n"
        "New bookings and cancellations arrive here automatically."
    )


async def _send_day(message: Message, db: Database, day: date) -> None:
    start = datetime.combine(day, time.min, settings.tz)
    items = await db.active_between(start, start + timedelta(days=1))
    if not items:
        await message.answer(f"📭 No bookings on {day:%a %d %b}.")
        return
    lines = [f"📋 <b>{day:%A %d %B}</b> — {len(items)} booking(s)\n"]
    revenue = 0
    for b in items:
        s = SERVICES_BY_CODE[b.service]
        revenue += s.price
        lines.append(f"<b>{b.starts_at.astimezone(settings.tz):%H:%M}</b> {s.title} — {b.client_name}, {b.phone}  #{b.id}")
    lines.append(f"\n💰 Expected revenue: ${revenue}")
    await message.answer("\n".join(lines))


@router.message(Command("today"))
async def today(message: Message, db: Database) -> None:
    await _send_day(message, db, datetime.now(settings.tz).date())


@router.message(Command("tomorrow"))
async def tomorrow(message: Message, db: Database) -> None:
    await _send_day(message, db, datetime.now(settings.tz).date() + timedelta(days=1))


@router.message(Command("day"))
async def any_day(message: Message, command: CommandObject, db: Database) -> None:
    try:
        day = date.fromisoformat((command.args or "").strip())
    except ValueError:
        await message.answer("Usage: /day YYYY-MM-DD")
        return
    await _send_day(message, db, day)
