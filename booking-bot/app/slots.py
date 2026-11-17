"""Working-hours and free-slot calculation."""

from datetime import date, datetime, time, timedelta

from .config import settings
from .db import Database


def now() -> datetime:
    return datetime.now(settings.tz)


def bookable_days() -> list[date]:
    today = now().date()
    return [today + timedelta(days=i) for i in range(settings.days_ahead)]


async def free_slots(db: Database, day: date, duration_min: int) -> list[datetime]:
    """Start times on `day` where a service of `duration_min` fits without overlaps."""
    tz = settings.tz
    opens = datetime.combine(day, time(settings.open_hour), tz)
    closes = datetime.combine(day, time(settings.close_hour), tz)
    busy = await db.active_between(opens - timedelta(hours=4), closes)
    earliest = now() + timedelta(minutes=30)  # no last-minute bookings

    slots: list[datetime] = []
    step = timedelta(minutes=settings.slot_step_min)
    length = timedelta(minutes=duration_min)
    start = opens
    while start + length <= closes:
        end = start + length
        overlaps = any(start < b.ends_at and b.starts_at < end for b in busy)
        if start >= earliest and not overlaps:
            slots.append(start)
        start += step
    return slots
