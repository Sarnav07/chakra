"""Nearest-neighbour baseline (SPEC Section 10 "Baseline") and shared route builders.

build_route / build_alternative / stream_vehicles are also used by plan.py,
so every alternative has the exact keys of SPEC 14 "alternatives[]".
"""
from app.routing.distance import road_km
from app.routing.types import RoutingSettings, Stop

START_NODE = "DEPOT"
END_NODE = {"general": "DEPOT", "food": "COMPOST"}


def node_by_id(settings: RoutingSettings, node_id: str) -> dict:
    return next(n for n in settings.nodes if n["node_id"] == node_id)


def route_minutes(km: float, n_stops: int, settings: RoutingSettings) -> float:
    """Driving minutes plus service minutes per stop."""
    return km / settings.speed_kmph * 60 + settings.service_min_per_bin * n_stops


def stream_vehicles(stops: list[Stop], fleet_size: int,
                    settings: RoutingSettings) -> tuple[dict[str, list[dict]], list[str]]:
    """SPEC 10 stream rule -> ({stream: vehicles}, bin_ids left unassigned).

    Both streams and k >= 2: the last vehicle serves food, the others general.
    Only one stream: all k vehicles serve it. Both streams and k == 1: the
    vehicle serves general and every food stop is unassigned.
    """
    vehicles = settings.vehicles_for(fleet_size)
    has_general = any(s.stream == "general" for s in stops)
    has_food = any(s.stream == "food" for s in stops)
    if has_general and has_food:
        if fleet_size == 1:
            return {"general": vehicles}, [s.bin_id for s in stops if s.stream == "food"]
        return {"general": vehicles[:-1], "food": vehicles[-1:]}, []
    if has_food:
        return {"food": vehicles}, []
    if has_general:
        return {"general": vehicles}, []
    return {}, []


def build_route(vehicle: dict, stream: str, ordered_stops: list[Stop],
                settings: RoutingSettings, solver: str) -> dict:
    """One route dict (SPEC 14 routes[]) for stops visited in the given order."""
    start = node_by_id(settings, START_NODE)
    end = node_by_id(settings, END_NODE[stream])
    path = [start, *ordered_stops, end]
    km = sum(road_km(a, b, settings.detour_factor) for a, b in zip(path, path[1:]))
    return {
        "vehicle_id": vehicle["vehicle_id"],
        "stream": stream,
        "start_node": start["node_id"],
        "end_node": end["node_id"],
        "stops": [{"seq": i, "bin_id": s.bin_id, "name": s.name, "lat": s.lat, "lon": s.lon,
                   "demand_l": s.demand_l} for i, s in enumerate(ordered_stops, start=1)],
        "ordered_bin_ids": [s.bin_id for s in ordered_stops],
        "km": km,
        "minutes": route_minutes(km, len(ordered_stops), settings),
        "load_l": sum(s.demand_l for s in ordered_stops),
        "est_cost_rs": vehicle["fixed_cost_rs"] + km * vehicle["cost_per_km_rs"],
        "solver": solver,
        "polyline": ([[start["lat"], start["lon"]]]
                     + [[s.lat, s.lon] for s in ordered_stops]
                     + [[end["lat"], end["lon"]]]),
    }


def build_alternative(stops: list[Stop], fleet_size: int, routes: list[dict],
                      unassigned_bin_ids: list[str], settings: RoutingSettings) -> dict:
    """One alternative dict (SPEC 14 alternatives[]) with the SPEC 10 feasibility test."""
    routes = [r for r in routes if r["stops"]]
    capacity = {v["vehicle_id"]: v["capacity_l"] * settings.capacity_buffer
                for v in settings.vehicles}
    placed = [b for r in routes for b in r["ordered_bin_ids"]] + list(unassigned_bin_ids)
    feasible = (sorted(placed) == sorted(s.bin_id for s in stops)
                and not unassigned_bin_ids
                and all(r["load_l"] <= capacity[r["vehicle_id"]]
                        and r["minutes"] <= settings.shift_min for r in routes))
    return {
        "fleet_size": fleet_size,
        "feasible": feasible,
        "manual_dispatch_required": not feasible,
        "total_km": sum(r["km"] for r in routes),
        "completion_minutes": max((r["minutes"] for r in routes), default=0.0),
        "total_minutes": sum(r["minutes"] for r in routes),
        # = non-empty routes x fixed_cost_rs + total km x cost_per_km_rs
        "total_cost_rs": sum(r["est_cost_rs"] for r in routes),
        "vehicles_used": len(routes),
        "unassigned_bin_ids": list(unassigned_bin_ids),
        "routes": routes,
    }


def baseline_nearest_neighbor(stops: list[Stop], fleet_size: int,
                              settings: RoutingSettings | None = None) -> dict:
    """Nearest neighbour without clustering: from the start node, repeatedly go
    to the nearest unvisited stop of the stream that still fits capacity and
    shift (including the drive to the end node), then go to the end node;
    next vehicle. Stops no vehicle can take are unassigned."""
    settings = settings or RoutingSettings()
    by_stream, unassigned = stream_vehicles(stops, fleet_size, settings)
    routes = []
    for stream, vehicles in by_stream.items():
        left = [s for s in stops if s.stream == stream]
        end = node_by_id(settings, END_NODE[stream])
        for vehicle in vehicles:
            capacity = vehicle["capacity_l"] * settings.capacity_buffer
            here = node_by_id(settings, START_NODE)
            ordered, load, km = [], 0.0, 0.0
            while True:
                fitting = [
                    s for s in left
                    if load + s.demand_l <= capacity
                    and route_minutes(km + road_km(here, s, settings.detour_factor)
                                      + road_km(s, end, settings.detour_factor),
                                      len(ordered) + 1, settings) <= settings.shift_min]
                if not fitting:
                    break
                nxt = min(fitting, key=lambda s: road_km(here, s, settings.detour_factor))
                km += road_km(here, nxt, settings.detour_factor)
                load += nxt.demand_l
                ordered.append(nxt)
                left.remove(nxt)
                here = nxt
            if ordered:
                routes.append(build_route(vehicle, stream, ordered, settings, "nearest_neighbor"))
        unassigned += [s.bin_id for s in left]
    return build_alternative(stops, fleet_size, routes, unassigned, settings)
