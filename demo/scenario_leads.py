"""End-to-end scenario for leads-bot (CSV mode). Run: python demo/scenario_leads.py"""

import asyncio
import csv
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "leads-bot"))
sys.path.insert(0, str(ROOT / "demo"))
CSV = os.path.join(tempfile.mkdtemp(), "leads.csv")
os.environ.update(BOT_TOKEN="42:TEST", ADMIN_IDS="777", CSV_PATH=CSV, GOOGLE_CREDENTIALS_FILE="", SPREADSHEET_ID="")

from aiogram import Dispatcher  # noqa: E402
from aiogram.types import User  # noqa: E402

from app import keyboards as kb  # noqa: E402
from app.handlers import form  # noqa: E402
from app.storage import CsvStore, Lead, SheetsStore  # noqa: E402
from simulator import Emulator  # noqa: E402
from transcript import save  # noqa: E402

MANAGER = User(id=777, is_bot=False, first_name="Alex", username="alex_sales")


async def check_sheets_store() -> None:
    """SheetsStore against a fake gspread worksheet: row values go in RAW, lead number comes from the range."""
    class FakeWorksheet:
        rows: list = []

        def append_row(self, values, value_input_option):
            assert value_input_option == "RAW"
            self.rows.append(values)
            return {"updates": {"updatedRange": f"Leads!A{len(self.rows) + 1}:K{len(self.rows) + 1}"}}

    store = object.__new__(SheetsStore)
    store.ws = FakeWorksheet()
    lead = Lead("2026-11-17 10:00", "Ann", "=HYPERLINK(\"x\")", "Website", "$5,000+", "ASAP", "", "@ann", "direct")
    assert await store.add(lead) == 1 and await store.add(lead) == 2
    assert store.ws.rows[0][2] == '=HYPERLINK("x")'


async def main() -> None:
    await check_sheets_store()
    dp = Dispatcher(store=CsvStore(CSV))
    dp.include_router(form.router)
    em = Emulator(dp, User(id=1001, is_bot=False, first_name="Daniel", username="daniel_k"))

    await em.send("/start instagram")
    await em.send(kb.BTN_REQUEST)
    await em.send("Daniel")
    em.snapshot("choose-service", "Pixel Forge Studio")
    await em.tap("Telegram bot")
    await em.tap("$500 – $2,000")
    await em.tap("Within a month")
    em.snapshot("qualify", "Pixel Forge Studio", last=6)
    await em.send("A bot for my yoga studio: class schedule, booking, payments via Stripe "
                  "and reminders. Like @example_bot but simpler.")
    await em.send("not a phone")  # validation
    assert "doesn't look like" in em.last_bot_text()
    await em.send("daniel@yogaflow.example")
    await em.tap("✅ Send request")
    assert any("Request #1 received" in b.html for b in em.chat())
    em.snapshot("sent", "Pixel Forge Studio", last=6)

    lead_note = em.chat(MANAGER.id)[-1].html
    assert "New lead #1" in lead_note and "instagram" in lead_note, lead_note
    em.snapshot("manager", "Pixel Forge Studio", chat_id=MANAGER.id, subtitle="bot · sales team chat")

    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    assert rows[0]["Contact"] == "daniel@yogaflow.example" and rows[0]["Source"] == "instagram", rows

    save("leads", em)

    # Starting a new request
    before = len(em.log)
    await em.send(kb.BTN_REQUEST)
    await em.send("Second Lead")
    await em.tap("Website")
    assert len(em.log) > before

    print("leads-bot: all checks passed")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), 60))
