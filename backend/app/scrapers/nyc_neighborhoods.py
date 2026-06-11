"""NYC neighborhood boundary boxes for reverse geocoding.
Each neighborhood is defined by a (min_lat, max_lat, min_lng, max_lng) bounding box."""

NEIGHBORHOOD_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    # Manhattan (min_lat, max_lat, min_lng, max_lng)
    "Financial District": (40.700, 40.714, -74.018, -74.000),
    "Tribeca": (40.714, 40.724, -74.012, -74.000),
    "SoHo": (40.720, 40.728, -74.005, -73.995),
    "NoHo": (40.724, 40.732, -73.998, -73.990),
    "Nolita": (40.720, 40.727, -73.998, -73.990),
    "Lower East Side": (40.712, 40.724, -73.998, -73.975),
    "East Village": (40.722, 40.734, -73.998, -73.975),
    "West Village": (40.728, 40.740, -74.010, -73.998),
    "Greenwich Village": (40.727, 40.738, -74.005, -73.993),
    "Chelsea": (40.738, 40.752, -74.008, -73.990),
    "Flatiron": (40.738, 40.746, -73.993, -73.982),
    "Gramercy Park": (40.733, 40.742, -73.990, -73.978),
    "Kips Bay": (40.738, 40.748, -73.984, -73.972),
    "Murray Hill": (40.745, 40.755, -73.984, -73.972),
    "Midtown East": (40.750, 40.760, -73.978, -73.965),
    "Midtown West": (40.750, 40.766, -73.996, -73.982),
    "Hell's Kitchen": (40.755, 40.772, -73.999, -73.984),
    "Upper East Side": (40.762, 40.785, -73.973, -73.950),
    "Upper West Side": (40.775, 40.802, -73.990, -73.965),
    "Harlem": (40.800, 40.824, -73.960, -73.934),
    "East Harlem": (40.790, 40.812, -73.950, -73.930),
    "Washington Heights": (40.835, 40.860, -73.948, -73.925),
    "Inwood": (40.860, 40.878, -73.930, -73.908),
    # Brooklyn
    "DUMBO": (40.700, 40.706, -73.993, -73.980),
    "Brooklyn Heights": (40.690, 40.700, -73.998, -73.985),
    "Downtown Brooklyn": (40.686, 40.696, -73.990, -73.976),
    "Boerum Hill": (40.680, 40.690, -73.990, -73.975),
    "Cobble Hill": (40.683, 40.692, -73.998, -73.988),
    "Carroll Gardens": (40.676, 40.686, -74.000, -73.988),
    "Fort Greene": (40.686, 40.696, -73.980, -73.968),
    "Park Slope": (40.666, 40.686, -73.990, -73.972),
    "Prospect Heights": (40.674, 40.684, -73.972, -73.960),
    "Crown Heights": (40.662, 40.680, -73.964, -73.930),
    "Williamsburg": (40.706, 40.724, -73.970, -73.940),
    "Greenpoint": (40.724, 40.740, -73.965, -73.940),
    "Bushwick": (40.690, 40.710, -73.930, -73.900),
    "Bed-Stuy": (40.676, 40.696, -73.960, -73.926),
    "Sunset Park": (40.638, 40.660, -74.020, -73.990),
    "Bay Ridge": (40.618, 40.640, -74.040, -74.010),
    # Queens
    "Astoria": (40.760, 40.780, -73.930, -73.900),
    "Long Island City": (40.738, 40.760, -73.960, -73.930),
    "Sunnyside": (40.738, 40.750, -73.930, -73.910),
    "Jackson Heights": (40.746, 40.758, -73.900, -73.870),
    "Flushing": (40.755, 40.775, -73.840, -73.810),
    "Forest Hills": (40.714, 40.730, -73.856, -73.835),
    # Bronx
    "Mott Haven": (40.808, 40.824, -73.926, -73.905),
    "Concourse": (40.822, 40.840, -73.930, -73.910),
    "Fordham": (40.856, 40.868, -73.910, -73.890),
    "Riverdale": (40.878, 40.910, -73.920, -73.895),
    # Staten Island
    "St. George": (40.638, 40.648, -74.080, -74.068),
    "Tompkinsville": (40.632, 40.642, -74.082, -74.070),
}


def get_neighborhood_from_coords(lat: float, lng: float) -> str | None:
    """Return the neighborhood name for given coordinates, or None if not in any known boundary."""
    if not lat or not lng:
        return None

    for name, (min_lat, max_lat, min_lng, max_lng) in NEIGHBORHOOD_BOUNDS.items():
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return name

    return None
