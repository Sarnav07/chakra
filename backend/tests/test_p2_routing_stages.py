"""P2 routing stages 1-2 and the feasibility gate (SPEC 10; SPEC 19 T4 and T6)."""
from collections import Counter

import numpy as np
import pytest

from app.config import CAMPUS_CENTER
from app.routing.assign import assign_vehicles
from app.routing.cluster import cluster_stops
from app.routing.feasibility import check_alternative, enforce_shift
from app.routing.plan import plan_routes
from app.routing.types import RoutingSettings, Stop

SETTINGS = RoutingSettings()
CAPACITY = {v["vehicle_id"]: v["capacity_l"] * SETTINGS.capacity_buffer
            for v in SETTINGS.vehicles}


def _stop(bin_id, stream, dlat, dlon, demand_l):
    return Stop(bin_id=bin_id, name=f"Test {bin_id}", lat=CAMPUS_CENTER[0] + dlat,
                lon=CAMPUS_CENTER[1] + dlon, stream=stream, demand_l=demand_l)


# (a) 12 hand-made stops in two streams
HAND_MADE = (
    [_stop(f"G{i:02d}", "general", 0.0008 * (i % 4) - 0.002, 0.0009 * (i // 4) - 0.003,
           120.0 + 40 * i) for i in range(8)]
    + [_stop(f"F{i:02d}", "food", 0.0005 * i + 0.001, 0.0006 * i + 0.002, 60.0 + 10 * i)
       for i in range(4)])


# (b) 50 random stops around CAMPUS_CENTER (fixed seed)
def _random_stops(n=50, seed=2026):
    rng = np.random.default_rng(seed)
    stops = []
    for i in range(n):
        stream = "food" if i % 5 == 0 else "general"
        stops.append(_stop(f"R{i:02d}", stream, float(rng.uniform(-0.006, 0.006)),
                           float(rng.uniform(-0.007, 0.007)),
                           round(float(rng.uniform(20, 200)), 1)))
    return stops


RANDOM_50 = _random_stops()
CASES = {"hand_made_12": HAND_MADE, "random_50": RANDOM_50}


def _check_t4_t6(stops, alt):
    stream_of = {s.bin_id: s.stream for s in stops}
    # T4: every selected stop exactly once in a route or unassigned
    placed = Counter([b for r in alt["routes"] for b in r["ordered_bin_ids"]]
                     + alt["unassigned_bin_ids"])
    assert placed == Counter(list(stream_of))
    for r in alt["routes"]:
        # T4: capacity and shift hold
        assert r["load_l"] <= CAPACITY[r["vehicle_id"]] + 1e-6
        assert r["minutes"] <= SETTINGS.shift_min + 1e-6
        # T6: one stream per route; food ends at COMPOST, general at DEPOT
        assert {stream_of[b] for b in r["ordered_bin_ids"]} == {r["stream"]}
        assert r["start_node"] == "DEPOT"
        assert r["end_node"] == ("COMPOST" if r["stream"] == "food" else "DEPOT")
        assert r["solver"] == "ortools"
    # T4: infeasible -> the reason is listed (unassigned or another violation)
    if not alt["feasible"]:
        assert check_alternative(alt, list(stream_of), SETTINGS)


@pytest.mark.parametrize("case", CASES)
def test_t4_t6_all_fleet_sizes(case):
    stops = CASES[case]
    result = plan_routes(stops)
    assert [a["fleet_size"] for a in result["alternatives"]] == [1, 2, 3]
    for alt in result["alternatives"]:
        _check_t4_t6(stops, alt)


@pytest.mark.parametrize("case", CASES)
def test_check_alternative_empty_for_feasible(case):
    stops = CASES[case]
    feasible = [a for a in plan_routes(stops)["alternatives"] if a["feasible"]]
    assert feasible, "expected at least one feasible alternative"
    for alt in feasible:
        assert check_alternative(alt, [s.bin_id for s in stops], SETTINGS) == []


def test_k1_with_both_streams_is_infeasible():
    alt = plan_routes(HAND_MADE, fleet_sizes=(1,))["alternatives"][0]
    assert sorted(alt["unassigned_bin_ids"]) == ["F00", "F01", "F02", "F03"]
    assert alt["feasible"] is False and alt["manual_dispatch_required"] is True


def test_capacity_overload_lists_unassigned():
    heavy = [_stop(f"H{i:02d}", "general", 0.0003 * i, -0.0002 * i, 700.0) for i in range(12)]
    alt = plan_routes(heavy, fleet_sizes=(2,))["alternatives"][0]   # 8400 L > 2 x 3600 L
    assert alt["unassigned_bin_ids"]
    assert alt["feasible"] is False
    _check_t4_t6(heavy, alt)
    assert any("unassigned" in v for v in check_alternative(alt, [s.bin_id for s in heavy],
                                                            SETTINGS))


def test_deterministic():
    assert plan_routes(RANDOM_50) == plan_routes(RANDOM_50)
    assert plan_routes(HAND_MADE) == plan_routes(HAND_MADE)


def test_cluster_one_stop_per_cluster_when_enough_clusters():
    stops = HAND_MADE[:3]
    clusters, unassigned = cluster_stops(stops, 5, 3600, 1.3)
    assert sorted(len(c) for c in clusters) == [1, 1, 1] and unassigned == []


def test_cluster_capacity_and_coverage():
    general = [s for s in RANDOM_50 if s.stream == "general"]
    clusters, unassigned = cluster_stops(general, 2, 1500.0, 1.3)
    assert len(clusters) <= 2
    assert all(sum(s.demand_l for s in c) <= 1500.0 for c in clusters)
    ids = [s.bin_id for c in clusters for s in c] + [s.bin_id for s in unassigned]
    assert sorted(ids) == sorted(s.bin_id for s in general)


def test_assign_respects_capacity():
    general = [s for s in RANDOM_50 if s.stream == "general"]
    clusters, _ = cluster_stops(general, 3, 3600.0, 1.3)
    pairs = assign_vehicles(clusters, SETTINGS.vehicles)
    assert sorted(s.bin_id for _, c in pairs for s in c) == sorted(
        s.bin_id for c in clusters for s in c)
    for vehicle, c in pairs:
        assert sum(s.demand_l for s in c) <= vehicle["capacity_l"] * SETTINGS.capacity_buffer


def test_enforce_shift_moves_then_unassigns():
    tight = RoutingSettings(shift_min=15)
    long_route = [_stop(f"S{i}", "general", 0.0002 * i, 0.0002 * i, 50.0) for i in range(8)]
    routes = [{"vehicle": tight.vehicles[0], "stream": "general", "stops": long_route},
              {"vehicle": tight.vehicles[1], "stream": "general", "stops": []}]
    fixed, unassigned = enforce_shift(routes, tight)
    from app.routing.feasibility import route_metrics
    for r in fixed:
        assert route_metrics(r["vehicle"], r["stream"], r["stops"], tight)["minutes"] <= 15
    assert fixed[1]["stops"], "a stop should move to the idle vehicle"
    ids = [s.bin_id for r in fixed for s in r["stops"]] + unassigned
    assert sorted(ids) == sorted(s.bin_id for s in long_route)
    assert len(routes[0]["stops"]) == 8   # input not modified


def test_check_alternative_reports_violations():
    alt = plan_routes(HAND_MADE, fleet_sizes=(2,))["alternatives"][0]
    broken = {**alt, "unassigned_bin_ids": [alt["routes"][0]["ordered_bin_ids"][0]]}
    violations = check_alternative(broken, [s.bin_id for s in HAND_MADE], SETTINGS)
    assert any("appears 2 times" in v for v in violations)
    assert any("unassigned" in v for v in violations)
