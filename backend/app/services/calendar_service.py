from datetime import datetime, timedelta

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.calendar_connection import CalendarConnection

logger = structlog.get_logger()

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
BUFFER_MINUTES = 20
TOUR_MINUTES = 15
TOTAL_WINDOW = BUFFER_MINUTES + TOUR_MINUTES + BUFFER_MINUTES


def _build_credentials(refresh_token: str) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_calendar_client_id,
        client_secret=settings.google_calendar_client_secret,
        scopes=SCOPES,
    )


async def get_all_connections() -> list[CalendarConnection]:
    async with async_session_factory() as db:
        result = await db.execute(select(CalendarConnection))
        return result.scalars().all()


async def is_any_calendar_connected() -> bool:
    connections = await get_all_connections()
    return len(connections) > 0


async def get_combined_available_times(
    days_ahead: int = 7,
    duration_minutes: int = TOTAL_WINDOW,
    start_hour: int = 9,
    end_hour: int = 19,
) -> list[dict]:
    """Query all connected calendars and return free slots from EITHER user, labeled by name."""
    if not settings.google_calendar_client_id:
        return []

    connections = await get_all_connections()
    if not connections:
        return []

    all_slots = []
    for conn in connections:
        try:
            slots = _query_freebusy_for_user(
                conn.user_email,
                conn.refresh_token,
                days_ahead,
                duration_minutes,
                start_hour,
                end_hour,
            )
            for slot in slots:
                slot["user"] = conn.user_email.split("@")[0].title()
            all_slots.extend(slots)
        except Exception as e:
            logger.warning("Calendar query failed for user", email=conn.user_email, error=str(e))

    all_slots.sort(key=lambda s: (s["date"], s["start"]))
    return all_slots[:10]


def _query_freebusy_for_user(
    email: str,
    refresh_token: str,
    days_ahead: int,
    duration_minutes: int,
    start_hour: int,
    end_hour: int,
) -> list[dict]:
    creds = _build_credentials(refresh_token)
    service = build("calendar", "v3", credentials=creds)

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

    result = service.freebusy().query(body={
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": "primary"}],
    }).execute()

    busy_periods = result.get("calendars", {}).get("primary", {}).get("busy", [])
    busy_ranges = []
    for b in busy_periods:
        start = datetime.fromisoformat(b["start"].replace("Z", "+00:00")).replace(tzinfo=None)
        end = datetime.fromisoformat(b["end"].replace("Z", "+00:00")).replace(tzinfo=None)
        busy_ranges.append((start, end))

    available = []
    for day_offset in range(days_ahead):
        day = now.date() + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue

        day_start = datetime.combine(day, datetime.min.time().replace(hour=start_hour))
        day_end = datetime.combine(day, datetime.min.time().replace(hour=end_hour))
        if day_start < now:
            day_start = now + timedelta(minutes=30)

        slot_start = day_start
        while slot_start + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            conflict = False
            for busy_start, busy_end in busy_ranges:
                if slot_start < busy_end and slot_end > busy_start:
                    conflict = True
                    slot_start = busy_end + timedelta(minutes=5)
                    break
            if not conflict:
                available.append({
                    "date": day.strftime("%A, %B %d"),
                    "start": slot_start.strftime("%-I:%M %p"),
                    "end": slot_end.strftime("%-I:%M %p"),
                })
                slot_start = slot_end + timedelta(minutes=15)
            if len(available) >= 5:
                break
        if len(available) >= 5:
            break

    return available


def format_availability_for_email(slots: list[dict]) -> str:
    if not slots:
        return ""
    lines = ["Available times (including travel buffer):"]
    for s in slots[:8]:
        user = s.get("user", "")
        prefix = f"  {user}: " if user else "  - "
        lines.append(f"{prefix}{s['date']}, {s['start']} – {s['end']}")
    return "\n".join(lines)
