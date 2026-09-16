"""
Open3D Dense Point Cloud Processing & Analysis Module

Loads COLMAP MVS fused point cloud (dense/fused.ply):
1. Copies raw PLY to derived/photogrammetry_dense_raw.ply for API serving.
2. Computes metrics (count, bounds, RGB availability, density).
3. Applies Open3D voxel downsampling and statistical outlier removal.
4. Exports processed cloud to derived/photogrammetry_dense_processed.ply.

Never modifies COLMAP output files in dense/.
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import open3d as o3d
    O3D_AVAILABLE = True
except ImportError:
    O3D_AVAILABLE = False
    logger.warning("Open3D package not installed; dense point cloud processing will run in fallback mode.")


def process_dense_pointcloud(
    dense_ply_path: Path,
    derived_dir: Path,
    voxel_size: Optional[float] = 0.05,
    nb_neighbors: int = 20,
    std_ratio: float = 2.0,
) -> Dict[str, Any]:
    """
    Process dense photogrammetric PLY point cloud.

    Returns:
        dict: Point cloud statistics and output paths.
    """
    res: Dict[str, Any] = {
        "status": "NOT_FOUND",
        "raw_point_count": 0,
        "processed_point_count": 0,
        "xyz_bounds": None,
        "has_rgb": False,
        "mean_nn_distance_m": 0.0,
        "voxel_size_applied": None,
        "outliers_removed": 0,
        "raw_ply_path": None,
        "processed_ply_path": None,
    }

    if not dense_ply_path.exists():
        logger.info(f"Dense PLY path {dense_ply_path} does not exist.")
        return res

    derived_dir.mkdir(parents=True, exist_ok=True)
    raw_copy_path = derived_dir / "photogrammetry_dense_raw.ply"
    processed_copy_path = derived_dir / "photogrammetry_dense_processed.ply"

    # Always copy raw PLY to derived/
    shutil.copy2(dense_ply_path, raw_copy_path)
    res["raw_ply_path"] = str(raw_copy_path)
    res["status"] = "RAW_COPIED"

    if not O3D_AVAILABLE:
        logger.warning("Open3D not available. Raw PLY copied to derived/, skipping Open3D processing.")
        res["processed_ply_path"] = str(raw_copy_path)
        return res

    try:
        pcd = o3d.io.read_point_cloud(str(dense_ply_path))
        pts = pcd.points
        raw_count = len(pts)
        res["raw_point_count"] = raw_count

        if raw_count == 0:
            logger.warning("Loaded PLY contains 0 points.")
            return res

        # Colors check
        res["has_rgb"] = pcd.has_colors()

        # Bounding box
        min_b = pcd.get_min_bound()
        max_b = pcd.get_max_bound()
        res["xyz_bounds"] = {
            "min_x": round(float(min_b[0]), 3),
            "max_x": round(float(max_b[0]), 3),
            "min_y": round(float(min_b[1]), 3),
            "max_y": round(float(max_b[1]), 3),
            "min_z": round(float(min_b[2]), 3),
            "max_z": round(float(max_b[2]), 3),
            "extent_x": round(float(max_b[0] - min_b[0]), 3),
            "extent_y": round(float(max_b[1] - min_b[1]), 3),
            "extent_z": round(float(max_b[2] - min_b[2]), 3),
        }

        # Downsampling & Outlier removal
        current_pcd = pcd
        if voxel_size and voxel_size > 0.0:
            current_pcd = current_pcd.voxel_down_sample(voxel_size=voxel_size)
            res["voxel_size_applied"] = voxel_size

        clean_pcd, inliers = current_pcd.remove_statistical_outlier(
            nb_neighbors=nb_neighbors,
            std_ratio=std_ratio,
        )

        outliers_count = len(current_pcd.points) - len(clean_pcd.points)
        res["outliers_removed"] = outliers_count

        processed_count = len(clean_pcd.points)
        res["processed_point_count"] = processed_count

        # Compute mean NN distance for density estimation (subsample up to 5000 points)
        sample_pcd = clean_pcd
        if processed_count > 5000:
            sample_pcd = clean_pcd.random_down_sample(5000 / processed_count)

        distances = sample_pcd.compute_nearest_neighbor_distance()
        if len(distances) > 0:
            import numpy as np
            res["mean_nn_distance_m"] = round(float(np.mean(distances)), 4)

        # Save processed PLY
        o3d.io.write_point_cloud(str(processed_copy_path), clean_pcd)
        res["processed_ply_path"] = str(processed_copy_path)
        res["status"] = "COMPLETE"

        logger.info(f"Open3D processing complete: {raw_count} raw points → {processed_count} processed points ({outliers_count} outliers removed).")

    except Exception as e:
        logger.error(f"Error in Open3D point cloud processing: {e}")
        res["status"] = "ERROR"
        # Fallback copy
        shutil.copy2(dense_ply_path, processed_copy_path)
        res["processed_ply_path"] = str(processed_copy_path)

    return res
