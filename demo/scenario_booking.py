"""End-to-end scenario for booking-bot. Run: python demo/scenario_booking.py"""

import asyncio
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "booking-bot"))
sys.path.insert(0, str(ROOT / "demo"))
os.environ.update(BOT_TOKEN="42:TEST", ADMIN_IDS="777", TIMEZONE="Europe/London",
                  DB_PATH=os.path.join(tempfile.mkdtemp(), "b.db"))

from aiogram import Dispatcher  # noqa: E402
from aiogram.types import User  # noqa: E402

from app.db import Database  # noqa: E402
from app.handlers import admin, client  # noqa: E402
from app import keyboards as kb  # noqa: E402
from app.slots import free_slots, now  # noqa: E402
from simulator import Emulator  # noqa: E402
from transcript import save  # noqa: E402

ADMIN = User(id=777, is_bot=False, first_name="Mike", username="mike_barber")


async def main() -> None:
    db = Database(os.environ["DB_PATH"])
    await db.connect()
    try:
        dp = Dispatcher(db=db)
        dp.include_routers(admin.router, client.router)
        em = Emulator(dp)

        tomorrow = now().date() + timedelta(days=1)
        await em.send("/start")
        await em.send(kb.BTN_BOOK)
        em.snapshot("choose-service", "Sharp Cuts Barbershop")
        await em.tap("Men's haircut · 60 min · $30")
        await em.tap(tomorrow.strftime("%a %d %b"))
        em.snapshot("choose-time", "Sharp Cuts Barbershop", last=4)
        await em.tap("11:00")
        await em.send("Emma Clark")
        await em.share_contact("+44 7700 900123")
        em.snapshot("review", "Sharp Cuts Barbershop", last=6)
        await em.tap("✅ Confirm")
        assert any("booked!" in b.html for b in em.chat()), em.last_bot_text()
        em.snapshot("booked", "Sharp Cuts Barbershop", last=6)

        # Admin got a notification with a cancel button
        admin_msgs = em.chat(ADMIN.id)
        assert admin_msgs and "New booking #1" in admin_msgs[-1].html

        # 11:00 and the overlapping 10:30 slot are gone; 12:00 is still free
        left = {t.strftime("%H:%M") for t in await free_slots(db, tomorrow, 60)}
        assert "11:00" not in left and "10:30" not in left and "12:00" in left, left

        await em.send(kb.BTN_MY)
        assert "Men's haircut" in em.last_bot_text()

        # Admin schedule
        await em.send("/tomorrow", chat_id=ADMIN.id, user=ADMIN)
        assert "Emma Clark" in em.last_bot_text(ADMIN.id)
        em.snapshot("admin", "Sharp Cuts Barbershop", chat_id=ADMIN.id, subtitle="bot · admin chat")

        # Non-admin cannot use admin commands (falls through, no schedule shown)
        before = len(em.log)
        await em.send("/today")
        assert all("Expected revenue" not in b.html for b in em.log[before:])

        # Reminder query picks the booking up only inside the reminder window
        b = await db.get(1)
        assert await db.due_reminders(b.starts_at - timedelta(hours=1), b.starts_at + timedelta(hours=1))
        assert not await db.due_reminders(b.starts_at - timedelta(hours=5), b.starts_at - timedelta(hours=3))

        save("booking", em)
    finally:
        await db.close()
    print("booking-bot: all checks passed")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), 60))
