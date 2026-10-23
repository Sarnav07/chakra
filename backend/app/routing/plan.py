"""Route planning entry points (SPEC Section 15). Pure functions, no database.

plan_routes: stream rule -> stage 1 cluster -> stage 2 assign vehicles ->
stage 3 order (nearest neighbour for now; OR-Tools in P2-4) -> feasibility gate.
"""
from app.routing.assign import assign_vehicles
from app.routing.baseline import (END_NODE, START_NODE, baseline_nearest_neighbor,
                                  build_alternative, build_route, node_by_id,
                                  stream_vehicles)
from app.routing.cluster import cluster_stops
from app.routing.feasibility import check_alternative, enforce_shift, order_nearest
from app.routing.types import RoutingSettings, Stop

__all__ = ["plan_routes", "baseline_nearest_neighbor", "recommend_fleet_size"]

SOLVER = "cluster_nearest_neighbor"


def recommend_fleet_size(alternatives: list[dict]) -> int | None:
    """SPEC 10: feasible alternative with the lowest total_cost_rs, ties -> lower
    total_km; None if none is feasible."""
    feasible = [a for a in alternatives if a["feasible"]]
    if not feasible:
        return None
    return min(feasible, key=lambda a: (a["total_cost_rs"], a["total_km"]))["fleet_size"]


def _plan_one(stops: list[Stop], fleet_size: int, settings: RoutingSettings) -> dict:
    """One alternative for fleet size k."""
    by_stream, unassigned = stream_vehicles(stops, fleet_size, settings)
    vehicle_order = [v["vehicle_id"] for v in settings.vehicles]
    working = []
    for stream, vehicles in by_stream.items():
        stream_stops = [s for s in stops if s.stream == stream]
        capacity = min(v["capacity_l"] for v in vehicles) * settings.capacity_buffer
        clusters, left = cluster_stops(stream_stops, len(vehicles), capacity,
                                       settings.detour_factor)
        unassigned += [s.bin_id for s in left]
        start = node_by_id(settings, START_NODE)
        end = node_by_id(settings, END_NODE[stream])
        pairs = assign_vehicles(clusters, vehicles, settings.capacity_buffer)
        used = {v["vehicle_id"] for v, _ in pairs}
        for vehicle, cluster in pairs:
            working.append({"vehicle": vehicle, "stream": stream,
                            "stops": order_nearest(start, cluster, end, settings.detour_factor)})
        # idle vehicles of this stream can still receive stops in the feasibility gate
        working += [{"vehicle": v, "stream": stream, "stops": []}
                    for v in vehicles if v["vehicle_id"] not in used]
    working.sort(key=lambda r: vehicle_order.index(r["vehicle"]["vehicle_id"]))

    working, shift_unassigned = enforce_shift(working, settings)
    unassigned += shift_unassigned
    routes = [build_route(r["vehicle"], r["stream"], r["stops"], settings, SOLVER)
              for r in working if r["stops"]]
    alternative = build_alternative(stops, fleet_size, routes, unassigned, settings)
    violations = check_alternative(alternative, [s.bin_id for s in stops], settings)
    alternative["feasible"] = not violations
    alternative["manual_dispatch_required"] = bool(violations)
    return alternative


def plan_routes(stops: list[Stop], fleet_sizes=(1, 2, 3), fast: bool = False,
                settings: RoutingSettings | None = None) -> dict:
    """Return {"alternatives": [...], "recommended_fleet_size": int | None}.

    `fast` is accepted for the SPEC signature; it only matters once OR-Tools
    orders the stops (P2-4).
    """
    settings = settings or RoutingSettings()
    alternatives = [_plan_one(stops, k, settings) for k in fleet_sizes]
    return {"alternatives": alternatives,
            "recommended_fleet_size": recommend_fleet_size(alternatives)}
