"""Stage 2 - give clusters to vehicles, then one refinement pass (SPEC Section 10)."""
from app.config import CAPACITY_BUFFER
from app.routing.cluster import centroid
from app.routing.distance import haversine_km
from app.routing.types import Stop


def _km(stop: Stop, point: dict) -> float:
    # straight-line km is enough here: only distances are compared
    return haversine_km(stop.lat, stop.lon, point["lat"], point["lon"])


def assign_vehicles(clusters: list[list[Stop]], vehicles: list[dict],
                    capacity_buffer: float = CAPACITY_BUFFER) -> list[tuple[dict, list[Stop]]]:
    """Sort clusters by load (desc, ties by smallest bin_id) and give them to
    vehicles in order. Then one pass over all stops in bin_id order: move a
    stop to another cluster if that cluster's centroid (computed once, before
    the pass) is nearer than its own and the receiving vehicle still has
    effective capacity (capacity_l x capacity_buffer).
    Returns [(vehicle, stops)], one pair per non-empty input cluster.
    """
    ordered = sorted((list(c) for c in clusters if c),
                     key=lambda c: (-sum(s.demand_l for s in c), min(s.bin_id for s in c)))
    if len(ordered) > len(vehicles):
        raise ValueError(f"{len(ordered)} clusters but only {len(vehicles)} vehicles")
    pairs = list(zip(vehicles, ordered))

    capacity = [v["capacity_l"] * capacity_buffer for v, _ in pairs]
    loads = [sum(s.demand_l for s in c) for _, c in pairs]
    centroids = [centroid(c) for _, c in pairs]
    home = {s.bin_id: i for i, (_, c) in enumerate(pairs) for s in c}
    all_stops = sorted((s for _, c in pairs for s in c), key=lambda s: s.bin_id)

    for stop in all_stops:
        i = home[stop.bin_id]
        options = sorted((_km(stop, centroids[j]), j) for j in range(len(pairs))
                         if j != i and loads[j] + stop.demand_l <= capacity[j])
        if options and options[0][0] < _km(stop, centroids[i]):
            j = options[0][1]
            pairs[i][1].remove(stop)
            pairs[j][1].append(stop)
            loads[i] -= stop.demand_l
            loads[j] += stop.demand_l
            home[stop.bin_id] = j
    return pairs
