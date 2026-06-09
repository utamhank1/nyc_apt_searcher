import re

from app.scrapers.models import RawListing

NEIGHBORHOOD_ALIASES = {
    "ues": "Upper East Side",
    "uws": "Upper West Side",
    "les": "Lower East Side",
    "fidi": "Financial District",
    "soho": "SoHo",
    "noho": "NoHo",
    "nolita": "Nolita",
    "tribeca": "Tribeca",
    "e village": "East Village",
    "w village": "West Village",
    "hells kitchen": "Hell's Kitchen",
    "clinton": "Hell's Kitchen",
    "midtown east": "Midtown East",
    "midtown west": "Midtown West",
    "murray hill": "Murray Hill",
    "gramercy": "Gramercy Park",
    "flatiron": "Flatiron",
    "chelsea": "Chelsea",
    "greenwich village": "Greenwich Village",
    "wburg": "Williamsburg",
    "w'burg": "Williamsburg",
    "bushwick": "Bushwick",
    "bed stuy": "Bed-Stuy",
    "bed-stuy": "Bed-Stuy",
    "bedford stuyvesant": "Bed-Stuy",
    "crown heights": "Crown Heights",
    "park slope": "Park Slope",
    "cobble hill": "Cobble Hill",
    "boerum hill": "Boerum Hill",
    "dumbo": "DUMBO",
    "downtown brooklyn": "Downtown Brooklyn",
    "fort greene": "Fort Greene",
    "prospect heights": "Prospect Heights",
    "brooklyn heights": "Brooklyn Heights",
    "carroll gardens": "Carroll Gardens",
    "astoria": "Astoria",
    "lic": "Long Island City",
    "long island city": "Long Island City",
    "sunnyside": "Sunnyside",
    "jackson heights": "Jackson Heights",
}

BOROUGH_FROM_NEIGHBORHOOD = {
    "Upper East Side": "Manhattan", "Upper West Side": "Manhattan",
    "East Village": "Manhattan", "West Village": "Manhattan",
    "Lower East Side": "Manhattan", "Financial District": "Manhattan",
    "SoHo": "Manhattan", "NoHo": "Manhattan", "Nolita": "Manhattan",
    "Tribeca": "Manhattan", "Hell's Kitchen": "Manhattan",
    "Midtown East": "Manhattan", "Midtown West": "Manhattan",
    "Murray Hill": "Manhattan", "Gramercy Park": "Manhattan",
    "Flatiron": "Manhattan", "Chelsea": "Manhattan",
    "Greenwich Village": "Manhattan", "Harlem": "Manhattan",
    "East Harlem": "Manhattan", "Washington Heights": "Manhattan",
    "Inwood": "Manhattan", "Kips Bay": "Manhattan",
    "Williamsburg": "Brooklyn", "Greenpoint": "Brooklyn",
    "Bushwick": "Brooklyn", "Bed-Stuy": "Brooklyn",
    "Crown Heights": "Brooklyn", "Park Slope": "Brooklyn",
    "Cobble Hill": "Brooklyn", "Boerum Hill": "Brooklyn",
    "DUMBO": "Brooklyn", "Downtown Brooklyn": "Brooklyn",
    "Fort Greene": "Brooklyn", "Prospect Heights": "Brooklyn",
    "Brooklyn Heights": "Brooklyn", "Carroll Gardens": "Brooklyn",
    "Sunset Park": "Brooklyn", "Bay Ridge": "Brooklyn",
    "Astoria": "Queens", "Long Island City": "Queens",
    "Sunnyside": "Queens", "Jackson Heights": "Queens",
    "Flushing": "Queens", "Forest Hills": "Queens",
}

AMENITY_SYNONYMS = {
    "dw": "dishwasher", "d/w": "dishwasher",
    "w/d": "washer/dryer in unit", "w/d in unit": "washer/dryer in unit",
    "laundry in unit": "washer/dryer in unit", "in-unit laundry": "washer/dryer in unit",
    "laundry in building": "laundry in building", "laundry room": "laundry in building",
    "elev": "elevator", "doorperson": "doorman",
    "ac": "air conditioning", "a/c": "air conditioning",
    "central air": "air conditioning",
    "pet friendly": "pets allowed", "cats ok": "pets allowed", "dogs ok": "pets allowed",
    "rooftop": "roof access", "roof deck": "roof access",
    "outdoor": "outdoor space", "patio": "outdoor space", "balcony": "outdoor space",
    "terrace": "outdoor space", "backyard": "outdoor space", "garden": "outdoor space",
    "fitness": "gym", "fitness center": "gym",
    "parking": "parking available", "garage": "parking available",
    "storage": "storage available",
    "concierge": "concierge",
}


def normalize_neighborhood(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().lower()
    if cleaned in NEIGHBORHOOD_ALIASES:
        return NEIGHBORHOOD_ALIASES[cleaned]
    for alias, canonical in NEIGHBORHOOD_ALIASES.items():
        if alias in cleaned:
            return canonical
    return raw.strip().title()


def infer_borough(neighborhood: str | None) -> str | None:
    if not neighborhood:
        return None
    return BOROUGH_FROM_NEIGHBORHOOD.get(neighborhood)


def normalize_amenities(raw_amenities: list[str]) -> list[str]:
    normalized = set()
    for a in raw_amenities:
        cleaned = a.strip().lower()
        if cleaned in AMENITY_SYNONYMS:
            normalized.add(AMENITY_SYNONYMS[cleaned])
        else:
            normalized.add(cleaned)
    return sorted(normalized)


def clean_price(price_str: str | None) -> int | None:
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d]", "", str(price_str))
    return int(cleaned) if cleaned else None


def normalize_listing(raw: RawListing) -> dict:
    neighborhood = normalize_neighborhood(raw.neighborhood)
    borough = raw.borough or infer_borough(neighborhood)

    return {
        "source": raw.source,
        "source_id": raw.source_id,
        "url": raw.url,
        "title": raw.title,
        "price": raw.price if isinstance(raw.price, int) else clean_price(str(raw.price)),
        "beds": raw.beds,
        "baths": raw.baths,
        "sqft": raw.sqft,
        "address": raw.address,
        "neighborhood": neighborhood,
        "borough": borough,
        "amenities": normalize_amenities(raw.amenities),
        "images": raw.images[:10],
        "broker_name": raw.broker_name,
        "broker_email": raw.broker_email,
        "broker_phone": raw.broker_phone,
        "open_house_dates": raw.open_house_dates,
        "description": raw.description[:5000] if raw.description else None,
    }
