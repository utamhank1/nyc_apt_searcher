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

NEIGHBORHOOD_ZIP_CODES = {
    # Manhattan
    "Chelsea": ["10001", "10011"],
    "East Harlem": ["10029", "10035"],
    "East Village": ["10003", "10009"],
    "Financial District": ["10004", "10005", "10006", "10007", "10038"],
    "Flatiron": ["10010", "10016"],
    "Gramercy Park": ["10003", "10010"],
    "Greenwich Village": ["10003", "10011", "10012", "10014"],
    "Harlem": ["10026", "10027", "10030", "10037", "10039"],
    "Hell's Kitchen": ["10018", "10019", "10036"],
    "Inwood": ["10034", "10040"],
    "Kips Bay": ["10010", "10016"],
    "Lower East Side": ["10002"],
    "Midtown East": ["10017", "10022", "10055"],
    "Midtown West": ["10018", "10019", "10036"],
    "Murray Hill": ["10016", "10017"],
    "NoHo": ["10003", "10012"],
    "Nolita": ["10012", "10013"],
    "SoHo": ["10012", "10013"],
    "Tribeca": ["10007", "10013"],
    "Upper East Side": ["10021", "10028", "10065", "10075", "10128"],
    "Upper West Side": ["10023", "10024", "10025"],
    "Washington Heights": ["10031", "10032", "10033", "10040"],
    "West Village": ["10011", "10014"],
    # Brooklyn
    "Bay Ridge": ["11209", "11220"],
    "Bed-Stuy": ["11205", "11206", "11216", "11221", "11233"],
    "Boerum Hill": ["11201", "11217"],
    "Brooklyn Heights": ["11201"],
    "Bushwick": ["11206", "11207", "11221", "11237"],
    "Carroll Gardens": ["11231"],
    "Cobble Hill": ["11201", "11231"],
    "Crown Heights": ["11213", "11216", "11225", "11238"],
    "Downtown Brooklyn": ["11201", "11217"],
    "DUMBO": ["11201"],
    "Fort Greene": ["11205", "11217"],
    "Greenpoint": ["11222"],
    "Park Slope": ["11215", "11217"],
    "Prospect Heights": ["11217", "11238"],
    "Sunset Park": ["11220", "11232"],
    "Williamsburg": ["11211", "11249"],
    # Queens
    "Astoria": ["11102", "11103", "11105", "11106"],
    "Flushing": ["11354", "11355", "11358"],
    "Forest Hills": ["11375"],
    "Jackson Heights": ["11372", "11373"],
    "Long Island City": ["11101", "11109"],
    "Sunnyside": ["11104"],
    # Bronx
    "Concourse": ["10451", "10452", "10456"],
    "Fordham": ["10458", "10468"],
    "Mott Haven": ["10451", "10454", "10455"],
    "Riverdale": ["10463", "10471"],
    # Staten Island
    "St. George": ["10301"],
    "Tompkinsville": ["10301", "10304"],
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

    # Build common params (price, beds, amenities, move-in)
    common_params = {"resultsPerPage": "20", "sortBy": "newest"}

    prices = []
    if criteria.get("min_price"):
        prices.append(str(criteria["min_price"]))
    if criteria.get("max_price"):
        if not prices:
            prices.append("")
        prices.append(str(criteria["max_price"]))
    if prices:
        common_params["prices"] = ",".join(prices)

    if criteria.get("min_beds"):
        common_params["bedrooms"] = str(criteria["min_beds"])

    if criteria.get("move_in_date"):
        common_params["moveInDate"] = criteria["move_in_date"]

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
            common_params["pets"] = "cats,dogs"
    if nyc_amenities:
        common_params["nycAmenities"] = ",".join(nyc_amenities)
    if features:
        common_params["features"] = ",".join(features)

    # Determine search strategy: zip codes (if neighborhoods selected) or city (if not)
    neighborhoods = criteria.get("neighborhoods", [])
    boroughs = criteria.get("boroughs", ["Manhattan"])

    search_targets = []

    if neighborhoods:
        # Collect unique zip codes for selected neighborhoods
        zip_codes = set()
        nh_to_zip_found = {}
        for nh in neighborhoods:
            zips = NEIGHBORHOOD_ZIP_CODES.get(nh, [])
            if zips:
                zip_codes.update(zips)
                nh_to_zip_found[nh] = zips
            else:
                logger.warning(f"No zip codes mapped for neighborhood: {nh}")

        # Search by zip code — group into batches to limit API calls
        for zip_code in sorted(zip_codes):
            # Map zip back to borough for tagging
            borough = _zip_to_borough(zip_code, neighborhoods)
            search_targets.append({
                "location": f"postal_code:{zip_code}",
                "borough": borough,
                "label": zip_code,
            })

        logger.info(f"Searching {len(zip_codes)} zip codes for {len(neighborhoods)} neighborhoods")
    else:
        # No neighborhoods selected — search by borough
        for borough in boroughs:
            location = BOROUGH_LOCATIONS.get(borough, f"city:{borough}, NY")
            search_targets.append({
                "location": location,
                "borough": borough,
                "label": borough,
            })

    all_listings = []
    seen_ids = set()

    for target in search_targets:
        params = {**common_params, "location": target["location"]}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCH_URL, headers=headers, params=params)

                if resp.status_code == 429:
                    logger.warning("RapidAPI rate limit hit")
                    break
                if resp.status_code != 200:
                    logger.warning("Realtor API error", status=resp.status_code, label=target["label"], body=resp.text[:200])
                    continue

                data = resp.json()
                results = data.get("data", {}).get("results", [])
                total = data.get("data", {}).get("total", 0)

                for prop in results:
                    listing = _parse_property(prop, target["borough"])
                    if listing and listing.source_id not in seen_ids:
                        seen_ids.add(listing.source_id)
                        all_listings.append(listing)

                logger.info(f"Realtor.com [{target['label']}]: {len(results)} fetched, {total} total")

        except Exception as e:
            logger.error("Realtor API request failed", label=target["label"], error=str(e))

    return all_listings


