"""Stage 1 - capacity-aware clustering of one stream's stops (SPEC Section 10).

Deterministic: no randomness, ties broken by bin_id (then cluster index).
"""
import math

from app.routing.distance import road_km
from app.routing.types import Stop

MAX_ITERATIONS = 10


def centroid(stops: list[Stop]) -> dict:
    """Demand-weighted mean lat/lon (plain mean if total demand is 0)."""
    total = sum(s.demand_l for s in stops)
    if total <= 0:
        return {"lat": sum(s.lat for s in stops) / len(stops),
                "lon": sum(s.lon for s in stops) / len(stops)}
    return {"lat": sum(s.lat * s.demand_l for s in stops) / total,
            "lon": sum(s.lon * s.demand_l for s in stops) / total}


def _seeds(stops: list[Stop], n_clusters: int, detour_factor: float) -> list[Stop]:
    """First seed = highest-demand stop; next seed = stop maximising
    (distance to nearest existing seed) x demand."""
    seeds = [min(stops, key=lambda s: (-s.demand_l, s.bin_id))]
    while len(seeds) < n_clusters:
        seed_ids = {s.bin_id for s in seeds}
        rest = [s for s in stops if s.bin_id not in seed_ids]
        seeds.append(min(rest, key=lambda s: (
            -min(road_km(s, x, detour_factor) for x in seeds) * s.demand_l, s.bin_id)))
    return seeds


def _assign(stops, centroids, capacity_l, detour_factor) -> dict[str, int | None]:
    """One pass: order stops by (distance to nearest centroid / demand) ascending,
    put each into the nearest centroid whose cluster still has capacity."""
    def key(s):
        nearest = min(road_km(s, c, detour_factor) for c in centroids)
        return (nearest / s.demand_l if s.demand_l > 0 else math.inf, s.bin_id)

    loads = [0.0] * len(centroids)
    assignment = {}
    for s in sorted(stops, key=key):
        options = sorted((road_km(s, c, detour_factor), i) for i, c in enumerate(centroids)
                         if loads[i] + s.demand_l <= capacity_l)
        if options:
            i = options[0][1]
            loads[i] += s.demand_l
            assignment[s.bin_id] = i
        else:
            assignment[s.bin_id] = None
    return assignment


def cluster_stops(stops: list[Stop], n_clusters: int, capacity_l: float,
                  detour_factor: float) -> tuple[list[list[Stop]], list[Stop]]:
    """Split stops into at most n_clusters clusters of load <= capacity_l.

    capacity_l is the effective capacity of one vehicle (capacity x buffer).
    Returns (non-empty clusters, stops that fit nowhere). Stops inside a
    cluster are in bin_id order.
    """
    stops = sorted(stops, key=lambda s: s.bin_id)
    if not stops:
        return [], []
    if n_clusters < 1:
        return [], stops
    if n_clusters >= len(stops):
        return ([[s] for s in stops if s.demand_l <= capacity_l],
                [s for s in stops if s.demand_l > capacity_l])

    centroids = [{"lat": s.lat, "lon": s.lon} for s in _seeds(stops, n_clusters, detour_factor)]
    assignment = None
    for _ in range(MAX_ITERATIONS):
        new_assignment = _assign(stops, centroids, capacity_l, detour_factor)
        if new_assignment == assignment:
            break
        assignment = new_assignment
        for i in range(n_clusters):
            members = [s for s in stops if assignment[s.bin_id] == i]
            if members:   # an empty cluster keeps its previous centroid
                centroids[i] = centroid(members)

    clusters = [[s for s in stops if assignment[s.bin_id] == i] for i in range(n_clusters)]
    return ([c for c in clusters if c],
            [s for s in stops if assignment[s.bin_id] is None])
