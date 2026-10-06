"""Tests for geocoding, the fuel planner and the API endpoints."""
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from .fuel import NoStationInRange, RouteStation, plan_fuel_stops
from .geo import LocationNotFound, geocode, normalize_place
from .models import FuelStation, Place


def station(mile, price, name=None):
    """Build a route station at `mile` with `price` per gallon."""
    return RouteStation(
        id=int(mile), name=name or f"S{mile}", address="", city="", state="", price=price, lat=0, lon=0, mile=mile
    )


class NormalizePlaceTests(SimpleTestCase):
    """City names from both data sources must produce the same key."""

    def test_saint_and_suffix(self):
        self.assertEqual(normalize_place("St. Louis city"), "saint louis")
        self.assertEqual(normalize_place("East St. Louis"), "east saint louis")
        self.assertEqual(normalize_place("Big Cabin town"), "big cabin")


class FuelPlannerTests(SimpleTestCase):
    """The planner must be cheapest-first, respect range, and buy exactly the trip's fuel."""

    def plan(self, stations, total):
        return plan_fuel_stops(stations, total, tank_range=500, mpg=10, first_fill_window=50)

    def test_buys_exactly_the_fuel_needed(self):
        stops = self.plan([station(0, 3.0), station(400, 3.5), station(800, 3.2)], 1000)
        self.assertAlmostEqual(sum(s.gallons for s in stops), 100.0)

    def test_buys_just_enough_to_reach_a_cheaper_station(self):
        stops = self.plan([station(0, 4.0), station(300, 3.0)], 700)
        self.assertEqual([s.station.mile for s in stops], [0, 300])
        self.assertAlmostEqual(stops[0].gallons, 30.0)
        self.assertAlmostEqual(stops[1].gallons, 40.0)

    def test_fills_tank_at_cheap_station_and_buys_little_at_expensive_one(self):
        stops = self.plan([station(0, 3.0), station(450, 5.0), station(600, 4.0)], 900)
        self.assertAlmostEqual(stops[0].gallons, 50.0)
        self.assertAlmostEqual(stops[1].gallons, 10.0)
        self.assertAlmostEqual(sum(s.cost for s in stops), 50 * 3.0 + 10 * 5.0 + 30 * 4.0)

    def test_short_trip_has_a_single_stop(self):
        stops = self.plan([station(5, 3.0)], 120)
        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(stops[0].gallons, 12.0)

    def test_gap_longer_than_range_is_an_error(self):
        with self.assertRaises(NoStationInRange):
            self.plan([station(0, 3.0), station(600, 3.0)], 1000)


class GeocodeTests(TestCase):
    """User input is resolved offline from the places table."""

    def setUp(self):
        Place.objects.create(name="dallas", state="TX", lat=32.78, lon=-96.80)

    def test_city_state(self):
        self.assertEqual(geocode("Dallas, tx")[:2], (32.78, -96.80))

    def test_lat_lon(self):
        self.assertEqual(geocode("40.7, -74.0")[:2], (40.7, -74.0))

    def test_unknown_city(self):
        with self.assertRaises(LocationNotFound):
            geocode("Atlantis, ZZ")


class RouteApiTests(TestCase):
    """End-to-end request with the routing service mocked."""

    def setUp(self):
        cache.clear()
        Place.objects.create(name="alpha", state="TX", lat=30.0, lon=-97.0)
        Place.objects.create(name="beta", state="TX", lat=30.0, lon=-90.0)
        FuelStation.objects.create(
            opis_id=1, name="Cheap Stop", address="I-10", city="Alpha", state="TX", price=3.0, lat=30.0, lon=-96.95
        )
        FuelStation.objects.create(
            opis_id=2, name="Mid Stop", address="I-10", city="Mid", state="TX", price=3.5, lat=30.0, lon=-93.5
        )

    def test_route_returns_stops_cost_and_map(self):
        coords = [(30.0, -97.0 + i * 0.07) for i in range(101)]
        with mock.patch("routing.trip.get_route", return_value=(coords, 418.0)) as route:
            response = self.client.get("/api/route", {"start": "Alpha, TX", "finish": "Beta, TX"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        route.assert_called_once()
        self.assertAlmostEqual(data["total_gallons"], 41.8, places=1)
        self.assertEqual(data["fuel_stops"][0]["name"], "Cheap Stop")
        self.assertIn("/map?", data["map_url"])

    def test_missing_parameters(self):
        self.assertEqual(self.client.get("/api/route").status_code, 400)
