import numpy as np

from motile_plugin.motile_solver import solve
from motile_plugin.solver_params import SolverParams


# capsys is a pytest fixture that captures stdout and stderr output streams
def test_solve_2d(segmentation_2d, graph_2d):
    params = SolverParams()
    params.merge_cost = None
    params.appear_cost = None
    params.disappear_cost = None
    soln_graph = solve(params, segmentation_2d)
    assert set(soln_graph.nodes) == set(graph_2d.nodes)

def test_solve_3d(segmentation_3d, graph_3d):
    params = SolverParams()
    params.merge_cost = None
    params.appear_cost = None
    params.disappear_cost = None
    soln_graph = solve(params, segmentation_3d)
    assert set(soln_graph.nodes) == set(graph_3d.nodes)
