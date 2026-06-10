from datetime import date, datetime

import structlog

from app.core.config import settings

logger = structlog.get_logger()


def _parse_date(val: str) -> date | None:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        return None


def _check_move_in_date(listing_data: dict, criteria: dict) -> bool | None:
    mode = criteria.get("move_in_mode", "")
    if not mode:
        return True

    listing_date_str = listing_data.get("available_date")
    if not listing_date_str:
        return None

    if listing_date_str.lower() in ("immediately", "now", "asap"):
        listing_date = date.today()
    else:
        listing_date = _parse_date(listing_date_str)
        if not listing_date:
            return None

    if mode == "immediately":
        return listing_date <= date.today()
    elif mode == "date":
        target = _parse_date(criteria.get("move_in_date", ""))
        if not target:
            return True
        return listing_date <= target
    elif mode == "range":
        start = _parse_date(criteria.get("move_in_range_start", ""))
        end = _parse_date(criteria.get("move_in_range_end", ""))
        if start and listing_date < start:
            return False
        if end and listing_date > end:
            return False
        return True

    return True


def score_listing(listing_data: dict, criteria: dict | None = None) -> float | None:
    """Score a listing against search criteria.
    If criteria is None, falls back to global settings (backward compat)."""
    if criteria is None:
        criteria = {
            "boroughs": settings.boroughs_list,
            "neighborhoods": settings.neighborhoods_list,
            "max_price": settings.max_price,
            "min_beds": settings.min_beds,
            "must_have_amenities": settings.must_have_amenities_list,
            "preferred_amenities": settings.preferred_amenities_list,
            "move_in_mode": settings.move_in_mode,
            "move_in_date": settings.move_in_date,
            "move_in_range_start": settings.move_in_range_start,
            "move_in_range_end": settings.move_in_range_end,
            "move_in_only": settings.move_in_only,
            "lead_score_threshold": settings.lead_score_threshold,
        }

    boroughs = criteria.get("boroughs", [])
    if boroughs and listing_data.get("borough"):
        if listing_data["borough"] not in boroughs:
            return None

    max_price = criteria.get("max_price", 0)
    if max_price and listing_data.get("price"):
        if listing_data["price"] > max_price * 1.05:
            return None

    min_beds = criteria.get("min_beds", 0)
    if min_beds and listing_data.get("beds"):
        if listing_data["beds"] < min_beds:
            return None

    must_haves = criteria.get("must_have_amenities", [])
    if must_haves and listing_data.get("amenities"):
        listing_amenities_lower = [a.lower() for a in listing_data["amenities"]]
        for must_have in must_haves:
            if must_have.lower() not in listing_amenities_lower:
                return None

    date_match = _check_move_in_date(listing_data, criteria)
    if criteria.get("move_in_only"):
        if date_match is False:
            return None
        if date_match is None and criteria.get("move_in_mode"):
            return None

    score = 0.0

    if max_price and listing_data.get("price"):
        price_ratio = listing_data["price"] / max_price
        if price_ratio <= 1.0:
            score += (1 - price_ratio) * 30
        else:
            score += max(0, (1 - (price_ratio - 1) * 5)) * 10

    neighborhoods = criteria.get("neighborhoods", [])
    if neighborhoods and listing_data.get("neighborhood"):
        if listing_data["neighborhood"] in neighborhoods:
            score += 25
        elif listing_data.get("borough") in boroughs:
            score += 10

    preferred = criteria.get("preferred_amenities", [])
    if preferred and listing_data.get("amenities"):
        listing_amenities_lower = {a.lower() for a in listing_data["amenities"]}
        preferred_lower = {a.lower() for a in preferred}
        overlap = len(listing_amenities_lower & preferred_lower)
        if len(preferred_lower) > 0:
            score += (overlap / len(preferred_lower)) * 25

    max_commute = 60
    if listing_data.get("commute_minutes") is not None:
        commute = listing_data["commute_minutes"]
        if commute <= max_commute:
            score += (1 - commute / max_commute) * 20

    return round(score, 1)
