import structlog
import googlemaps

from app.core.config import settings

logger = structlog.get_logger()

_cache: dict[str, int | None] = {}


async def get_commute_minutes(address: str) -> int | None:
    """Get transit commute time in minutes from address to work address."""
    if not settings.google_maps_api_key or not settings.work_address:
        return None

    if not address:
        return None

    cache_key = f"{address}|{settings.work_address}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        gmaps = googlemaps.Client(key=settings.google_maps_api_key)
        result = gmaps.directions(
            origin=address,
            destination=settings.work_address,
            mode="transit",
            departure_time="now",
        )

        if result and result[0].get("legs"):
            duration_seconds = result[0]["legs"][0]["duration"]["value"]
            minutes = round(duration_seconds / 60)
            _cache[cache_key] = minutes
            return minutes

    except Exception as e:
        logger.warning("Commute calculation failed", address=address, error=str(e))

    _cache[cache_key] = None
    return None
