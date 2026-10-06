"""App configuration for the routing app."""
from django.apps import AppConfig


class RoutingConfig(AppConfig):
    """Fuel route planning app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "routing"
