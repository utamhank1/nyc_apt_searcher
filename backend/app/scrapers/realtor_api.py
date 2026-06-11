import re

import httpx
import structlog

from app.core.config import settings
from app.scrapers.models import RawListing

logger = structlog.get_logger()

RAPIDAPI_HOST = "realtor-search.p.rapidapi.com"
SEARCH_URL = f"https://{RAPIDAPI_HOST}/properties/search-rent"

BOROUGH_LOCATIONS = {
    "Manhattan": "city:New York, NY",
    "Brooklyn": "city:Brooklyn, NY",
    "Queens": "city:Queens, NY",
    "Bronx": "city:Bronx, NY",
    "Staten Island": "city:Staten Island, NY",
}

AMENITY_TO_NYC_PARAM = {
    "dishwasher": "dishwasher",
    "doorman": "community_doorman",
    "elevator": "community_elevator",
    "outdoor space": "community_outdoor_space",
}

AMENITY_TO_FEATURE_PARAM = {
    "washer/dryer in unit": "washer_dryer",
    "gym": "community_gym",
    "parking available": "garage_1_or_more",
    "air conditioning": "central_air",
}


async def search_realtor_api(criteria: dict) -> list[RawListing]:
    if not settings.rapidapi_key:
        logger.warning("RapidAPI key not configured")
        return []

    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }

    all_listings = []
    boroughs = criteria.get("boroughs", ["Manhattan"])

    for borough in boroughs:
        location = BOROUGH_LOCATIONS.get(borough, f"city:{borough}, NY")

        params = {
            "location": location,
            "resultsPerPage": "20",
            "sortBy": "newest",
        }

        prices = []
        if criteria.get("min_price"):
            prices.append(str(criteria["min_price"]))
        if criteria.get("max_price"):
            if not prices:
                prices.append("")
            prices.append(str(criteria["max_price"]))
        if prices:
            params["prices"] = ",".join(prices)

        if criteria.get("min_beds"):
            params["bedrooms"] = str(criteria["min_beds"])

        if criteria.get("move_in_date"):
            params["moveInDate"] = criteria["move_in_date"]

        # Map must-have amenities to API params
        must_haves = criteria.get("must_have_amenities", [])
        nyc_amenities = []
        features = []
        for a in must_haves:
            a_lower = a.lower()
            if a_lower in AMENITY_TO_NYC_PARAM:
                nyc_amenities.append(AMENITY_TO_NYC_PARAM[a_lower])
            if a_lower in AMENITY_TO_FEATURE_PARAM:
                features.append(AMENITY_TO_FEATURE_PARAM[a_lower])
            if a_lower == "pets allowed":
                params["pets"] = "cats,dogs"

        if nyc_amenities:
            params["nycAmenities"] = ",".join(nyc_amenities)
        if features:
            params["features"] = ",".join(features)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCH_URL, headers=headers, params=params)

                if resp.status_code == 429:
                    logger.warning("RapidAPI rate limit hit")
                    break
                if resp.status_code != 200:
                    logger.warning("Realtor API error", status=resp.status_code, body=resp.text[:300])
                    continue

                data = resp.json()
                results = data.get("data", {}).get("results", [])

                for prop in results:
                    listing = _parse_property(prop, borough)
                    if listing:
                        all_listings.append(listing)

                total = data.get("data", {}).get("total", 0)
                logger.info(f"Realtor.com [{borough}]: {len(results)} fetched, {total} total available")

        except Exception as e:
            logger.error("Realtor API request failed", borough=borough, error=str(e))

    return all_listings


def _parse_property(prop: dict, borough: str) -> RawListing | None:
    try:
        property_id = str(prop.get("property_id") or prop.get("listing_id") or "")
        if not property_id:
            return None

        price = prop.get("list_price")
        if isinstance(price, str):
            m = re.search(r"[\d,]+", price)
            price = int(m.group().replace(",", "")) if m else None

        location = prop.get("location", {})
        address_data = location.get("address", {})
        line = address_data.get("line", "")
        city = address_data.get("city", "")
        address = f"{line}, {city}" if line else city

        neighborhood = None
        neighborhoods = location.get("neighborhoods")
        if neighborhoods and isinstance(neighborhoods, list):
            neighborhood = neighborhoods[0].get("name", "") if neighborhoods[0] else None

        county = location.get("county", {})
        detected_borough = county.get("name", borough)

        desc = prop.get("description", {})
        beds = desc.get("beds")
        baths = desc.get("baths")
        sqft = desc.get("sqft")
        prop_type = desc.get("type", "")

        url = prop.get("href", "")
        if not url:
            url = f"https://www.realtor.com/rentals/details/{property_id}"

        # Photos
        images = []
        primary = prop.get("primary_photo")
        if primary and isinstance(primary, dict):
            images.append(primary.get("href", ""))
        photos = prop.get("photos") or []
        for p in photos[:5]:
            if isinstance(p, dict):
                images.append(p.get("href", ""))

        # Broker info
        broker_name = None
        broker_phone = None
        advertisers = prop.get("advertisers") or []
        if advertisers:
            agent = advertisers[0]
            broker_name = agent.get("name", "")

        branding = prop.get("branding") or []
        office_name = ""
        if branding:
            office_name = branding[0].get("name", "")

        # Extract amenities from details
        amenities = []
        details = prop.get("details") or []
        for detail in details:
            category = detail.get("category", "")
            if category in ("Appliances", "Interior Features", "Heating and Cooling", "Garage and Parking"):
                for text in detail.get("text", []):
                    amenities.append(text)

        # Extract available date from details
        available_date = None
        for detail in details:
            for text in detail.get("text", []):
                if "Availability Date" in text:
                    date_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
                    if date_match:
                        available_date = date_match.group()

        # Open houses
        open_houses = prop.get("open_houses") or []
        open_house_dates = []
        for oh in open_houses:
            if isinstance(oh, dict):
                open_house_dates.append({
                    "date": oh.get("start_date", oh.get("date", "")),
                    "start_time": oh.get("start_time", ""),
                    "end_time": oh.get("end_time", ""),
                })

        title = f"{line}" if line else f"Realtor #{property_id}"

        return RawListing(
            source="realtor",
            source_id=property_id,
            url=url,
            title=title,
            price=int(price) if price else None,
            beds=int(beds) if beds else None,
            baths=float(baths) if baths else None,
            sqft=int(sqft) if sqft else None,
            address=address,
            neighborhood=neighborhood,
            borough=detected_borough,
            images=[i for i in images if i],
            broker_name=broker_name or office_name or None,
            description=prop_type,
            available_date=available_date,
            open_house_dates=open_house_dates,
            amenities=amenities,
        )
    except Exception as e:
        logger.debug("Failed to parse Realtor property", error=str(e))
        return None
