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


def _check_move_in_date(listing_data: dict) -> bool | None:
    """Check if listing matches move-in date criteria.
    Returns True if matches, False if doesn't, None if no date info available."""
    mode = settings.move_in_mode
    if not mode:
        return True

    listing_date_str = listing_data.get("available_date")
    if not listing_date_str:
        return None  # no date info on listing

    if listing_date_str.lower() in ("immediately", "now", "asap"):
        listing_date = date.today()
    else:
        listing_date = _parse_date(listing_date_str)
        if not listing_date:
            return None

    if mode == "immediately":
        return listing_date <= date.today()
    elif mode == "date":
        target = _parse_date(settings.move_in_date)
        if not target:
            return True
        return listing_date <= target
    elif mode == "range":
        start = _parse_date(settings.move_in_range_start)
        end = _parse_date(settings.move_in_range_end)
        if start and listing_date < start:
            return False
        if end and listing_date > end:
            return False
        return True

    return True


def score_listing(listing_data: dict) -> float | None:
    """Score a listing against the current search criteria.
    Returns None if hard-filtered out, or 0-100 score."""

    # Hard filters — return None to exclude
    boroughs = settings.boroughs_list
    if boroughs and listing_data.get("borough"):
        if listing_data["borough"] not in boroughs:
            return None

    max_price = settings.max_price
    if max_price and listing_data.get("price"):
        if listing_data["price"] > max_price * 1.05:
            return None

    min_beds = settings.min_beds
    if min_beds and listing_data.get("beds"):
        if listing_data["beds"] < min_beds:
            return None

    must_haves = settings.must_have_amenities_list
    if must_haves and listing_data.get("amenities"):
        listing_amenities_lower = [a.lower() for a in listing_data["amenities"]]
        for must_have in must_haves:
            if must_have.lower() not in listing_amenities_lower:
                return None

    # Move-in date filter
    date_match = _check_move_in_date(listing_data)
    if settings.move_in_only:
        if date_match is False:
            return None
        if date_match is None and settings.move_in_mode:
            return None  # no date info = excluded in "only" mode

    # Soft scoring (0-100)
    score = 0.0

    # Price closeness (30 points) — cheaper is better
    if max_price and listing_data.get("price"):
        price_ratio = listing_data["price"] / max_price
        if price_ratio <= 1.0:
            score += (1 - price_ratio) * 30
        else:
            score += max(0, (1 - (price_ratio - 1) * 5)) * 10

    # Neighborhood match (25 points)
    neighborhoods = settings.neighborhoods_list
    if neighborhoods and listing_data.get("neighborhood"):
        if listing_data["neighborhood"] in neighborhoods:
            score += 25
        elif listing_data.get("borough") in boroughs:
            score += 10

    # Preferred amenity overlap (25 points)
    preferred = settings.preferred_amenities_list
    if preferred and listing_data.get("amenities"):
        listing_amenities_lower = {a.lower() for a in listing_data["amenities"]}
        preferred_lower = {a.lower() for a in preferred}
        overlap = len(listing_amenities_lower & preferred_lower)
        if len(preferred_lower) > 0:
            score += (overlap / len(preferred_lower)) * 25

    # Commute time (20 points) — shorter is better
    max_commute = 60
    if listing_data.get("commute_minutes") is not None:
        commute = listing_data["commute_minutes"]
        if commute <= max_commute:
            score += (1 - commute / max_commute) * 20

    return round(score, 1)
