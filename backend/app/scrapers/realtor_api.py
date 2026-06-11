import httpx
import structlog

from app.core.config import settings
from app.scrapers.models import RawListing

logger = structlog.get_logger()

RAPIDAPI_HOST = "realtor16.p.rapidapi.com"
SEARCH_URL = f"https://{RAPIDAPI_HOST}/api/v1/rentals"

# Neighborhood to city/zip mappings for Realtor.com API
NYC_BOROUGH_CITIES = {
    "Manhattan": "New York",
    "Brooklyn": "Brooklyn",
    "Queens": "Queens",
    "Bronx": "Bronx",
    "Staten Island": "Staten Island",
}


async def search_realtor_api(criteria: dict) -> list[RawListing]:
    """Search Realtor.com via RapidAPI for NYC rentals."""
    if not settings.rapidapi_key:
        logger.warning("RapidAPI key not configured, skipping Realtor.com")
        return []

    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }

    all_listings = []
    boroughs = criteria.get("boroughs", ["New York"])

    for borough in boroughs:
        city = NYC_BOROUGH_CITIES.get(borough, borough)
        params = {
            "city": city,
            "state_code": "NY",
            "status": "for_rent",
            "limit": "20",
            "offset": "0",
            "sort": "newest",
        }

        if criteria.get("min_price"):
            params["price_min"] = str(criteria["min_price"])
        if criteria.get("max_price"):
            params["price_max"] = str(criteria["max_price"])
        if criteria.get("min_beds"):
            params["beds_min"] = str(criteria["min_beds"])

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCH_URL, headers=headers, params=params)

                if resp.status_code == 429:
                    logger.warning("RapidAPI rate limit hit")
                    break
                if resp.status_code != 200:
                    logger.warning("Realtor API error", status=resp.status_code, body=resp.text[:200])
                    continue

                data = resp.json()
                properties = data.get("properties", data.get("results", data.get("listings", [])))

                if not properties:
                    # Try alternate response structure
                    if isinstance(data, list):
                        properties = data
                    elif "home_search" in data:
                        properties = data["home_search"].get("results", [])

                for prop in properties:
                    listing = _parse_property(prop, borough)
                    if listing:
                        all_listings.append(listing)

                logger.info(f"Realtor.com [{borough}]: {len(properties)} properties found")

        except Exception as e:
            logger.error("Realtor API request failed", borough=borough, error=str(e))

    return all_listings


def _parse_property(prop: dict, borough: str) -> RawListing | None:
    try:
        property_id = str(prop.get("property_id") or prop.get("listing_id") or prop.get("id", ""))
        if not property_id:
            return None

        # Price
        price = None
        list_price = prop.get("list_price") or prop.get("price") or prop.get("rent")
        if isinstance(list_price, (int, float)):
            price = int(list_price)
        elif isinstance(list_price, str):
            import re
            m = re.search(r"[\d,]+", list_price)
            price = int(m.group().replace(",", "")) if m else None
        elif isinstance(list_price, dict):
            price = list_price.get("max") or list_price.get("min")

        # Address
        location = prop.get("location", {})
        address_data = location.get("address", prop.get("address", {}))
        if isinstance(address_data, dict):
            line = address_data.get("line", "")
            city = address_data.get("city", "")
            address = f"{line}, {city}" if line else city
            neighborhood = address_data.get("neighborhood_name") or address_data.get("neighborhood", "")
        elif isinstance(address_data, str):
            address = address_data
            neighborhood = ""
        else:
            address = prop.get("address", "")
            neighborhood = ""

        # Beds/baths
        description = prop.get("description", {})
        if isinstance(description, dict):
            beds = description.get("beds") or description.get("bedrooms")
            baths = description.get("baths") or description.get("bathrooms")
            sqft = description.get("sqft") or description.get("lot_sqft")
        else:
            beds = prop.get("beds") or prop.get("bedrooms")
            baths = prop.get("baths") or prop.get("bathrooms")
            sqft = prop.get("sqft") or prop.get("building_size", {}).get("size")

        # URL
        permalink = prop.get("permalink") or prop.get("web_url") or ""
        if permalink and not permalink.startswith("http"):
            url = f"https://www.realtor.com/realestateandhomes-detail/{permalink}"
        elif permalink:
            url = permalink
        else:
            url = f"https://www.realtor.com/realestateandhomes-detail/{property_id}"

        # Photos
        photos = prop.get("photos", prop.get("photo", []))
        images = []
        if isinstance(photos, list):
            for p in photos[:5]:
                if isinstance(p, dict):
                    images.append(p.get("href", p.get("url", "")))
                elif isinstance(p, str):
                    images.append(p)

        # Broker/agent
        advertisers = prop.get("advertisers", [])
        broker_name = None
        broker_phone = None
        if advertisers and isinstance(advertisers, list):
            agent = advertisers[0]
            broker_name = agent.get("name", "")
            phones = agent.get("phones", [])
            if phones and isinstance(phones, list):
                broker_phone = phones[0].get("number", "")

        return RawListing(
            source="realtor",
            source_id=property_id,
            url=url,
            title=address or f"Realtor #{property_id}",
            price=price,
            beds=int(beds) if beds else None,
            baths=float(baths) if baths else None,
            sqft=int(sqft) if sqft else None,
            address=address,
            neighborhood=neighborhood if isinstance(neighborhood, str) else None,
            borough=borough,
            images=images,
            broker_name=broker_name,
            broker_phone=broker_phone,
        )
    except Exception as e:
        logger.debug("Failed to parse Realtor property", error=str(e))
        return None
