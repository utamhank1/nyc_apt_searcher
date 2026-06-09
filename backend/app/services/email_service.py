import resend
import structlog

from app.core.config import settings

logger = structlog.get_logger()


def _init_resend():
    if settings.resend_api_key:
        resend.api_key = settings.resend_api_key


async def send_alert_email(listing: dict) -> bool:
    """Send a hot lead alert email with Y/N prompt."""
    _init_resend()
    if not settings.resend_api_key or not settings.alert_to_email:
        logger.warning("Email not configured, skipping alert")
        return False

    subject = f"🔥 Hot Apartment Lead! #{listing['id']} - {listing.get('neighborhood', 'NYC')}"
    body = _build_alert_body(listing)

    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": settings.alert_to_email,
            "subject": subject,
            "html": body,
        })
        logger.info("Alert email sent", listing_id=listing["id"])
        return True
    except Exception as e:
        logger.error("Failed to send alert email", error=str(e))
        return False


async def send_broker_email(listing: dict) -> bool:
    """Send an intro email to the broker, CC'ing user and search partners."""
    _init_resend()
    if not settings.resend_api_key:
        logger.warning("Email not configured, skipping broker email")
        return False

    broker_email = listing.get("broker_email")
    if not broker_email:
        logger.warning("No broker email for listing", listing_id=listing.get("id"))
        return False

    subject, body = _build_broker_email(listing)

    cc_list = []
    if settings.user_email:
        cc_list.append(settings.user_email)
    cc_list.extend(settings.search_partner_emails_list)
    cc_list = [e for e in cc_list if e][:4]

    try:
        params = {
            "from": settings.resend_from_email,
            "to": broker_email,
            "subject": subject,
            "text": body,
        }
        if cc_list:
            params["cc"] = cc_list

        resend.Emails.send(params)
        logger.info("Broker email sent", listing_id=listing.get("id"), broker=broker_email)
        return True
    except Exception as e:
        logger.error("Failed to send broker email", error=str(e))
        return False


def _build_alert_body(listing: dict) -> str:
    commute = f"🚇 {listing['commute_minutes']} min commute" if listing.get("commute_minutes") else ""
    amenities = ", ".join(listing.get("amenities", [])[:5])
    amenities_line = f"✅ Has: {amenities}" if amenities else ""
    score = listing.get("match_score", 0)

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>🔥 Hot apartment lead detected!</h2>
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 16px 0;">
            <p style="font-size: 16px; margin: 4px 0;">📍 {listing.get('address', 'Address unavailable')}, {listing.get('neighborhood', '')}, {listing.get('borough', '')}</p>
            <p style="font-size: 20px; font-weight: bold; margin: 4px 0;">💰 ${listing.get('price', '?'):,}/mo · {listing.get('beds', '?')}BR/{listing.get('baths', '?')}BA{f" · {listing.get('sqft'):,} sqft" if listing.get('sqft') else ''}</p>
            <p style="margin: 4px 0;">{commute}</p>
            <p style="margin: 4px 0;">{amenities_line}</p>
            <p style="margin: 4px 0;">⭐ Match Score: {score}/100</p>
        </div>
        <p>👉 <a href="{listing.get('url', '#')}" style="color: #0066cc;">View listing on {listing.get('source', 'site').title()}</a></p>
        <hr style="margin: 20px 0;">
        <p style="font-size: 18px; font-weight: bold;">Would you like to tour it?</p>
        <p>Reply <strong>Y</strong> to schedule a tour (we'll email the broker for you)</p>
        <p>Reply <strong>N</strong> to pass</p>
        <p style="color: #666; font-size: 12px;">Source: {listing.get('source', '').title()} | Listing #{listing.get('id', '')}</p>
    </div>
    """


def _build_broker_email(listing: dict) -> tuple[str, str]:
    """Build broker intro email using custom or default template."""
    placeholders = {
        "{{address}}": listing.get("address", "the listed address"),
        "{{price}}": f"${listing.get('price', '?'):,}" if listing.get("price") else "the listed price",
        "{{beds}}": str(listing.get("beds", "?")),
        "{{baths}}": str(listing.get("baths", "?")),
        "{{sqft}}": str(listing.get("sqft", "?")) if listing.get("sqft") else "N/A",
        "{{neighborhood}}": listing.get("neighborhood", ""),
        "{{source}}": listing.get("source", "").title(),
        "{{listing_url}}": listing.get("url", ""),
        "{{broker_name}}": listing.get("broker_name", ""),
        "{{your_name}}": settings.user_name or "Prospective Tenant",
        "{{your_phone}}": settings.user_phone or "",
        "{{your_email}}": settings.user_email or settings.alert_to_email or "",
    }

    if settings.use_custom_email_template:
        subject = settings.custom_email_subject
        body = settings.custom_email_body
    else:
        subject = "Inquiry about {{address}} - {{source}}"
        body = (
            "Hi {{broker_name}},\n\n"
            "I came across your listing at {{address}} "
            "({{beds}}BR/{{baths}}BA, {{price}}/mo) and "
            "I'm very interested in scheduling a viewing.\n\n"
            "Could you share available times this week?\n\n"
            "Best regards,\n"
            "{{your_name}}\n"
            "{{your_phone}}"
        )

    for placeholder, value in placeholders.items():
        subject = subject.replace(placeholder, str(value))
        body = body.replace(placeholder, str(value))

    return subject, body
