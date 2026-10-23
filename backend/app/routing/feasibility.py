"""Stage-3 ordering helper, route metrics and the feasibility gate (SPEC Section 10).

Working routes here are dicts {"vehicle": dict, "stream": str, "stops": [Stop]}
with stops in visiting order; plan.py turns them into SPEC 14 route dicts.
"""
from collections import Counter

from app.routing.baseline import END_NODE, START_NODE, node_by_id, route_minutes
from app.routing.distance import road_km
from app.routing.types import RoutingSettings, Stop

TOLERANCE = 1e-6   # float slack when re-checking sums


def _path_km(start, stops, end, detour_factor) -> float:
    path = [start, *stops, end]
    return sum(road_km(a, b, detour_factor) for a, b in zip(path, path[1:]))


def _ends(stream: str, settings: RoutingSettings) -> tuple[dict, dict]:
    return node_by_id(settings, START_NODE), node_by_id(settings, END_NODE[stream])


def order_nearest(start, stops: list[Stop], end, detour_factor: float) -> list[Stop]:
    """Nearest-neighbour visiting order from start (ties by bin_id).

    end is not used by the greedy order; it is kept so the OR-Tools order
    (P2-4) can replace this with the same call shape.
    """
    here, left, ordered = start, list(stops), []
    while left:
        nxt = min(left, key=lambda s: (road_km(here, s, detour_factor), s.bin_id))
        ordered.append(nxt)
        left.remove(nxt)
        here = nxt
    return ordered


def route_metrics(vehicle: dict, stream: str, ordered_stops: list[Stop],
                  settings: RoutingSettings) -> dict:
    """km, minutes, load_l, est_cost_rs (= fixed_cost_rs + km x cost_per_km_rs)
    of one route. An empty route is not driven: all zeros."""
    if not ordered_stops:
        return {"km": 0.0, "minutes": 0.0, "load_l": 0.0, "est_cost_rs": 0.0}
    start, end = _ends(stream, settings)
    km = _path_km(start, ordered_stops, end, settings.detour_factor)
    return {"km": km,
            "minutes": route_minutes(km, len(ordered_stops), settings),
            "load_l": sum(s.demand_l for s in ordered_stops),
            "est_cost_rs": vehicle["fixed_cost_rs"] + km * vehicle["cost_per_km_rs"]}


def _best_insertion(routes, source, stop, settings):
    """Cheapest (added km) feasible insertion of stop into another same-stream
    route -> (route, position) or None."""
    best = None
    for index, target in enumerate(routes):
        if target is source or target["stream"] != source["stream"]:
            continue
        capacity = target["vehicle"]["capacity_l"] * settings.capacity_buffer
        if sum(s.demand_l for s in target["stops"]) + stop.demand_l > capacity:
            continue
        start, end = _ends(target["stream"], settings)
        before = _path_km(start, target["stops"], end, settings.detour_factor) if target["stops"] else 0.0
        for pos in range(len(target["stops"]) + 1):
            trial = target["stops"][:pos] + [stop] + target["stops"][pos:]
            if route_metrics(target["vehicle"], target["stream"], trial,
                             settings)["minutes"] > settings.shift_min:
                continue
            added = _path_km(start, trial, end, settings.detour_factor) - before
            if best is None or (added, index, pos) < best[0]:
                best = ((added, index, pos), target, pos)
    return None if best is None else (best[1], best[2])


def enforce_shift(routes: list[dict], settings: RoutingSettings) -> tuple[list[dict], list[str]]:
    """Feasibility gate: while a route exceeds shift_min, take its stop with the
    largest removal saving (km saved by skipping it; ties by bin_id) and insert
    it, at the cheapest position, into another same-stream route that keeps
    capacity and time; if none can take it, unassign it.
    Returns (routes, unassigned bin_ids). Input routes are not modified.
    """
    routes = [{**r, "stops": list(r["stops"])} for r in routes]
    unassigned = []
    for route in routes:
        start, end = _ends(route["stream"], settings)
        while route["stops"] and route_metrics(route["vehicle"], route["stream"], route["stops"],
                                               settings)["minutes"] > settings.shift_min:
            full_km = _path_km(start, route["stops"], end, settings.detour_factor)

            def saving(s):
                rest = [x for x in route["stops"] if x is not s]
                return full_km - (_path_km(start, rest, end, settings.detour_factor) if rest else 0.0)

            stop = min(route["stops"], key=lambda s: (-saving(s), s.bin_id))
            route["stops"].remove(stop)
            target = _best_insertion(routes, route, stop, settings)
            if target is None:
                unassigned.append(stop.bin_id)
            else:
                target_route, pos = target
                target_route["stops"].insert(pos, stop)
    return routes, unassigned


def check_alternative(alternative: dict, selected_bin_ids: list[str],
                      settings: RoutingSettings) -> list[str]:
    """SPEC 10 feasibility rules -> list of violations (empty list = feasible)."""
    violations = []
    placed = Counter([b for r in alternative["routes"] for b in r["ordered_bin_ids"]]
                     + list(alternative["unassigned_bin_ids"]))
    selected = set(selected_bin_ids)
    for bin_id in sorted(selected):
        if placed[bin_id] != 1:
            violations.append(f"{bin_id}: appears {placed[bin_id]} times (must be exactly once)")
    for bin_id in sorted(set(placed) - selected):
        violations.append(f"{bin_id}: is not a selected stop")
    if alternative["unassigned_bin_ids"]:
        violations.append("unassigned stops: " + ", ".join(alternative["unassigned_bin_ids"]))

    capacity = {v["vehicle_id"]: v["capacity_l"] * settings.capacity_buffer
                for v in settings.vehicles}
    for vehicle_id, n in Counter(r["vehicle_id"] for r in alternative["routes"]).items():
        if n > 1:
            violations.append(f"{vehicle_id}: has {n} routes (one route per vehicle)")
    for r in alternative["routes"]:
        vid = r["vehicle_id"]
        if r["load_l"] > capacity[vid] + TOLERANCE:
            violations.append(f"{vid}: load {r['load_l']:.1f} L exceeds {capacity[vid]:.1f} L")
        if r["minutes"] > settings.shift_min + TOLERANCE:
            violations.append(f"{vid}: {r['minutes']:.1f} min exceeds shift {settings.shift_min} min")
        if r["start_node"] != START_NODE or r["end_node"] != END_NODE[r["stream"]]:
            violations.append(f"{vid}: {r['stream']} route must run {START_NODE} -> "
                              f"{END_NODE[r['stream']]}, got {r['start_node']} -> {r['end_node']}")
    return violations
