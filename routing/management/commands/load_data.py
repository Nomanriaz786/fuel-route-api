"""Load US places and fuel stations (with coordinates) into the database."""
import csv

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from routing.geo import normalize_place
from routing.models import FuelStation, Place


class Command(BaseCommand):
    """Import the Census gazetteer and geocode each fuel station by its city and state."""

    help = "Load data/us_places.txt and data/fuel_prices.csv into the database."

    @transaction.atomic
    def handle(self, *args, **options):
        """Replace all places and stations with fresh data from the CSV files."""
        Place.objects.all().delete()
        FuelStation.objects.all().delete()

        places = {}
        with open(settings.DATA_DIR / "us_places.txt", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="|"):
                key = (normalize_place(row["NAME"]), row["USPS"])
                places.setdefault(key, (float(row["INTPTLAT"]), float(row["INTPTLONG"].strip())))
        Place.objects.bulk_create(
            Place(name=name, state=state, lat=lat, lon=lon) for (name, state), (lat, lon) in places.items()
        )

        cheapest = {}
        with open(settings.DATA_DIR / "fuel_prices.csv", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                station_id = int(row["OPIS Truckstop ID"])
                if station_id not in cheapest or float(row["Retail Price"]) < float(cheapest[station_id]["Retail Price"]):
                    cheapest[station_id] = row

        stations, skipped = [], 0
        for station_id, row in cheapest.items():
            location = places.get((normalize_place(row["City"]), row["State"].strip()))
            if location is None:
                skipped += 1
                continue
            stations.append(
                FuelStation(
                    opis_id=station_id,
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=row["City"].strip(),
                    state=row["State"].strip(),
                    price=float(row["Retail Price"]),
                    lat=location[0],
                    lon=location[1],
                )
            )
        FuelStation.objects.bulk_create(stations)
        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(places)} places and {len(stations)} stations "
                f"({skipped} skipped because their city was not found, mostly Canadian stops)."
            )
        )
