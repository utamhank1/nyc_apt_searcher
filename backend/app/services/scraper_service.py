import hashlib
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.listing import Listing
from app.models.search_config import SearchConfig
from app.scrapers.normalizer import normalize_listing
from app.services.matching_service import score_listing
from app.services.commute_service import get_commute_minutes

logger = structlog.get_logger()


async def _ensure_default_search(db: AsyncSession):
    """On first run, create a default search from env vars if no searches exist."""
    count = (await db.execute(select(SearchConfig))).scalars().first()
    if count:
        return

    default = SearchConfig(
        name="Default Search",
        is_active=True,
        boroughs=settings.boroughs_list,
        neighborhoods=settings.neighborhoods_list,
        max_price=settings.max_price,
        min_price=settings.min_price,
        min_beds=settings.min_beds,
        min_baths=settings.min_baths,
        must_have_amenities=settings.must_have_amenities_list,
        preferred_amenities=settings.preferred_amenities_list,
        work_address=settings.work_address,
        lead_score_threshold=settings.lead_score_threshold,
        sources_enabled=settings.sources_enabled_dict,
        move_in_mode=settings.move_in_mode,
        move_in_date=settings.move_in_date,
        move_in_range_start=settings.move_in_range_start,
        move_in_range_end=settings.move_in_range_end,
        move_in_only=settings.move_in_only,
    )
    db.add(default)
    await db.commit()
    logger.info("Created default search from env vars")


async def run_scrape():
    """Run scraping for all active saved searches."""
    logger.info("Starting scrape run")

    async with async_session_factory() as db:
        await _ensure_default_search(db)

        result = await db.execute(select(SearchConfig).where(SearchConfig.is_active == True))
        active_searches = result.scalars().all()

        if not active_searches:
            logger.warning("No active searches configured")
            return

        logger.info(f"Running {len(active_searches)} active search(es)")

        for search_config in active_searches:
            try:
                await _run_search(search_config, db)
            except Exception as e:
                logger.error("Search failed", search_name=search_config.name, error=str(e))

    logger.info("Scrape run complete")


async def _run_search(search_config: SearchConfig, db: AsyncSession):
    """Run scrapers for a single search config."""
    criteria = search_config.to_criteria_dict()
    sources = criteria.get("sources_enabled", {})
    search_name = search_config.name

    logger.info(f"Scraping for: {search_name}")

    all_raw_listings = []

    try:
        from app.scrapers.realtor_api import search_realtor_api
        raw = await search_realtor_api(criteria)
        all_raw_listings.extend(raw)
        logger.info(f"Realtor.com [{search_name}]: {len(raw)} listings")
    except Exception as e:
        logger.error("Realtor.com API failed", search=search_name, error=str(e))

    if not all_raw_listings:
        logger.warning(f"No listings found for: {search_name}")
        return

    new_leads = []
    threshold = criteria.get("lead_score_threshold", 70)

    for raw in all_raw_listings:
        try:
            normalized = normalize_listing(raw)

            existing = await db.execute(
                select(Listing).where(
                    Listing.source == normalized["source"],
                    Listing.source_id == normalized["source_id"],
                )
            )
            existing_listing = existing.scalar_one_or_none()

            commute = None
            if normalized.get("address") and criteria.get("work_address"):
                commute = await get_commute_minutes(normalized["address"])
            normalized["commute_minutes"] = commute

            score = score_listing(normalized, criteria)
            if score is None:
                continue

            normalized["match_score"] = score

            if existing_listing:
                existing_listing.price = normalized.get("price", existing_listing.price)
                existing_listing.last_seen = datetime.utcnow()
                existing_listing.is_active = True
                if commute:
                    existing_listing.commute_minutes = commute
                existing_listing.match_score = score
                existing_listing.search_config_id = search_config.id
                existing_listing.search_name = search_name
            else:
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
                    available_date=normalized.get("available_date"),
                    commute_minutes=commute,
                    match_score=score,
                    search_config_id=search_config.id,
                    search_name=search_name,
                )
                db.add(listing)
                await db.flush()

                if score >= 65:
                    new_leads.append(listing)

        except Exception as e:
            logger.error("Failed to process listing", error=str(e), source=raw.source)

    await db.commit()

    for listing in new_leads:
        if not listing.notified:
            await _send_alerts(listing, db)

    logger.info(f"[{search_name}] complete: {len(all_raw_listings)} raw, {len(new_leads)} hot leads")


async def _send_alerts(listing: Listing, db: AsyncSession):
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
        "available_date": listing.available_date,
        "commute_minutes": listing.commute_minutes,
        "match_score": listing.match_score,
        "search_name": listing.search_name,
        "broker_email": listing.broker_email,
        "open_house_dates": listing.open_house_dates or [],
    }

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
        logger.info("Alerts sent", listing_id=listing.id, search=listing.search_name)


async def process_single_listing(raw, db: AsyncSession, force_alert: bool = False) -> Listing | None:
    """Process a single manually submitted listing."""
    normalized = normalize_listing(raw)

    existing = await db.execute(
        select(Listing).where(
            Listing.source == normalized["source"],
            Listing.source_id == normalized["source_id"],
        )
    )
    existing_listing = existing.scalar_one_or_none()

    commute = None
    if normalized.get("address"):
        commute = await get_commute_minutes(normalized["address"])
    normalized["commute_minutes"] = commute

    score = score_listing(normalized)
    if score is None:
        score = 50.0
    normalized["match_score"] = score

    if existing_listing:
        existing_listing.price = normalized.get("price", existing_listing.price)
        existing_listing.last_seen = datetime.utcnow()
        existing_listing.is_active = True
        existing_listing.commute_minutes = commute or existing_listing.commute_minutes
        existing_listing.match_score = score
        existing_listing.amenities = normalized.get("amenities") or existing_listing.amenities
        existing_listing.broker_name = normalized.get("broker_name") or existing_listing.broker_name
        existing_listing.broker_email = normalized.get("broker_email") or existing_listing.broker_email
        existing_listing.broker_phone = normalized.get("broker_phone") or existing_listing.broker_phone
        existing_listing.available_date = normalized.get("available_date") or existing_listing.available_date
        existing_listing.open_house_dates = normalized.get("open_house_dates") or existing_listing.open_house_dates
        existing_listing.description = normalized.get("description") or existing_listing.description
        existing_listing.search_name = "Manual"
        await db.commit()
        listing = existing_listing
    else:
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
            available_date=normalized.get("available_date"),
            commute_minutes=commute,
            match_score=score,
            search_name="Manual",
        )
        db.add(listing)
        await db.flush()
        await db.commit()

    if force_alert:
        await _send_alerts(listing, db)

    return listing
