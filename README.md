# Fuel Route API

A Django API that takes a start and finish location in the USA and returns:

- the driving route (as GeoJSON, plus an interactive map page),
- the most cost-effective fuel stops for a truck with a **500-mile range**,
- the **total fuel cost** at **10 miles per gallon**.

Each request makes **one** call to an external service (the routing API).

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_data      # one-time: loads places and geocodes the fuel stations
python manage.py runserver
```

## Usage

```http
GET /api/route?start=Chicago, IL&finish=Dallas, TX
GET /map?start=Chicago, IL&finish=Dallas, TX
```

`start` and `finish` accept `"City, ST"` or `"lat,lon"`.

A ready-made Postman collection is in `postman/fuel-route-api.postman_collection.json` (set `baseUrl` if not running on port 8000).

Example response (shortened):

```json
{
  "start": {"name": "Chicago, IL", "lat": 41.83, "lon": -87.68},
  "finish": {"name": "Dallas, TX", "lat": 32.79, "lon": -96.77},
  "distance_miles": 961.5,
  "total_gallons": 96.15,
  "total_fuel_cost": 283.14,
  "fuel_stops": [
    {"name": "QUIKTRIP #7205", "address": "I-80, EXIT 161", "city": "Lansing", "state": "IL",
     "mile": 15.1, "price_per_gallon": 3.079, "gallons": 8.21, "cost": 25.27}
  ],
  "route": {"type": "LineString", "coordinates": [[-87.68, 41.83]]},
  "map_url": "http://localhost:8000/map?start=Chicago%2C+IL&finish=Dallas%2C+TX"
}
```

Errors return JSON with an `error` message: `400` for unknown locations or missing parameters, `502` if the routing service fails.

## How it works

1. **Data loading (once).** `load_data` reads the US Census places gazetteer (`data/us_places.txt`) and the fuel price list (`data/fuel_prices.csv`). The price list has no coordinates, so each station is placed at its city's coordinates. Duplicate station rows keep the lowest price.
2. **Geocoding (offline).** The start and finish are looked up in the same places table, so no external geocoding call is needed.
3. **Routing (one call).** The free [OSRM](https://project-osrm.org/) API returns the route geometry and distance.
4. **Stations along the route.** The route is sampled every mile; stations within 10 miles of it are kept, each with its mile position on the route.
5. **Fuel plan.** A greedy algorithm that gives the lowest total cost:
   - at each stop, if a cheaper station is within range, buy just enough fuel to reach it;
   - otherwise, fill the tank (or buy just enough to finish) and go to the cheapest station in range.
6. **Cost.** Gallons = miles / 10; total cost is the sum of gallons times price at each stop.

Results are cached per start and finish, so repeated requests return in milliseconds.

## Assumptions

- The truck fills up first at the cheapest station within 50 miles of the start, or at the first station on the route if none is that close. Fuel used before that stop is billed at its price, so the total covers the whole trip.
- A station counts as "on the route" if it is within 10 miles of it.
- Station positions are city-level, because the price list has no coordinates.
- The provided price list has very few stations in some areas (for example, only 16 rows in California), so some routes have a long first leg.

## Tests

```bash
python manage.py test routing
```

## Project structure

```text
config/                      Django settings and root URLs
routing/
  models.py                  Place and FuelStation
  geo.py                     distance math and offline geocoding
  osrm.py                    the single routing API call
  fuel.py                    stations along the route and the fuel plan
  trip.py                    ties the steps together and caches results
  views.py, urls.py          /api/route and /map
  management/commands/       load_data
  templates/routing/map.html Leaflet map
  tests.py
data/                        fuel prices and US places
postman/                     Postman collection with example requests
```
