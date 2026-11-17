"""Settings loaded from environment variables (.env supported)."""

from dataclasses import dataclass, field
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Service:
    code: str
    title: str
    duration_min: int
    price: int


# Edit this list to match the client's business.
SERVICES: list[Service] = [
    Service("haircut", "Men's haircut", 60, 30),
    Service("beard", "Beard trim", 30, 15),
    Service("combo", "Haircut + beard", 90, 40),
    Service("kids", "Kids haircut", 30, 20),
]

SERVICES_BY_CODE = {s.code: s for s in SERVICES}


def _ids(raw: str) -> set[int]:
    return {int(x) for x in raw.replace(" ", "").split(",") if x}


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: os.environ["BOT_TOKEN"])
    admin_ids: set[int] = field(default_factory=lambda: _ids(os.getenv("ADMIN_IDS", "")))
    tz: ZoneInfo = field(default_factory=lambda: ZoneInfo(os.getenv("TIMEZONE", "Europe/London")))
    db_path: str = os.getenv("DB_PATH", "data/bookings.db")
    business_name: str = os.getenv("BUSINESS_NAME", "Sharp Cuts Barbershop")
    open_hour: int = int(os.getenv("OPEN_HOUR", "10"))
    close_hour: int = int(os.getenv("CLOSE_HOUR", "20"))
    slot_step_min: int = int(os.getenv("SLOT_STEP_MIN", "30"))
    days_ahead: int = int(os.getenv("DAYS_AHEAD", "7"))
    reminder_hours: int = int(os.getenv("REMINDER_HOURS", "2"))


settings = Settings()
