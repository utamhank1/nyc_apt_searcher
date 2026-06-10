from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.search_config import SearchConfig

router = APIRouter(tags=["searches"])

MAX_ACTIVE = 3


@router.get("/searches")
async def list_searches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SearchConfig).order_by(SearchConfig.is_active.desc(), SearchConfig.updated_at.desc()))
    searches = result.scalars().all()
    return {"items": [s.to_dict() for s in searches]}


@router.post("/searches")
async def create_search(body: dict, db: AsyncSession = Depends(get_db)):
    search = SearchConfig(
        name=body.get("name", "Untitled Search"),
        is_active=False,
        boroughs=body.get("boroughs", ["Manhattan", "Brooklyn"]),
        neighborhoods=body.get("neighborhoods", []),
        max_price=body.get("max_price", 3500),
        min_price=body.get("min_price", 0),
        min_beds=body.get("min_beds", 1),
        min_baths=body.get("min_baths", 1),
        must_have_amenities=body.get("must_have_amenities", []),
        preferred_amenities=body.get("preferred_amenities", []),
        work_address=body.get("work_address", ""),
        lead_score_threshold=body.get("lead_score_threshold", 70),
        sources_enabled=body.get("sources_enabled", {"streeteasy": True, "zillow": True}),
        move_in_mode=body.get("move_in_mode", ""),
        move_in_date=body.get("move_in_date", ""),
        move_in_range_start=body.get("move_in_range_start", ""),
        move_in_range_end=body.get("move_in_range_end", ""),
        move_in_only=body.get("move_in_only", False),
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)
    return {"ok": True, "search": search.to_dict()}


@router.put("/searches/{search_id}")
async def update_search(search_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SearchConfig).where(SearchConfig.id == search_id))
    search = result.scalar_one_or_none()
    if not search:
        return {"error": "Search not found"}
    if search.is_active:
        return {"error": "Cannot edit an active search. Deactivate it first."}

    for field in ["name", "boroughs", "neighborhoods", "max_price", "min_price", "min_beds",
                   "min_baths", "must_have_amenities", "preferred_amenities", "work_address",
                   "lead_score_threshold", "sources_enabled", "move_in_mode", "move_in_date",
                   "move_in_range_start", "move_in_range_end", "move_in_only"]:
        if field in body:
            setattr(search, field, body[field])

    search.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "search": search.to_dict()}


@router.delete("/searches/{search_id}")
async def delete_search(search_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SearchConfig).where(SearchConfig.id == search_id))
    search = result.scalar_one_or_none()
    if not search:
        return {"error": "Search not found"}
    if search.is_active:
        return {"error": "Cannot delete an active search. Deactivate it first."}

    await db.delete(search)
    await db.commit()
    return {"ok": True}


@router.post("/searches/{search_id}/activate")
async def activate_search(search_id: int, db: AsyncSession = Depends(get_db)):
    active_count = (await db.execute(
        select(func.count(SearchConfig.id)).where(SearchConfig.is_active == True)
    )).scalar() or 0

    if active_count >= MAX_ACTIVE:
        return {"error": f"Maximum {MAX_ACTIVE} active searches allowed. Deactivate one first."}

    result = await db.execute(select(SearchConfig).where(SearchConfig.id == search_id))
    search = result.scalar_one_or_none()
    if not search:
        return {"error": "Search not found"}

    search.is_active = True
    search.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "search": search.to_dict()}


@router.post("/searches/{search_id}/deactivate")
async def deactivate_search(search_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SearchConfig).where(SearchConfig.id == search_id))
    search = result.scalar_one_or_none()
    if not search:
        return {"error": "Search not found"}

    search.is_active = False
    search.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "search": search.to_dict()}
