"""Database models: US places for geocoding and fuel stations with prices."""
from django.db import models


class Place(models.Model):
    """A US city or town from the Census gazetteer, keyed by normalized name and state."""

    name = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    lat = models.FloatField()
    lon = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "state"], name="unique_place")]


class FuelStation(models.Model):
    """A truck stop from the provided price list, located by its city."""

    opis_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    price = models.FloatField()
    lat = models.FloatField()
    lon = models.FloatField()
