import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.calendar_connection import CalendarConnection

router = APIRouter(tags=["calendar"])

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


@router.get("/calendar/authorize")
async def authorize(role: str = "main", email: str = ""):
    if not settings.google_calendar_client_id:
        return {"error": "Google Calendar client ID not configured. Set GOOGLE_CALENDAR_CLIENT_ID in env vars."}

    user_email = email or (settings.user_email if role == "main" else "")
    state = json.dumps({"role": role, "email": user_email})

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
        state=state,
    )
    return {"auth_url": auth_url}


@router.get("/calendar/callback")
async def callback(code: str, state: str = "{}", db: AsyncSession = Depends(get_db)):
    if not settings.google_calendar_client_id:
        return {"error": "Google Calendar not configured"}

    try:
        state_data = json.loads(state)
    except json.JSONDecodeError:
        state_data = {}

    role = state_data.get("role", "main")
    user_email = state_data.get("email", settings.user_email)

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

        if not creds.refresh_token:
            return {"error": "No refresh token received. Try disconnecting and reconnecting."}

        existing = await db.execute(
            select(CalendarConnection).where(CalendarConnection.user_email == user_email)
        )
        conn = existing.scalar_one_or_none()

        if conn:
            conn.refresh_token = creds.refresh_token
            conn.connected_at = datetime.utcnow()
        else:
            conn = CalendarConnection(
                user_email=user_email,
                refresh_token=creds.refresh_token,
                is_main_user=(role == "main"),
            )
            db.add(conn)

        await db.commit()

        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
            "<h2>Google Calendar Connected!</h2>"
            f"<p>Connected for: {user_email}</p>"
            "<p>You can close this tab and return to the app.</p>"
            "</body></html>"
        )
    except Exception as e:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
            f"<h2>Connection Failed</h2><p>{str(e)}</p>"
            f"</body></html>",
            status_code=400,
        )


@router.get("/calendar/connections")
async def list_connections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CalendarConnection))
    connections = result.scalars().all()
    return {
        "connections": [
            {
                "user_email": c.user_email,
                "is_main_user": c.is_main_user,
                "connected_at": c.connected_at.isoformat() if c.connected_at else None,
            }
            for c in connections
        ]
    }


@router.get("/calendar/status")
async def calendar_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CalendarConnection))
    connections = result.scalars().all()
    return {
        "connected": len(connections) > 0,
        "connections": [
            {"email": c.user_email, "is_main": c.is_main_user}
            for c in connections
        ],
    }


@router.delete("/calendar/disconnect")
async def disconnect(email: str = "", db: AsyncSession = Depends(get_db)):
    if email:
        result = await db.execute(
            select(CalendarConnection).where(CalendarConnection.user_email == email)
        )
    else:
        result = await db.execute(
            select(CalendarConnection).where(CalendarConnection.is_main_user == True)
        )

    conn = result.scalar_one_or_none()
    if conn:
        await db.delete(conn)
        await db.commit()
        return {"ok": True, "message": f"Disconnected {conn.user_email}"}
    return {"ok": True, "message": "No connection found"}
