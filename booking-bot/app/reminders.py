"""Background task that reminds clients about upcoming visits."""

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from .config import SERVICES_BY_CODE, settings
from .db import Database
from .slots import now

log = logging.getLogger(__name__)


async def reminder_loop(bot: Bot, db: Database, interval_sec: int = 60) -> None:
    while True:
        try:
            current = now()
            for b in await db.due_reminders(current, current + timedelta(hours=settings.reminder_hours)):
                s = SERVICES_BY_CODE[b.service]
                try:
                    await bot.send_message(
                        b.user_id,
                        f"⏰ Reminder: <b>{s.title}</b> today at "
                        f"<b>{b.starts_at.astimezone(settings.tz):%H:%M}</b>.\nSee you at {settings.business_name}!",
                    )
                except TelegramAPIError as e:  # user blocked the bot, etc.
                    log.warning("Reminder for booking %s failed: %s", b.id, e)
                await db.mark_reminded(b.id)
        except Exception:
            log.exception("Reminder loop iteration failed")
        await asyncio.sleep(interval_sec)
