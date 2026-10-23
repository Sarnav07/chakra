"""P2 routing basics: distances, nearest-neighbour baseline, temporary planner."""
from collections import Counter

import pytest

from app.routing.distance import distance_matrix_m, haversine_km, road_km
from app.routing.plan import baseline_nearest_neighbor, plan_routes
from app.routing.types import RoutingSettings, Stop

SETTINGS = RoutingSettings()


def _stop(bin_id, stream, dlat, dlon, demand_l=150.0):
    return Stop(bin_id=bin_id, name=f"Test {bin_id}", lat=29.8650 + dlat, lon=77.8960 + dlon,
                stream=stream, demand_l=demand_l)


GENERAL = [_stop(f"G{i}", "general", 0.0004 * i, -0.0003 * i) for i in range(1, 7)]
FOOD = [_stop("F1", "food", -0.0004, 0.0020), _stop("F2", "food", -0.0002, 0.0026)]
MIXED = GENERAL + FOOD


def _served(alt):
    return [b for r in alt["routes"] for b in r["ordered_bin_ids"]]


def test_haversine_one_degree_of_latitude():
    assert 111.1 <= haversine_km(0, 0, 1, 0) <= 111.3


def test_road_km_and_matrix():
    a, b = GENERAL[0], {"lat": GENERAL[1].lat, "lon": GENERAL[1].lon}
    assert road_km(a, b, 1.3) == pytest.approx(
        haversine_km(a.lat, a.lon, b["lat"], b["lon"]) * 1.3)
    m = distance_matrix_m([a, b], 1.3)
    assert m[0][0] == 0 and m[0][1] == m[1][0] == round(road_km(a, b, 1.3) * 1000)


@pytest.mark.parametrize("k", [1, 2, 3])
def test_every_stop_exactly_once(k):
    alt = baseline_nearest_neighbor(MIXED, k)
    placed = Counter(_served(alt) + alt["unassigned_bin_ids"])
    assert placed == Counter(s.bin_id for s in MIXED)


@pytest.mark.parametrize("k", [1, 2, 3])
def test_loads_within_effective_capacity(k):
    alt = baseline_nearest_neighbor(MIXED, k)
    for r in alt["routes"]:
        vehicle = next(v for v in SETTINGS.vehicles if v["vehicle_id"] == r["vehicle_id"])
        assert r["load_l"] <= vehicle["capacity_l"] * SETTINGS.capacity_buffer


@pytest.mark.parametrize("k", [2, 3])
def test_streams_and_end_nodes(k):
    stream_of = {s.bin_id: s.stream for s in MIXED}
    alt = baseline_nearest_neighbor(MIXED, k)
    assert alt["feasible"]
    for r in alt["routes"]:
        assert {stream_of[b] for b in r["ordered_bin_ids"]} == {r["stream"]}
        assert r["start_node"] == "DEPOT"
        assert r["end_node"] == ("COMPOST" if r["stream"] == "food" else "DEPOT")
        assert [s["seq"] for s in r["stops"]] == list(range(1, len(r["stops"]) + 1))
        assert len(r["polyline"]) == len(r["stops"]) + 2
    assert alt["routes"][-1]["vehicle_id"] == f"V{k}"   # last vehicle serves food


def test_k1_with_both_streams_leaves_food_unassigned():
    alt = baseline_nearest_neighbor(MIXED, 1)
    assert sorted(alt["unassigned_bin_ids"]) == ["F1", "F2"]
    assert alt["feasible"] is False
    assert alt["manual_dispatch_required"] is True
    assert [r["stream"] for r in alt["routes"]] == ["general"]


def test_more_demand_than_capacity_leaves_unassigned():
    heavy = [_stop(f"H{i}", "general", 0.0002 * i, 0.0002 * i, demand_l=1000.0)
             for i in range(10)]   # 10 000 L > 2 x 3600 L
    alt = baseline_nearest_neighbor(heavy, 2)
    assert alt["unassigned_bin_ids"]
    assert alt["feasible"] is False


def test_shift_limit_leaves_unassigned():
    short_shift = RoutingSettings(shift_min=10)   # 3 stops x 3 min already > 10 with driving
    alt = baseline_nearest_neighbor(GENERAL, 1, short_shift)
    assert alt["unassigned_bin_ids"]
    assert all(r["minutes"] <= 10 for r in alt["routes"])


def test_empty_stops():
    alt = baseline_nearest_neighbor([], 2)
    assert alt["feasible"] is True
    assert alt["total_km"] == 0 and alt["total_cost_rs"] == 0
    assert alt["routes"] == [] and alt["unassigned_bin_ids"] == []


def test_alternative_keys_match_spec():
    alt = baseline_nearest_neighbor(MIXED, 2)
    assert set(alt) == {"fleet_size", "feasible", "manual_dispatch_required", "total_km",
                        "completion_minutes", "total_minutes", "total_cost_rs",
                        "vehicles_used", "unassigned_bin_ids", "routes"}
    assert set(alt["routes"][0]) == {"vehicle_id", "stream", "start_node", "end_node", "stops",
                                     "ordered_bin_ids", "km", "minutes", "load_l",
                                     "est_cost_rs", "solver", "polyline"}
    assert set(alt["routes"][0]["stops"][0]) == {"seq", "bin_id", "name", "lat", "lon",
                                                 "demand_l"}
    assert alt["routes"][0]["solver"] == "nearest_neighbor"


def test_plan_routes_recommends_cheapest_feasible():
    result = plan_routes(MIXED)
    alts = result["alternatives"]
    assert [a["fleet_size"] for a in alts] == [1, 2, 3]
    assert all(r["solver"] == "temporary_nearest_neighbor" for a in alts for r in a["routes"])
    feasible = [a for a in alts if a["feasible"]]
    best = min(feasible, key=lambda a: (a["total_cost_rs"], a["total_km"]))
    assert result["recommended_fleet_size"] == best["fleet_size"]


def test_plan_routes_none_feasible():
    assert plan_routes(MIXED, fleet_sizes=(1,))["recommended_fleet_size"] is None
