from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing, ListingStatus, LeadResponse

logger = structlog.get_logger()


def _listing_to_dict(listing: Listing) -> dict:
    return {
        "id": listing.id,
        "source": listing.source,
        "source_id": listing.source_id,
        "url": listing.url,
        "title": listing.title,
        "price": listing.price,
        "beds": listing.beds,
        "baths": listing.baths,
        "sqft": listing.sqft,
        "address": listing.address,
        "neighborhood": listing.neighborhood,
        "borough": listing.borough,
        "amenities": listing.amenities or [],
        "broker_name": listing.broker_name,
        "broker_email": listing.broker_email,
        "broker_phone": listing.broker_phone,
        "commute_minutes": listing.commute_minutes,
        "match_score": listing.match_score,
    }


async def process_yes_response(listing: Listing, db: AsyncSession):
    """Handle a 'Yes' reply — send broker email with user + partners CC'd."""
    logger.info("Processing YES response", listing_id=listing.id)

    listing.lead_response = LeadResponse.YES.value
    listing.lead_responded_at = datetime.utcnow()
    listing.status = ListingStatus.PENDING.value

    listing_dict = _listing_to_dict(listing)

    from app.services.email_service import send_broker_email
    sent = await send_broker_email(listing_dict)

    if sent:
        listing.broker_email_sent = True
        listing.broker_email_sent_at = datetime.utcnow()
        listing.status = ListingStatus.TOUR_SCHEDULED.value
        logger.info("Broker email sent successfully", listing_id=listing.id)
    else:
        logger.warning("Could not send broker email", listing_id=listing.id)

    await db.commit()


async def process_no_response(listing: Listing, db: AsyncSession):
    """Handle a 'No' reply — mark as passed."""
    logger.info("Processing NO response", listing_id=listing.id)

    listing.lead_response = LeadResponse.NO.value
    listing.lead_responded_at = datetime.utcnow()
    listing.status = ListingStatus.PASSED.value

    await db.commit()
