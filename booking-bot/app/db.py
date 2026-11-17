"""SQLite storage for bookings."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    client_name  TEXT    NOT NULL,
    phone        TEXT    NOT NULL,
    service      TEXT    NOT NULL,
    starts_at    TEXT    NOT NULL,  -- ISO 8601, UTC
    duration_min INTEGER NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'active',  -- active | cancelled
    reminded     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(starts_at);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
"""


@dataclass
class Booking:
    id: int
    user_id: int
    client_name: str
    phone: str
    service: str
    starts_at: datetime
    duration_min: int
    status: str

    @property
    def ends_at(self) -> datetime:
        return self.starts_at + timedelta(minutes=self.duration_min)


def _utc(dt: datetime) -> str:
    """Store everything in UTC so string comparison in SQL stays correct across DST."""
    return dt.astimezone(timezone.utc).isoformat()


def _row(r: aiosqlite.Row) -> Booking:
    return Booking(
        id=r["id"],
        user_id=r["user_id"],
        client_name=r["client_name"],
        phone=r["phone"],
        service=r["service"],
        starts_at=datetime.fromisoformat(r["starts_at"]),
        duration_min=r["duration_min"],
        status=r["status"],
    )


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database.connect() was not called"
        return self._conn

    async def create(self, *, user_id: int, client_name: str, phone: str, service: str,
                     starts_at: datetime, duration_min: int) -> int:
        cur = await self.conn.execute(
            "INSERT INTO bookings (user_id, client_name, phone, service, starts_at, duration_min, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, client_name, phone, service, _utc(starts_at), duration_min,
             _utc(datetime.now(timezone.utc))),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get(self, booking_id: int) -> Booking | None:
        async with self.conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)) as cur:
            r = await cur.fetchone()
        return _row(r) if r else None

    async def cancel(self, booking_id: int) -> None:
        await self.conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        await self.conn.commit()

    async def active_between(self, start: datetime, end: datetime) -> list[Booking]:
        async with self.conn.execute(
            "SELECT * FROM bookings WHERE status = 'active' AND starts_at >= ? AND starts_at < ?"
            " ORDER BY starts_at",
            (_utc(start), _utc(end)),
        ) as cur:
            return [_row(r) for r in await cur.fetchall()]

    async def upcoming_for_user(self, user_id: int, now: datetime) -> list[Booking]:
        async with self.conn.execute(
            "SELECT * FROM bookings WHERE user_id = ? AND status = 'active' AND starts_at >= ?"
            " ORDER BY starts_at",
            (user_id, _utc(now)),
        ) as cur:
            return [_row(r) for r in await cur.fetchall()]

    async def due_reminders(self, now: datetime, horizon: datetime) -> list[Booking]:
        async with self.conn.execute(
            "SELECT * FROM bookings WHERE status = 'active' AND reminded = 0"
            " AND starts_at > ? AND starts_at <= ?",
            (_utc(now), _utc(horizon)),
        ) as cur:
            return [_row(r) for r in await cur.fetchall()]

    async def mark_reminded(self, booking_id: int) -> None:
        await self.conn.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
        await self.conn.commit()
