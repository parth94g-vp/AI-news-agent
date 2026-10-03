from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return (dt.astimezone(timezone.utc) if dt.tzinfo else dt).replace(tzinfo=None)


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def local_today(tz_name: str) -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def format_local(dt: datetime | None, tz_name: str) -> str:
    if dt is None:
        return "Unknown time"
    return ensure_utc(dt).astimezone(ZoneInfo(tz_name)).strftime("%d %b %Y, %H:%M")
