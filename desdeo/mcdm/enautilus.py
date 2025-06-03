"""Functions related to the E-NAUTILUS method are defined here.

Reference of the method:

Ruiz, A. B., Sindhya, K., Miettinen, K., Ruiz, F., & Luque, M. (2015).
E-NAUTILUS: A decision support system for complex multiobjective optimization
problems based on the NAUTILUS method. European Journal of Operational Research,
246(1), 218-231.

Variables:
- N_I: number of iterations to be carried out.
- N_S: number of points to investigate at each iteration.
- h: current iteration number.
- it_h: the number of iterations left at each iteration (including h)
- z_h: the selecte point by the DM at iteration h.
- P_h: the subset of reachable solutions at iteration h which can be reached
    from the previous iteration (h-1) without impairing any of the objective
    function values.
"""

import numpy as np
from pydantic import BaseModel, Field
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist

from desdeo.problem import (
    Constraint,
    ConstraintTypeEnum,
    Problem,
    ScalarizationFunction,
    get_nadir_dict,
    numpy_array_to_objective_dict,
    objective_dict_to_numpy_array,
)
from desdeo.tools.generics import BaseSolver, SolverResults
from desdeo.tools.scalarization import (
    add_asf_diff,
    add_asf_nondiff,
    add_epsilon_constraints,
)
from desdeo.tools.utils import guess_best_solver


def prune_by_average_linkage(non_dominated_points: np.ndarray, k: int):
    """Prune a set of non-dominated points using average linkage clustering (Morse, 1980).

    This is used to calculate the representative solutions in E-NAUTILUS.

    Args:
        non_dominated_points (np.ndarray): an array of non-dominated points in objective space.
        k (int): Number of representative points to retain.

    Returns:
        np.ndarray: an array of representative points.
    """
    if len(non_dominated_points) <= k:
        # no need to prune
        return non_dominated_points

    # Compute pairwise distances
    distances = pdist(non_dominated_points, metric="euclidean")

    # Hierarchical clustering using average linkage
    z = linkage(distances, method="average")

    # Cut tree to form k clusters
    cluster_labels = fcluster(z, k, criterion="maxclust")

    # For each cluster, choose the point closest to the centroid
    representatives = []
    for cluster_id in range(1, k + 1):
        cluster_points = non_dominated_points[cluster_labels == cluster_id]
        centroid = cluster_points.mean(axis=0)
        closest_idx = np.argmin(np.linalg.norm(cluster_points - centroid, axis=1))
        representatives.append(cluster_points[closest_idx])

    return np.array(representatives)


def calculate_intermediate_points(
    z_previous: np.ndarray, zs_representatives: np.ndarray, iterations_left: int
) -> np.ndarray:
    """Calculates the intermediate points to be shown to the decision maker at each iteration.

    The number of returned points depends on how many `zs_representative points` are supplied.

    Args:
        z_previous (np.ndarray): the point selected by the decision maker in the previous iteration.
        zs_representatives (np.ndarray): the representative solutions at the current iteration.
        iterations_left (int): the number of iterations left (including the current one).

    Returns:
        np.ndarray: an array of intermediate points.
    """
    return ((iterations_left - 1) / iterations_left) * z_previous + (1 / iterations_left) * zs_representatives


def calculate_reachable_subset(
    non_dominated_points: np.ndarray, lower_bounds: np.ndarray, z_preferred: np.ndarray
) -> np.ndarray:
    """Calculates the reachable subset on a non-dominated set from a selected intermediate point.

    Args:
        non_dominated_points (np.ndarray): the original set of non-dominated points.
        lower_bounds (np.ndarray): the lower bounds of the reachable subset of non-dominates points.
        z_preferred (np.ndarray): the selected intermediate point subject to the reachable subset is calculated.

    Returns:
        np.ndarray: the reachable subset of non-dominated points.
    """
    return np.array([z for z in non_dominated_points if np.all(lower_bounds <= z) and np.all(z <= z_preferred)])
