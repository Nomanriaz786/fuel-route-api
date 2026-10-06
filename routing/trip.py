"""Plan a full trip: geocode, route once, pick fuel stops, and cache the result."""
import hashlib

from django.conf import settings
from django.core.cache import cache

from .fuel import plan_fuel_stops, sample_route, stations_along_route
from .geo import geocode
from .osrm import get_route


def plan_trip(start_text, finish_text):
    """Return a JSON-ready trip plan for two US locations."""
    raw = f"{start_text.strip().lower()}|{finish_text.strip().lower()}"
    key = "trip:" + hashlib.sha256(raw.encode()).hexdigest()
    cached = cache.get(key)
    if cached:
        return cached

    start_lat, start_lon, start_label = geocode(start_text)
    finish_lat, finish_lon, finish_label = geocode(finish_text)
    coords, total_miles = get_route((start_lat, start_lon), (finish_lat, finish_lon))
    route_lat, route_lon, route_miles = sample_route(coords)
    route_miles = route_miles * (total_miles / route_miles[-1])

    stations = stations_along_route(route_lat, route_lon, route_miles, settings.MAX_DETOUR_MILES)
    stops = plan_fuel_stops(
        stations,
        total_miles,
        settings.VEHICLE_RANGE_MILES,
        settings.VEHICLE_MPG,
        settings.FIRST_FILL_WINDOW_MILES,
    )

    result = {
        "start": {"name": start_label, "lat": start_lat, "lon": start_lon},
        "finish": {"name": finish_label, "lat": finish_lat, "lon": finish_lon},
        "distance_miles": round(total_miles, 1),
        "total_gallons": round(sum(s.gallons for s in stops), 2),
        "total_fuel_cost": round(sum(s.cost for s in stops), 2),
        "fuel_stops": [
            {
                "name": s.station.name,
                "address": s.station.address,
                "city": s.station.city,
                "state": s.station.state,
                "lat": s.station.lat,
                "lon": s.station.lon,
                "mile": round(s.station.mile, 1),
                "price_per_gallon": round(s.station.price, 3),
                "gallons": round(s.gallons, 2),
                "cost": round(s.cost, 2),
            }
            for s in stops
        ],
        "route": {
            "type": "LineString",
            "coordinates": [[round(float(lon), 5), round(float(lat), 5)] for lat, lon in zip(route_lat, route_lon)],
        },
    }
    cache.set(key, result)
    return result
