from fastapi import APIRouter
from google_auth_oauthlib.flow import Flow

from app.core.config import settings

router = APIRouter(tags=["calendar"])

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


@router.get("/calendar/authorize")
async def authorize():
    if not settings.google_calendar_client_id:
        return {"error": "Google Calendar client ID not configured. Set GOOGLE_CALENDAR_CLIENT_ID in env vars."}

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_calendar_client_id,
                "client_secret": settings.google_calendar_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.google_calendar_redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return {"auth_url": auth_url}


@router.get("/calendar/callback")
async def callback(code: str):
    if not settings.google_calendar_client_id:
        return {"error": "Google Calendar not configured"}

    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_calendar_client_id,
                    "client_secret": settings.google_calendar_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=settings.google_calendar_redirect_uri,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials

        settings.google_calendar_refresh_token = creds.refresh_token or ""
        return {"ok": True, "message": "Google Calendar connected!"}
    except Exception as e:
        return {"error": f"OAuth failed: {str(e)}"}


@router.get("/calendar/status")
async def calendar_status():
    from app.services.calendar_service import is_calendar_connected
    return {"connected": is_calendar_connected()}


@router.delete("/calendar/disconnect")
async def disconnect():
    settings.google_calendar_refresh_token = ""
    return {"ok": True, "message": "Google Calendar disconnected"}
