"""Route planning entry points (SPEC Section 15). Pure functions, no database.

plan_routes: stream rule -> stage 1 cluster -> stage 2 assign vehicles ->
stage 3 OR-Tools order per cluster -> feasibility gate.
"""
import math

from app.routing.assign import assign_vehicles
from app.routing.baseline import (END_NODE, START_NODE, baseline_nearest_neighbor,
                                  build_alternative, build_route, node_by_id,
                                  stream_vehicles)
from app.routing.cluster import cluster_stops
from app.routing.feasibility import (check_alternative, enforce_shift, improve_relocate,
                                     route_metrics)
from app.routing.order import order_with_ortools
from app.routing.types import RoutingSettings, Stop

__all__ = ["plan_routes", "baseline_nearest_neighbor", "recommend_fleet_size"]


def recommend_fleet_size(alternatives: list[dict]) -> int | None:
    """SPEC 10: feasible alternative with the lowest total_cost_rs, ties -> lower
    total_km; None if none is feasible."""
    feasible = [a for a in alternatives if a["feasible"]]
    if not feasible:
        return None
    return min(feasible, key=lambda a: (a["total_cost_rs"], a["total_km"]))["fleet_size"]


def _plan_stream(stream: str, stream_stops: list[Stop], vehicles: list[dict], n_clusters: int,
                 fast: bool, settings: RoutingSettings) -> tuple[list[dict], list[str]]:
    """Stages 1-3 and the feasibility gate for one stream with n clusters."""
    default_solver = "ortools_fast" if fast else "ortools"
    capacity = min(v["capacity_l"] for v in vehicles) * settings.capacity_buffer
    clusters, left = cluster_stops(stream_stops, n_clusters, capacity, settings.detour_factor)
    start = node_by_id(settings, START_NODE)
    end = node_by_id(settings, END_NODE[stream])
    pairs = assign_vehicles(clusters, vehicles, settings.capacity_buffer)
    used = {v["vehicle_id"] for v, _ in pairs}
    working = []
    for vehicle, cluster in pairs:
        ordered, solver = order_with_ortools(start, cluster, end, settings.detour_factor, fast)
        working.append({"vehicle": vehicle, "stream": stream, "stops": ordered, "solver": solver})
    # idle vehicles of this stream can still receive stops in the feasibility gate
    working += [{"vehicle": v, "stream": stream, "stops": [], "solver": default_solver}
                for v in vehicles if v["vehicle_id"] not in used]
    working, shift_unassigned = enforce_shift(working, settings)
    working = improve_relocate(working, settings)
    for route in working:
        # re-order routes the relocate pass changed; keep whichever order is shorter
        if len(route["stops"]) > 1:
            reordered, _ = order_with_ortools(start, route["stops"], end,
                                              settings.detour_factor, True)
            if (route_metrics(route["vehicle"], stream, reordered, settings)["km"]
                    < route_metrics(route["vehicle"], stream, route["stops"], settings)["km"]):
                route["stops"] = reordered
    return working, [s.bin_id for s in left] + shift_unassigned


def _plan_stream_fewest(stream: str, stream_stops: list[Stop], vehicles: list[dict],
                        fast: bool, settings: RoutingSettings) -> tuple[list[dict], list[str]]:
    """SPEC 10 stage 1 cluster count: try n = ceil(demand / buffered capacity)
    up to this stream's vehicle count and keep the try with the fewest
    unassigned stops, then the lowest cost (fixed cost per used vehicle + km
    cost, the same objective as recommend_fleet_size), then the lowest km.
    Once every stop is served, the search stops at the first n that is not
    better (each extra vehicle adds its fixed cost)."""
    capacity = min(v["capacity_l"] for v in vehicles) * settings.capacity_buffer
    demand = sum(s.demand_l for s in stream_stops)
    lowest = min(len(vehicles), max(1, math.ceil(demand / capacity - 1e-9)))
    best = None
    for n in range(lowest, len(vehicles) + 1):
        working, unassigned = _plan_stream(stream, stream_stops, vehicles, n, fast, settings)
        metrics = [route_metrics(r["vehicle"], stream, r["stops"], settings) for r in working]
        key = (len(unassigned), sum(m["est_cost_rs"] for m in metrics),
               sum(m["km"] for m in metrics))
        if best is None or key < best[0]:
            best = (key, working, unassigned)
        elif best[0][0] == 0:
            break
    return best[1], best[2]


def _plan_one(stops: list[Stop], fleet_size: int, fast: bool,
              settings: RoutingSettings) -> dict:
    """One alternative for fleet size k."""
    by_stream, unassigned = stream_vehicles(stops, fleet_size, settings)
    vehicle_order = [v["vehicle_id"] for v in settings.vehicles]
    working = []
    for stream, vehicles in by_stream.items():
        stream_stops = [s for s in stops if s.stream == stream]
        stream_routes, stream_unassigned = _plan_stream_fewest(stream, stream_stops, vehicles,
                                                               fast, settings)
        working += stream_routes
        unassigned += stream_unassigned
    working.sort(key=lambda r: vehicle_order.index(r["vehicle"]["vehicle_id"]))

    routes = [build_route(r["vehicle"], r["stream"], r["stops"], settings, r["solver"])
              for r in working if r["stops"]]
    alternative = build_alternative(stops, fleet_size, routes, unassigned, settings)
    violations = check_alternative(alternative, [s.bin_id for s in stops], settings)
    alternative["feasible"] = not violations
    alternative["manual_dispatch_required"] = bool(violations)
    return alternative


def plan_routes(stops: list[Stop], fleet_sizes=(1, 2, 3), fast: bool = False,
                settings: RoutingSettings | None = None) -> dict:
    """Return {"alternatives": [...], "recommended_fleet_size": int | None}.

    fast=True: OR-Tools first solution only (twin, scale lab); fast=False adds
    guided local search for ORTOOLS_TIME_LIMIT_S seconds per cluster.
    """
    settings = settings or RoutingSettings()
    alternatives = [_plan_one(stops, k, fast, settings) for k in fleet_sizes]
    return {"alternatives": alternatives,
            "recommended_fleet_size": recommend_fleet_size(alternatives)}
