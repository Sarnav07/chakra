"""Distances (SPEC Section 10): haversine x detour factor = road km."""
import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Straight-line (great-circle) distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _lat_lon(point):
    """(lat, lon) of a dict or of an object with lat/lon attributes."""
    if isinstance(point, dict):
        return point["lat"], point["lon"]
    return point.lat, point.lon


def road_km(a, b, detour_factor) -> float:
    """Road km between two points = haversine km x detour_factor."""
    return haversine_km(*_lat_lon(a), *_lat_lon(b)) * detour_factor


def distance_matrix_m(points, detour_factor) -> list[list[int]]:
    """Integer road metres between all pairs of points (for OR-Tools)."""
    return [[round(road_km(a, b, detour_factor) * 1000) for b in points] for a in points]
