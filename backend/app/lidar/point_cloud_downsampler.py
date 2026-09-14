"""
Point Cloud Downsampler Module

Provides configurable voxel grid downsampling (e.g., voxel_size = 0.02, 0.05, 0.10, 0.20 meters)
for point cloud data. Processing remains 100% server-side in local coordinates.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np


def voxel_grid_downsample(
    points: np.ndarray,
    voxel_size: float = 0.10,
    colors: Optional[np.ndarray] = None,
    scan_indices: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Voxel grid downsampling on 3D point cloud $[X, Y, Z]$.

    Args:
        points: NumPy array of shape (N, 3) containing local Cartesian XYZ
        voxel_size: Side length of 3D voxel cube in meters (e.g. 0.05, 0.10, 0.20)
        colors: Optional NumPy array of shape (N, 3) containing RGB [0..255]
        scan_indices: Optional NumPy array of shape (N,) containing scan IDs

    Returns:
        Tuple of (downsampled_points, downsampled_colors, downsampled_scan_indices)
    """
    if points is None or len(points) == 0:
        return np.empty((0, 3)), np.empty((0, 3)), np.empty((0,), dtype=int)

    # Compute 3D integer voxel indices for each point
    min_bound = points.min(axis=0)
    voxel_indices = np.floor((points - min_bound) / voxel_size).astype(np.int64)

    # Group points by unique voxel index key
    # Combine (vx, vy, vz) into a unique tuple/hashable identifier
    unique_voxels, return_index, inverse_indices, counts = np.unique(
        voxel_indices, axis=0, return_index=True, return_inverse=True, return_counts=True
    )

    num_voxels = len(unique_voxels)

    # Compute mean centroid per voxel
    downsampled_points = np.zeros((num_voxels, 3), dtype=np.float64)
    np.add.at(downsampled_points, inverse_indices, points)
    downsampled_points /= counts[:, np.newaxis]

    downsampled_colors = None
    if colors is not None and len(colors) == len(points):
        downsampled_colors = np.zeros((num_voxels, 3), dtype=np.float64)
        np.add.at(downsampled_colors, inverse_indices, colors)
        downsampled_colors /= counts[:, np.newaxis]
        downsampled_colors = np.clip(downsampled_colors, 0, 255).astype(np.uint8)

    downsampled_scans = None
    if scan_indices is not None and len(scan_indices) == len(points):
        # Assign scan_index from first point in each voxel
        downsampled_scans = scan_indices[return_index]

    return downsampled_points, downsampled_colors, downsampled_scans
