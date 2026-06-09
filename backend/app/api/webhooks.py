import re

import structlog
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.listing import Listing

logger = structlog.get_logger()

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/email-reply")
async def handle_email_reply(request: Request):
    """Handle inbound email replies from Resend webhook.
    Parses Y/N from the reply body and triggers the lead flow."""
    try:
        payload = await request.json()
        body_text = payload.get("text", "") or payload.get("html", "")
        from_email = payload.get("from", "")
        subject = payload.get("subject", "")

        listing_id = _extract_listing_id_from_subject(subject)
        if not listing_id:
            logger.warning("Could not extract listing ID from email reply", subject=subject)
            return {"ok": False, "reason": "no listing ID in subject"}

        response = _parse_yn_response(body_text)
        if not response:
            logger.info("Could not parse Y/N from reply", body=body_text[:200])
            return {"ok": False, "reason": "could not parse Y/N"}

        async with async_session_factory() as db:
            result = await db.execute(select(Listing).where(Listing.id == listing_id))
            listing = result.scalar_one_or_none()
            if not listing:
                return {"ok": False, "reason": "listing not found"}

            from app.services.lead_flow_service import process_yes_response, process_no_response
            if response == "yes":
                await process_yes_response(listing, db)
            else:
                await process_no_response(listing, db)

        return {"ok": True, "listing_id": listing_id, "response": response}
    except Exception as e:
        logger.error("Webhook error", error=str(e))
        return {"ok": False, "error": str(e)}


def _extract_listing_id_from_subject(subject: str) -> int | None:
    match = re.search(r"#(\d+)", subject)
    return int(match.group(1)) if match else None


def _parse_yn_response(text: str) -> str | None:
    cleaned = text.strip().lower()
    first_word = cleaned.split()[0] if cleaned.split() else ""
    if first_word in ("y", "yes", "yeah", "yep", "sure", "ok"):
        return "yes"
    if first_word in ("n", "no", "nah", "nope", "pass"):
        return "no"
    return None
