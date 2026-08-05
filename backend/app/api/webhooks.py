import base64
import hashlib
import hmac
import json
import re
import time

import structlog
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.listing import Listing

logger = structlog.get_logger()

router = APIRouter(tags=["webhooks"])

SIGNATURE_TOLERANCE_SECONDS = 5 * 60


def _signing_key(secret: str) -> bytes:
    """Resend/Svix secrets are formatted as whsec_<base64 key>."""
    _, _, encoded = secret.partition("_")
    return base64.b64decode(encoded or secret)


def _verify_signature(body: bytes, msg_id: str, timestamp: str, signature_header: str) -> None:
    """Verify a Svix-style webhook signature, raising HTTPException on failure."""
    if not settings.resend_webhook_secret:
        logger.error("Inbound webhook rejected: RESEND_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    if not (msg_id and timestamp and signature_header):
        raise HTTPException(status_code=401, detail="Missing webhook signature headers")

    try:
        sent_at = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid webhook timestamp")

    if abs(time.time() - sent_at) > SIGNATURE_TOLERANCE_SECONDS:
        raise HTTPException(status_code=401, detail="Webhook timestamp outside tolerance")

    signed_content = b".".join([msg_id.encode(), timestamp.encode(), body])
    expected = base64.b64encode(
        hmac.new(_signing_key(settings.resend_webhook_secret), signed_content, hashlib.sha256).digest()
    ).decode()

    for part in signature_header.split():
        version, _, candidate = part.partition(",")
        if version == "v1" and hmac.compare_digest(candidate, expected):
            return

    raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post("/webhooks/email-reply")
async def handle_email_reply(request: Request):
    """Handle inbound email replies from Resend webhook.
    Parses Y/N from the reply body and triggers the lead flow."""
    body = await request.body()
    _verify_signature(
        body,
        request.headers.get("svix-id", ""),
        request.headers.get("svix-timestamp", ""),
        request.headers.get("svix-signature", ""),
    )

    try:
        payload = json.loads(body)
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
