"""Route planning entry points (SPEC Section 15). Pure functions, no database.

TEMPORARY: plan_routes runs the nearest-neighbour baseline for every fleet
size. The three-stage method (cluster -> assign -> OR-Tools order) replaces
the body later with the same signature and return shape.
"""
from app.routing.baseline import baseline_nearest_neighbor
from app.routing.types import RoutingSettings, Stop

__all__ = ["plan_routes", "baseline_nearest_neighbor", "recommend_fleet_size"]


def recommend_fleet_size(alternatives: list[dict]) -> int | None:
    """SPEC 10: feasible alternative with the lowest total_cost_rs, ties -> lower
    total_km; None if none is feasible."""
    feasible = [a for a in alternatives if a["feasible"]]
    if not feasible:
        return None
    return min(feasible, key=lambda a: (a["total_cost_rs"], a["total_km"]))["fleet_size"]


def plan_routes(stops: list[Stop], fleet_sizes=(1, 2, 3), fast: bool = False,
                settings: RoutingSettings | None = None) -> dict:
    """Return {"alternatives": [...], "recommended_fleet_size": int | None}.

    TEMPORARY: `fast` is ignored; every route is labelled
    solver="temporary_nearest_neighbor".
    """
    settings = settings or RoutingSettings()
    alternatives = []
    for k in fleet_sizes:
        alt = baseline_nearest_neighbor(stops, k, settings)
        for route in alt["routes"]:
            route["solver"] = "temporary_nearest_neighbor"
        alternatives.append(alt)
    return {"alternatives": alternatives,
            "recommended_fleet_size": recommend_fleet_size(alternatives)}
