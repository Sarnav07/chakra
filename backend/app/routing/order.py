"""Stage 3 - visiting order of one cluster with OR-Tools (SPEC Section 10)."""
from app.config import ORTOOLS_TIME_LIMIT_S
from app.routing.distance import distance_matrix_m
from app.routing.feasibility import order_nearest
from app.routing.types import Stop

FALLBACK_SOLVER = "fallback_nearest_neighbor"


def order_with_ortools(start_node, stops: list[Stop], end_node, detour_factor: float,
                       fast: bool) -> tuple[list[Stop], str]:
    """Order stops from start_node to end_node (single-vehicle routing on
    integer road metres). Returns (ordered stops, solver name).

    fast=False: PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH for ORTOOLS_TIME_LIMIT_S s.
    fast=True : first solution only (twin and scale lab).
    0 or 1 stop skips the solver. Any exception or no solution -> nearest-
    neighbour order with solver "fallback_nearest_neighbor".
    """
    solver = "ortools_fast" if fast else "ortools"
    if len(stops) <= 1:
        return list(stops), solver
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2

        points = [start_node, *stops, end_node]          # node 0 = start, last = end
        matrix = distance_matrix_m(points, detour_factor)
        manager = pywrapcp.RoutingIndexManager(len(points), 1, [0], [len(points) - 1])
        routing = pywrapcp.RoutingModel(manager)

        def transit(from_index, to_index):
            return matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

        routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(transit))
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        if not fast:
            params.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
            params.time_limit.seconds = ORTOOLS_TIME_LIMIT_S
        solution = routing.SolveWithParameters(params)
        if solution is None:
            return order_nearest(start_node, stops, end_node, detour_factor), FALLBACK_SOLVER

        nodes = []
        index = solution.Value(routing.NextVar(routing.Start(0)))
        while not routing.IsEnd(index):
            nodes.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        ordered = [points[node] for node in nodes]
        if sorted(s.bin_id for s in ordered) != sorted(s.bin_id for s in stops):
            raise ValueError("OR-Tools route does not visit every stop exactly once")
        return ordered, solver
    except Exception:
        return order_nearest(start_node, stops, end_node, detour_factor), FALLBACK_SOLVER
