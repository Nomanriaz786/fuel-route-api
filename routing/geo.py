"""Distance math and offline geocoding of user input."""
import re

import numpy as np

from .models import Place

EARTH_RADIUS_MILES = 3958.8
_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|unified government|metropolitan government"
    r"|municipality|borough|village|city|town|cdp)(\s*\(.*\))?$",
    re.IGNORECASE,
)


class LocationNotFound(ValueError):
    """Raised when an input location cannot be resolved to coordinates."""


def normalize_place(name):
    """Return a lowercase lookup key for a city name ("St. Louis" -> "saint louis")."""
    name = _SUFFIX.sub("", name.strip()).lower()
    name = re.sub(r"\bst\b\.?", "saint", name)
    name = re.sub(r"[^a-z0-9 ]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles; works on scalars and numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def geocode(text):
    """Resolve "City, ST" or "lat,lon" to (lat, lon, label) without any external call."""
    parts = [p.strip() for p in (text or "").split(",")]
    if len(parts) != 2 or not all(parts):
        raise LocationNotFound(f'Use "City, ST" or "lat,lon": got "{text}"')
    try:
        lat, lon = float(parts[0]), float(parts[1])
        return lat, lon, f"{lat:.4f},{lon:.4f}"
    except ValueError:
        pass
    place = Place.objects.filter(name=normalize_place(parts[0]), state=parts[1].upper()).first()
    if place is None:
        raise LocationNotFound(f'Unknown US location: "{text}"')
    return place.lat, place.lon, f"{parts[0].title()}, {parts[1].upper()}"
