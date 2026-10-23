"""P2 stage 3: OR-Tools ordering (SPEC 10) and its fallback."""
import numpy as np
import pytest
from ortools.constraint_solver import pywrapcp

from app.config import CAMPUS_CENTER, NODES
from app.routing.distance import road_km
from app.routing.feasibility import order_nearest
from app.routing.order import FALLBACK_SOLVER, order_with_ortools
from app.routing.plan import plan_routes
from app.routing.types import RoutingSettings, Stop

SETTINGS = RoutingSettings()
DF = SETTINGS.detour_factor
DEPOT = next(n for n in NODES if n["node_id"] == "DEPOT")
COMPOST = next(n for n in NODES if n["node_id"] == "COMPOST")


def _stop(bin_id, stream, dlat, dlon, demand_l=100.0):
    return Stop(bin_id=bin_id, name=f"Test {bin_id}", lat=CAMPUS_CENTER[0] + dlat,
                lon=CAMPUS_CENTER[1] + dlon, stream=stream, demand_l=demand_l)


EIGHT = [_stop(f"E{i}", "general", 0.0007 * ((i * 3) % 8) - 0.003, 0.0006 * i - 0.002)
         for i in range(8)]


def _random_stops(n=12, seed=0):
    rng = np.random.default_rng(seed)
    return [_stop(f"R{i:02d}", "general", float(rng.uniform(-0.006, 0.006)),
                  float(rng.uniform(-0.007, 0.007))) for i in range(n)]


def _route_km(start, ordered, end):
    path = [start, *ordered, end]
    return sum(road_km(a, b, DF) for a, b in zip(path, path[1:]))


@pytest.mark.parametrize("stops", [[], EIGHT[:1], EIGHT], ids=["0", "1", "8"])
def test_every_stop_once_and_no_nodes(stops):
    ordered, solver = order_with_ortools(DEPOT, stops, DEPOT, DF, fast=False)
    assert sorted(s.bin_id for s in ordered) == sorted(s.bin_id for s in stops)
    assert all(isinstance(s, Stop) for s in ordered)          # start/end nodes not returned
    assert solver == "ortools"


@pytest.mark.parametrize("fast, name", [(True, "ortools_fast"), (False, "ortools")])
def test_fast_and_full_both_valid(fast, name):
    ordered, solver = order_with_ortools(DEPOT, EIGHT, COMPOST, DF, fast=fast)
    assert solver == name
    assert sorted(s.bin_id for s in ordered) == sorted(s.bin_id for s in EIGHT)


def test_food_route_ends_at_compost_general_at_depot():
    stops = EIGHT[:5] + [_stop("F1", "food", -0.0004, 0.0020), _stop("F2", "food", 0.0001, 0.0025)]
    alt = plan_routes(stops, fleet_sizes=(2,))["alternatives"][0]
    assert alt["feasible"]
    ends = {r["stream"]: r["end_node"] for r in alt["routes"]}
    assert ends == {"general": "DEPOT", "food": "COMPOST"}
    assert all(r["solver"] == "ortools" for r in alt["routes"])


def test_ortools_not_longer_than_nearest_neighbour():
    stops = _random_stops()
    ortools_order, solver = order_with_ortools(DEPOT, stops, DEPOT, DF, fast=False)
    nn_order = order_nearest(DEPOT, stops, DEPOT, DF)
    ortools_km = _route_km(DEPOT, ortools_order, DEPOT)
    nn_km = _route_km(DEPOT, nn_order, DEPOT)
    print(f"\n12 random stops (seed 0): ortools km = {ortools_km:.3f}, "
          f"nearest-neighbour km = {nn_km:.3f}")
    assert solver == "ortools"
    # OR-Tools optimises integer metres: allow 0.5 m rounding per arc
    assert ortools_km <= nn_km + 0.0005 * (len(stops) + 1)


def test_fallback_when_ortools_raises(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("simulated OR-Tools failure")
    monkeypatch.setattr(pywrapcp, "RoutingIndexManager", broken)
    ordered, solver = order_with_ortools(DEPOT, EIGHT, DEPOT, DF, fast=False)
    assert solver == FALLBACK_SOLVER
    assert sorted(s.bin_id for s in ordered) == sorted(s.bin_id for s in EIGHT)
    assert ordered == order_nearest(DEPOT, EIGHT, DEPOT, DF)


def test_fallback_when_no_solution(monkeypatch):
    class NoSolutionModel:
        def __init__(self, manager):
            pass

        def RegisterTransitCallback(self, callback):
            return 0

        def SetArcCostEvaluatorOfAllVehicles(self, index):
            pass

        def SolveWithParameters(self, params):
            return None
    monkeypatch.setattr(pywrapcp, "RoutingModel", NoSolutionModel)
    ordered, solver = order_with_ortools(DEPOT, EIGHT, DEPOT, DF, fast=True)
    assert solver == FALLBACK_SOLVER
    assert sorted(s.bin_id for s in ordered) == sorted(s.bin_id for s in EIGHT)


def test_plan_routes_output_keys_unchanged():
    stops = EIGHT + [_stop("F1", "food", -0.0004, 0.0020)]
    result = plan_routes(stops, fast=True)
    assert set(result) == {"alternatives", "recommended_fleet_size"}
    alt = next(a for a in result["alternatives"] if a["fleet_size"] == 2)
    assert set(alt) == {"fleet_size", "feasible", "manual_dispatch_required", "total_km",
                        "completion_minutes", "total_minutes", "total_cost_rs",
                        "vehicles_used", "unassigned_bin_ids", "routes"}
    assert set(alt["routes"][0]) == {"vehicle_id", "stream", "start_node", "end_node", "stops",
                                     "ordered_bin_ids", "km", "minutes", "load_l",
                                     "est_cost_rs", "solver", "polyline"}
    assert set(alt["routes"][0]["stops"][0]) == {"seq", "bin_id", "name", "lat", "lon",
                                                 "demand_l"}
    assert all(r["solver"] == "ortools_fast" for a in result["alternatives"]
               for r in a["routes"])
