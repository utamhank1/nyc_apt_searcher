from datetime import datetime, timedelta

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings

logger = structlog.get_logger()

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
BUFFER_MINUTES = 20
TOUR_MINUTES = 15
TOTAL_WINDOW = BUFFER_MINUTES + TOUR_MINUTES + BUFFER_MINUTES  # 55 min


def _get_credentials() -> Credentials | None:
    if not settings.google_calendar_refresh_token:
        return None
    if not settings.google_calendar_client_id:
        return None
    return Credentials(
        token=None,
        refresh_token=settings.google_calendar_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_calendar_client_id,
        client_secret=settings.google_calendar_client_secret,
        scopes=SCOPES,
    )


def is_calendar_connected() -> bool:
    return bool(settings.google_calendar_refresh_token and settings.google_calendar_client_id)


async def get_available_times(
    days_ahead: int = 7,
    duration_minutes: int = TOTAL_WINDOW,
    start_hour: int = 9,
    end_hour: int = 19,
) -> list[dict]:
    """Query Google Calendar FreeBusy API and return available time slots."""
    creds = _get_credentials()
    if not creds:
        return []

    try:
        service = build("calendar", "v3", credentials=creds)

        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}],
        }

        result = service.freebusy().query(body=body).execute()
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

                if len(available) >= 6:
                    break
            if len(available) >= 6:
                break

        return available

    except Exception as e:
        logger.error("Calendar query failed", error=str(e))
        return []


def format_availability_for_email(slots: list[dict]) -> str:
    if not slots:
        return ""
    lines = ["I'm available at the following times (including travel time):"]
    for s in slots[:5]:
        lines.append(f"  - {s['date']}, {s['start']} – {s['end']}")
    return "\n".join(lines)
