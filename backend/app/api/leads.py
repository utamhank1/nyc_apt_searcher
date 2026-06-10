from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.listing import Listing, ListingStatus

router = APIRouter(tags=["leads"])


@router.get("/leads")
async def get_leads(
    status: Optional[str] = None,
    borough: Optional[str] = None,
    source: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    sort_by: str = Query("match_score", pattern="^(match_score|price|commute_minutes|first_seen)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Listing).where(Listing.is_active == True)

    if status:
        query = query.where(Listing.status == status)
    if borough:
        query = query.where(Listing.borough == borough)
    if source:
        query = query.where(Listing.source == source)
    if min_price is not None:
        query = query.where(Listing.price >= min_price)
    if max_price is not None:
        query = query.where(Listing.price <= max_price)

    col = getattr(Listing, sort_by, Listing.match_score)
    if sort_dir == "desc":
        query = query.order_by(col.desc().nulls_last())
    else:
        query = query.order_by(col.asc().nulls_last())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    listings = result.scalars().all()

    return {
        "items": [_listing_to_dict(l) for l in listings],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.patch("/leads/{listing_id}/status")
async def update_lead_status(
    listing_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    new_status = body.get("status")
    if new_status and new_status not in [s.value for s in ListingStatus]:
        return {"error": f"Invalid status: {new_status}"}

    stmt = update(Listing).where(Listing.id == listing_id)
    if new_status:
        stmt = stmt.values(status=new_status)
    await db.execute(stmt)
    await db.commit()
    return {"ok": True, "listing_id": listing_id, "status": new_status}


@router.post("/leads/submit-url")
async def submit_listing_url(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    url = (body.get("url") or "").strip()
    if not url:
        return {"error": "URL is required"}

    if "streeteasy.com" in url:
        source = "streeteasy"
    elif "zillow.com" in url:
        source = "zillow"
    else:
        return {"error": "URL must be from StreetEasy or Zillow"}

    try:
        if source == "streeteasy":
            from app.scrapers.streeteasy import StreetEasyScraper
            scraper = StreetEasyScraper()
            try:
                raw = await scraper.scrape_single_listing(url)
            finally:
                await scraper.close()
        else:
            from app.scrapers.zillow import ZillowScraper
            scraper = ZillowScraper()
            try:
                raw = await scraper.scrape_single_listing(url)
            finally:
                await scraper.close()

        if not raw:
            return {"error": "Could not scrape this listing. The page may have blocked the request."}

        from app.services.scraper_service import process_single_listing
        listing = await process_single_listing(raw, db, force_alert=True)

        if not listing:
            return {"error": "Failed to process listing"}

        return {"ok": True, "listing": _listing_to_dict(listing)}

    except Exception as e:
        return {"error": f"Scraping failed: {str(e)}"}


@router.post("/leads/{listing_id}/preview-email")
async def preview_broker_email(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        return {"error": "Listing not found"}

    from app.services.email_service import get_broker_email_preview
    preview = await get_broker_email_preview(listing)
    return {"ok": True, "listing_id": listing_id, **preview}


@router.post("/leads/{listing_id}/send-email")
async def send_custom_broker_email(
    listing_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        return {"error": "Listing not found"}

    from app.services.email_service import send_custom_broker_email as send_email
    sent = await send_email(
        listing,
        subject=body.get("subject", ""),
        body_text=body.get("body", ""),
    )

    if sent:
        listing.broker_email_sent = True
        from datetime import datetime
        listing.broker_email_sent_at = datetime.utcnow()
        listing.status = "tour_scheduled"
        await db.commit()

    return {"ok": sent, "listing_id": listing_id}


@router.post("/leads/{listing_id}/tour")
async def trigger_tour(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        return {"error": "Listing not found"}

    from app.services.lead_flow_service import process_yes_response
    await process_yes_response(listing, db)
    return {"ok": True, "listing_id": listing_id, "message": "Tour flow triggered"}


def _listing_to_dict(l: Listing) -> dict:
    return {
        "id": l.id,
        "source": l.source,
        "source_id": l.source_id,
        "url": l.url,
        "title": l.title,
        "price": l.price,
        "beds": l.beds,
        "baths": l.baths,
        "sqft": l.sqft,
        "address": l.address,
        "neighborhood": l.neighborhood,
        "borough": l.borough,
        "amenities": l.amenities or [],
        "images": l.images or [],
        "broker_name": l.broker_name,
        "broker_email": l.broker_email,
        "broker_phone": l.broker_phone,
        "open_house_dates": l.open_house_dates or [],
        "description": l.description,
        "available_date": l.available_date,
        "commute_minutes": l.commute_minutes,
        "match_score": l.match_score,
        "status": l.status,
        "lead_response": l.lead_response,
        "notified": l.notified,
        "is_active": l.is_active,
        "first_seen": l.first_seen.isoformat() if l.first_seen else None,
        "broker_email_sent": l.broker_email_sent,
    }
