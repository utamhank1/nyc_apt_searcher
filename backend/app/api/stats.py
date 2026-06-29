from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.listing import Listing, ListingStatus

router = APIRouter(tags=["stats"])


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Listing.id)))).scalar() or 0
    active = (await db.execute(
        select(func.count(Listing.id)).where(Listing.is_active == True)
    )).scalar() or 0

    hot_leads = (await db.execute(
        select(func.count(Listing.id)).where(
            Listing.match_score != None,
            Listing.match_score >= 65,
            Listing.is_active == True,
        )
    )).scalar() or 0

    tours_scheduled = (await db.execute(
        select(func.count(Listing.id)).where(Listing.status == ListingStatus.TOUR_SCHEDULED.value)
    )).scalar() or 0

    broker_emails = (await db.execute(
        select(func.count(Listing.id)).where(Listing.broker_email_sent == True)
    )).scalar() or 0

    passed = (await db.execute(
        select(func.count(Listing.id)).where(Listing.status == ListingStatus.PASSED.value)
    )).scalar() or 0

    last_listing = (await db.execute(
        select(Listing.created_at).order_by(Listing.created_at.desc()).limit(1)
    )).scalar()

    return {
        "total_listings": total,
        "active_listings": active,
        "hot_leads": hot_leads,
        "tours_scheduled": tours_scheduled,
        "broker_emails_sent": broker_emails,
        "passed": passed,
        "last_scrape": last_listing.isoformat() if last_listing else None,
    }
