"""Single-call routing through the free OSRM API."""
import requests
from django.conf import settings

METERS_PER_MILE = 1609.344


class RouteNotFound(RuntimeError):
    """Raised when the routing service cannot return a route."""


def get_route(start, finish):
    """Return (coordinates as [(lat, lon), ...], distance in miles) for a driving route."""
    (lat1, lon1), (lat2, lon2) = start, finish
    url = f"{settings.OSRM_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    try:
        response = requests.get(url, params={"overview": "full", "geometries": "geojson"}, timeout=20)
        response.raise_for_status()
        route = response.json()["routes"][0]
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise RouteNotFound("Routing service could not find a route") from exc
    coords = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
    return coords, route["distance"] / METERS_PER_MILE
