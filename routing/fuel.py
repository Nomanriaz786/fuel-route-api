"""Find fuel stations along a route and choose the cheapest refuelling plan."""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .geo import haversine_miles
from .models import FuelStation


class NoStationInRange(RuntimeError):
    """Raised when a stretch of the route has no reachable fuel station."""


@dataclass(frozen=True)
class RouteStation:
    """A fuel station and its position (miles from the start) along the route."""

    id: int
    name: str
    address: str
    city: str
    state: str
    price: float
    lat: float
    lon: float
    mile: float


@dataclass
class FuelStop:
    """A planned purchase at one station."""

    station: RouteStation
    gallons: float

    @property
    def cost(self):
        """Money spent at this stop."""
        return self.gallons * self.station.price


@lru_cache(maxsize=1)
def _station_table():
    """Load all stations into numpy arrays once per process."""
    rows = list(FuelStation.objects.values_list("id", "name", "address", "city", "state", "price", "lat", "lon"))
    lat = np.array([r[6] for r in rows])
    lon = np.array([r[7] for r in rows])
    return rows, lat, lon


def sample_route(coords, step_miles=1.0):
    """Reduce a dense route to points about every `step_miles`, with their cumulative mileage."""
    lat = np.array([c[0] for c in coords])
    lon = np.array([c[1] for c in coords])
    miles = np.concatenate([[0.0], np.cumsum(haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:]))])
    idx = np.unique(np.append(np.searchsorted(miles, np.arange(0, miles[-1], step_miles)), len(miles) - 1))
    return lat[idx], lon[idx], miles[idx]


def stations_along_route(route_lat, route_lon, route_miles, max_detour):
    """Return stations within `max_detour` miles of the route, ordered by their mile on the route."""
    rows, lat, lon = _station_table()
    if not rows:
        return []
    pad = max_detour / 60
    inside = np.flatnonzero(
        (lat >= route_lat.min() - pad) & (lat <= route_lat.max() + pad)
        & (lon >= route_lon.min() - pad) & (lon <= route_lon.max() + pad)
    )
    found = []
    for chunk in np.array_split(inside, max(1, len(inside) // 500)):
        if not len(chunk):
            continue
        dist = haversine_miles(lat[chunk, None], lon[chunk, None], route_lat[None, :], route_lon[None, :])
        nearest = dist.argmin(axis=1)
        for k, (i, j) in enumerate(zip(chunk, nearest)):
            if dist[k, j] <= max_detour:
                found.append(RouteStation(*rows[i], mile=float(route_miles[j])))
    return sorted(found, key=lambda s: s.mile)


def plan_fuel_stops(stations, total_miles, tank_range, mpg, first_fill_window):
    """
    Choose where and how much to buy so the trip costs the least.

    The truck fills up first at the cheapest station within `first_fill_window`
    miles of the start (or the first station on the route if none is that close);
    fuel used before that stop is billed at its price. From each stop: if a cheaper
    station is within range, buy just enough to reach it; otherwise fill the tank
    (or buy just enough to finish) and continue to the cheapest station in range.
    """
    stations = [s for s in stations if s.mile < total_miles]
    if not stations or stations[0].mile > tank_range:
        raise NoStationInRange("No fuel station near the start of the route")
    nearby = [s for s in stations if s.mile <= first_fill_window] or stations[:1]
    current = min(nearby, key=lambda s: (s.price, s.mile))
    stops = [FuelStop(current, current.mile / mpg)]
    fuel = 0.0

    while True:
        ahead = [s for s in stations if current.mile < s.mile <= current.mile + tank_range]
        cheaper = next((s for s in ahead if s.price < current.price), None)
        if cheaper:
            buy = max(0.0, cheaper.mile - current.mile - fuel)
            fuel += buy - (cheaper.mile - current.mile)
            next_station = cheaper
        elif total_miles - current.mile <= tank_range:
            buy = max(0.0, total_miles - current.mile - fuel)
            _add(stops, current, buy / mpg)
            return stops
        elif ahead:
            next_station = min(ahead, key=lambda s: (s.price, -s.mile))
            buy = tank_range - fuel
            fuel = tank_range - (next_station.mile - current.mile)
        else:
            raise NoStationInRange(f"No fuel station within {tank_range} miles after mile {current.mile:.0f}")
        _add(stops, current, buy / mpg)
        current = next_station


def _add(stops, station, gallons):
    """Add gallons to the stop at `station`, creating it if needed."""
    if gallons <= 1e-9:
        return
    if stops and stops[-1].station == station:
        stops[-1].gallons += gallons
    else:
        stops.append(FuelStop(station, gallons))
