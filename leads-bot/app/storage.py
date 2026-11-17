"""Where leads go: Google Sheets in production, a CSV file as a zero-setup fallback."""

import asyncio
import csv
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Protocol

from .config import settings

log = logging.getLogger(__name__)


@dataclass
class Lead:
    created_at: str
    name: str
    contact: str
    service: str
    budget: str
    timeline: str
    details: str
    telegram: str
    source: str
    status: str = "New"


HEADER = [f.name.replace("_", " ").title() for f in fields(Lead)]


class LeadStore(Protocol):
    name: str

    async def add(self, lead: Lead) -> int: ...  # returns lead number


class CsvStore:
    name = "CSV file"

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def add(self, lead: Lead) -> int:
        async with self._lock:
            new_file = not self.path.exists()
            with self.path.open("a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new_file:
                    w.writerow(HEADER)
                w.writerow(asdict(lead).values())
            with self.path.open(encoding="utf-8") as f:
                return sum(1 for _ in f) - 1


class SheetsStore:
    name = "Google Sheets"

    def __init__(self, credentials_file: str, spreadsheet_id: str, worksheet: str):
        import gspread  # imported lazily so the CSV mode works without Google libs configured

        gc = gspread.service_account(filename=credentials_file)
        sh = gc.open_by_key(spreadsheet_id)
        try:
            self.ws = sh.worksheet(worksheet)
        except gspread.WorksheetNotFound:
            self.ws = sh.add_worksheet(title=worksheet, rows=1000, cols=len(HEADER))
        if not self.ws.row_values(1):
            self.ws.append_row(HEADER)
            self.ws.format("A1:Z1", {"textFormat": {"bold": True}})
            self.ws.freeze(rows=1)

    def _append(self, lead: Lead) -> int:
        resp = self.ws.append_row(list(asdict(lead).values()), value_input_option="RAW")  # RAW: user text is never parsed as a formula
        # "Leads!A12:J12" -> row 12 -> lead #11 (row 1 is the header)
        updated = resp.get("updates", {}).get("updatedRange", "")
        try:
            return int("".join(ch for ch in updated.split(":")[-1] if ch.isdigit())) - 1
        except ValueError:
            return len(self.ws.col_values(1)) - 1

    async def add(self, lead: Lead) -> int:
        return await asyncio.to_thread(self._append, lead)  # gspread is blocking


def build_store() -> LeadStore:
    if settings.google_credentials_file and settings.spreadsheet_id:
        log.info("Saving leads to Google Sheets %s", settings.spreadsheet_id)
        return SheetsStore(settings.google_credentials_file, settings.spreadsheet_id, settings.worksheet_name)
    log.info("Google Sheets not configured, saving leads to %s", settings.csv_path)
    return CsvStore(settings.csv_path)
