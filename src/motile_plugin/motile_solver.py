
import logging
import time

from motile import Solver, TrackGraph
from motile.constraints import MaxChildren, MaxParents
from motile.costs import Appear, Disappear, EdgeSelection, Split
from motile_toolbox.candidate_graph import (
    EdgeAttr,
    NodeAttr,
    get_candidate_graph,
    graph_to_nx,
)
import numpy as np

from .solver_params import SolverParams

logger = logging.getLogger(__name__)

def solve(
    solver_params: SolverParams,
    segmentation: np.ndarray,
    ):
    cand_graph, _ = get_candidate_graph(
        segmentation,
        solver_params.max_edge_distance,
        iou=solver_params.iou_weight is not None,
        multihypo=False
    )
    logger.debug(f"Cand graph has {cand_graph.number_of_nodes()} nodes")
    solver = construct_solver(cand_graph, solver_params)
    start_time = time.time()
    solution = solver.solve(verbose=True)
    logger.info(f"Solution took {time.time() - start_time} seconds")

    solution_graph = solver.get_selected_subgraph(solution=solution)
    solution_nx_graph = graph_to_nx(solution_graph)

    return solution_nx_graph


def construct_solver(cand_graph, solver_params):
    solver = Solver(TrackGraph(cand_graph, frame_attribute=NodeAttr.TIME.value))
    solver.add_constraints(MaxChildren(solver_params.max_children))
    solver.add_constraints(MaxParents(solver_params.max_parents))

    if solver_params.appear_cost is not None:
        solver.add_costs(Appear(solver_params.appear_cost))
    if solver_params.disappear_cost is not None:
        solver.add_costs(Disappear(solver_params.disappear_cost))
    if solver_params.division_cost is not None:
        solver.add_costs(Split(constant=solver_params.division_cost))
    if solver_params.merge_cost is not None:
        from motile.costs import Merge
        solver.add_costs(Merge(constant=solver_params.merge_cost))

    if solver_params.distance_weight is not None:
        solver.add_costs(EdgeSelection(
            solver_params.distance_weight,
            attribute=EdgeAttr.DISTANCE.value,
            constant=solver_params.distance_offset), name="distance")
    if solver_params.iou_weight is not None:
        solver.add_costs(EdgeSelection(
            weight=solver_params.iou_weight,
            attribute=EdgeAttr.IOU.value,
            constant=solver_params.iou_offset), name="iou")
    return solver

    
