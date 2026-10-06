"""HTTP endpoints: the JSON route API and an HTML map of the same plan."""
from urllib.parse import urlencode

from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from .fuel import NoStationInRange
from .geo import LocationNotFound
from .osrm import RouteNotFound
from .trip import plan_trip


def _plan_or_error(request):
    """Run the planner for ?start=&finish=; return (plan, None) or (None, error response)."""
    start, finish = request.GET.get("start", ""), request.GET.get("finish", "")
    if not start or not finish:
        return None, JsonResponse({"error": "Both 'start' and 'finish' are required."}, status=400)
    try:
        return plan_trip(start, finish), None
    except (LocationNotFound, NoStationInRange) as exc:
        return None, JsonResponse({"error": str(exc)}, status=400)
    except RouteNotFound as exc:
        return None, JsonResponse({"error": str(exc)}, status=502)


def route_api(request):
    """GET /api/route?start=...&finish=... returns the route, fuel stops and total fuel cost as JSON."""
    plan, error = _plan_or_error(request)
    if error:
        return error
    query = urlencode({"start": request.GET["start"], "finish": request.GET["finish"]})
    map_url = request.build_absolute_uri(f"{reverse('route-map')}?{query}")
    return JsonResponse({**plan, "map_url": map_url})


def route_map(request):
    """GET /map?start=...&finish=... draws the same plan on an interactive map."""
    plan, error = _plan_or_error(request)
    if error:
        return error
    return render(request, "routing/map.html", {"plan": plan})
