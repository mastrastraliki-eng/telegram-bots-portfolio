"""Settings loaded from environment variables (.env supported)."""

from dataclasses import dataclass, field
import os

from dotenv import load_dotenv

load_dotenv()

# Edit these to match the client's business.
SERVICES = ["Website", "Telegram bot", "Mobile app", "Automation / integrations", "Something else"]
BUDGETS = ["< $500", "$500 – $2,000", "$2,000 – $5,000", "$5,000+", "Not sure yet"]
TIMELINES = ["ASAP", "Within a month", "1–3 months", "Just exploring"]


def _ids(raw: str) -> set[int]:
    return {int(x) for x in raw.replace(" ", "").split(",") if x}


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: os.environ["BOT_TOKEN"])
    admin_ids: set[int] = field(default_factory=lambda: _ids(os.getenv("ADMIN_IDS", "")))
    # Optional: a group chat where every new lead is posted for the sales team
    leads_chat_id: int | None = field(default_factory=lambda: int(v) if (v := os.getenv("LEADS_CHAT_ID")) else None)
    company_name: str = os.getenv("COMPANY_NAME", "Pixel Forge Studio")
    timezone: str = os.getenv("TIMEZONE", "UTC")
    # Google Sheets (optional). Without it, leads are written to a local CSV file.
    google_credentials_file: str | None = os.getenv("GOOGLE_CREDENTIALS_FILE") or None
    spreadsheet_id: str | None = os.getenv("SPREADSHEET_ID") or None
    worksheet_name: str = os.getenv("WORKSHEET_NAME", "Leads")
    csv_path: str = os.getenv("CSV_PATH", "data/leads.csv")


settings = Settings()