def _zip_to_borough(zip_code: str, neighborhoods: list[str]) -> str:
    """Infer borough from zip code based on selected neighborhoods."""
    for nh in neighborhoods:
        zips = NEIGHBORHOOD_ZIP_CODES.get(nh, [])
        if zip_code in zips:
            for borough, nhs in {
                "Manhattan": ["Chelsea", "East Harlem", "East Village", "Financial District", "Flatiron",
                              "Gramercy Park", "Greenwich Village", "Harlem", "Hell's Kitchen", "Inwood",
                              "Kips Bay", "Lower East Side", "Midtown East", "Midtown West", "Murray Hill",
                              "NoHo", "Nolita", "SoHo", "Tribeca", "Upper East Side", "Upper West Side",
                              "Washington Heights", "West Village"],
                "Brooklyn": ["Bay Ridge", "Bed-Stuy", "Boerum Hill", "Brooklyn Heights", "Bushwick",
                             "Carroll Gardens", "Cobble Hill", "Crown Heights", "Downtown Brooklyn", "DUMBO",
                             "Fort Greene", "Greenpoint", "Park Slope", "Prospect Heights", "Sunset Park", "Williamsburg"],
                "Queens": ["Astoria", "Flushing", "Forest Hills", "Jackson Heights", "Long Island City", "Sunnyside"],
                "Bronx": ["Concourse", "Fordham", "Mott Haven", "Riverdale"],
                "Staten Island": ["St. George", "Tompkinsville"],
            }.items():
                if nh in nhs:
                    return borough
    return "Manhattan"


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
        postal_code = address_data.get("postal_code", "")
        address = f"{line}, {city}" if line else city

        # Determine neighborhood from zip code mapping
        neighborhood = None
        neighborhoods_data = location.get("neighborhoods")
        if neighborhoods_data and isinstance(neighborhoods_data, list):
            neighborhood = neighborhoods_data[0].get("name", "") if neighborhoods_data[0] else None

        if not neighborhood and postal_code:
            for nh, zips in NEIGHBORHOOD_ZIP_CODES.items():
                if postal_code in zips:
                    neighborhood = nh
                    break

        detected_borough = borough

        desc = prop.get("description", {})
        beds = desc.get("beds")
        baths = desc.get("baths")
        sqft = desc.get("sqft")
        prop_type = desc.get("type", "")

        url = prop.get("href", "")
        if not url:
            url = f"https://www.realtor.com/rentals/details/{property_id}"

        images = []
        primary = prop.get("primary_photo")
        if primary and isinstance(primary, dict):
            images.append(primary.get("href", ""))
        photos = prop.get("photos") or []
        for p in photos[:5]:
            if isinstance(p, dict):
                images.append(p.get("href", ""))

        broker_name = None
        advertisers = prop.get("advertisers") or []
        if advertisers:
            broker_name = advertisers[0].get("name", "")

        branding = prop.get("branding") or []
        office_name = branding[0].get("name", "") if branding else ""

        amenities = []
        details = prop.get("details") or []
        for detail in details:
            category = detail.get("category", "")
            if category in ("Appliances", "Interior Features", "Heating and Cooling", "Garage and Parking"):
                for text in detail.get("text", []):
                    amenities.append(text)

        available_date = None
        for detail in details:
            for text in detail.get("text", []):
                if "Availability Date" in text:
                    date_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
                    if date_match:
                        available_date = date_match.group()

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
