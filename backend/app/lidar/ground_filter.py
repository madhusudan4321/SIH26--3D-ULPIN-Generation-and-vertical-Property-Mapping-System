"""
Ground Filter Module — Terrain & Surface Classification

Implements progressive local elevation grid filtering to separate points into GROUND vs NON_GROUND.
Accounts for non-flat terrain by estimating local baseline elevation grids.
"""

from typing import Tuple, Dict, Any
import numpy as np


def classify_ground(
    points: np.ndarray,
    cell_size: float = 1.5,
    height_threshold: float = 0.35,
    percentile: float = 5.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Classify 3D points $[X, Y, Z]$ into GROUND vs NON_GROUND using progressive local elevation.

    Args:
        points: NumPy array of shape (N, 3) containing local XYZ coordinates
        cell_size: 2D spatial grid cell size in meters (e.g. 1.5m)
        height_threshold: Height tolerance above local ground baseline in meters (e.g. 0.35m)
        percentile: Elevation percentile within cell to compute ground baseline (5th percentile)

    Returns:
        Tuple of (ground_mask, ground_indices, non_ground_indices)
        ground_mask is boolean array of shape (N,)
    """
    if points is None or len(points) == 0:
        return np.array([], dtype=bool), np.array([], dtype=int), np.array([], dtype=int)

    xy = points[:, :2]
    z = points[:, 2]

    min_xy = xy.min(axis=0)
    grid_coords = np.floor((xy - min_xy) / cell_size).astype(np.int64)

    # Combine 2D grid coordinates into 1D cell index
    grid_keys = grid_coords[:, 0] * 1000000 + grid_coords[:, 1]
    unique_cells, cell_inverse = np.unique(grid_keys, return_inverse=True)

    # Compute baseline ground elevation Z_ground for each grid cell using 5th percentile
    local_ground_z = np.zeros(len(unique_cells))

    # Calculate percentile per unique cell
    for cell_idx in range(len(unique_cells)):
        cell_mask = (cell_inverse == cell_idx)
        cell_z = z[cell_mask]
        if len(cell_z) > 0:
            local_ground_z[cell_idx] = np.percentile(cell_z, percentile)
        else:
            local_ground_z[cell_idx] = z.min()

    # Map baseline local ground elevation back to every point
    point_baseline_z = local_ground_z[cell_inverse]

    # Ground points are within height_threshold of local baseline
    height_above_ground = z - point_baseline_z
    ground_mask = (height_above_ground <= height_threshold) & (height_above_ground >= -0.5)

    ground_indices = np.where(ground_mask)[0]
    non_ground_indices = np.where(~ground_mask)[0]

    return ground_mask, ground_indices, non_ground_indices
