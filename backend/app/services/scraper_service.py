import hashlib
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.listing import Listing
from app.scrapers.normalizer import normalize_listing
from app.services.matching_service import score_listing
from app.services.commute_service import get_commute_minutes

logger = structlog.get_logger()


async def run_scrape():
    """Main scrape orchestrator. Runs all enabled scrapers, normalizes, scores, and alerts."""
    logger.info("Starting scrape run")

    sources = settings.sources_enabled_dict
    criteria = {
        "boroughs": settings.boroughs_list,
        "neighborhoods": settings.neighborhoods_list,
        "max_price": settings.max_price,
        "min_price": settings.min_price,
        "min_beds": settings.min_beds,
    }

    all_raw_listings = []

    if sources.get("streeteasy", True):
        try:
            from app.scrapers.streeteasy import StreetEasyScraper
            scraper = StreetEasyScraper()
            try:
                raw = await scraper.scrape(criteria)
                all_raw_listings.extend(raw)
                logger.info(f"StreetEasy: {len(raw)} listings found")
            finally:
                await scraper.close()
        except Exception as e:
            logger.error("StreetEasy scraper failed", error=str(e))

    if sources.get("zillow", True):
        try:
            from app.scrapers.zillow import ZillowScraper
            scraper = ZillowScraper()
            try:
                raw = await scraper.scrape(criteria)
                all_raw_listings.extend(raw)
                logger.info(f"Zillow: {len(raw)} listings found")
            finally:
                await scraper.close()
        except Exception as e:
            logger.error("Zillow scraper failed", error=str(e))

    if not all_raw_listings:
        logger.warning("No listings found from any source")
        return

    # Normalize, score, and persist
    new_leads = []
    async with async_session_factory() as db:
        for raw in all_raw_listings:
            try:
                normalized = normalize_listing(raw)

                # Check for existing listing
                existing = await db.execute(
                    select(Listing).where(
                        Listing.source == normalized["source"],
                        Listing.source_id == normalized["source_id"],
                    )
                )
                existing_listing = existing.scalar_one_or_none()

                # Calculate commute time
                commute = None
                if normalized.get("address"):
                    commute = await get_commute_minutes(normalized["address"])
                normalized["commute_minutes"] = commute

                # Score the listing
                score = score_listing(normalized)
                if score is None:
                    continue  # Hard-filtered out

                normalized["match_score"] = score

                if existing_listing:
                    # Update existing listing
                    existing_listing.price = normalized.get("price", existing_listing.price)
                    existing_listing.last_seen = datetime.utcnow()
                    existing_listing.is_active = True
                    if normalized.get("commute_minutes"):
                        existing_listing.commute_minutes = normalized["commute_minutes"]
                    existing_listing.match_score = score
                else:
                    # Create new listing
                    listing = Listing(
                        source=normalized["source"],
                        source_id=normalized["source_id"],
                        url=normalized["url"],
                        title=normalized.get("title"),
                        price=normalized.get("price"),
                        beds=normalized.get("beds"),
                        baths=normalized.get("baths"),
                        sqft=normalized.get("sqft"),
                        address=normalized.get("address"),
                        neighborhood=normalized.get("neighborhood"),
                        borough=normalized.get("borough"),
                        amenities=normalized.get("amenities"),
                        images=normalized.get("images"),
                        broker_name=normalized.get("broker_name"),
                        broker_email=normalized.get("broker_email"),
                        broker_phone=normalized.get("broker_phone"),
                        open_house_dates=normalized.get("open_house_dates"),
                        description=normalized.get("description"),
                        commute_minutes=commute,
                        match_score=score,
                    )
                    db.add(listing)
                    await db.flush()

                    # Check if this is a hot lead
                    if score >= settings.lead_score_threshold:
                        new_leads.append(listing)

            except Exception as e:
                logger.error("Failed to process listing", error=str(e), source=raw.source)

        await db.commit()

        # Send alerts for new hot leads
        for listing in new_leads:
            if not listing.notified:
                await _send_alerts(listing, db)

    logger.info(
        "Scrape run complete",
        total_raw=len(all_raw_listings),
        new_hot_leads=len(new_leads),
    )


async def _send_alerts(listing: Listing, db: AsyncSession):
    """Send email and Telegram alerts for a hot lead."""
    listing_dict = {
        "id": listing.id,
        "source": listing.source,
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
        "commute_minutes": listing.commute_minutes,
        "match_score": listing.match_score,
    }

    # Compute notification hash for dedup
    hash_input = f"{listing.price}|{listing.beds}|{listing.baths}|{listing.address}"
    current_hash = hashlib.md5(hash_input.encode()).hexdigest()

    if listing.notified_hash == current_hash:
        return

    from app.services.email_service import send_alert_email
    from app.services.telegram_service import send_telegram_alert

    email_sent = await send_alert_email(listing_dict)
    telegram_sent = await send_telegram_alert(listing_dict)

    if email_sent or telegram_sent:
        listing.notified = True
        listing.notified_hash = current_hash
        listing.status = "alerted"
        await db.commit()
        logger.info("Alerts sent", listing_id=listing.id, email=email_sent, telegram=telegram_sent)
