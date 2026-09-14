"""
E57 Reader Module — Read-Only Streamlined Parser

Reads E57 scan headers, scanner poses, point attributes, and scan data arrays
without loading the complete 219M point cloud into memory.
"""

from pathlib import Path
from typing import Dict, List, Any, Generator, Tuple
import pye57
import numpy as np


def read_e57_scan_headers(file_path: str) -> Dict[str, Any]:
    """
    Read metadata and scan headers for all scans in an E57 file.

    Returns:
        Structured metadata dictionary including scan count, point counts,
        global bounds, and scan pose transformations.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"E57 file not found: {file_path}")

    e57 = pye57.E57(str(path))
    scan_count = e57.scan_count

    total_points = 0
    scans_info = []

    global_x_min = float("inf")
    global_x_max = float("-inf")
    global_y_min = float("inf")
    global_y_max = float("-inf")
    global_z_min = float("inf")
    global_z_max = float("-inf")

    all_attributes = set()
    has_poses = False

    for idx in range(scan_count):
        h = e57.get_header(idx)
        n_pts = h.point_count
        total_points += n_pts

        for field in h.point_fields:
            all_attributes.add(field)

        x_min, x_max = float(h.xMinimum), float(h.xMaximum)
        y_min, y_max = float(h.yMinimum), float(h.yMaximum)
        z_min, z_max = float(h.zMinimum), float(h.zMaximum)

        global_x_min = min(global_x_min, x_min)
        global_x_max = max(global_x_max, x_max)
        global_y_min = min(global_y_min, y_min)
        global_y_max = max(global_y_max, y_max)
        global_z_min = min(global_z_min, z_min)
        global_z_max = max(global_z_max, z_max)

        trans = [float(v) for v in h.translation]
        rot = [float(v) for v in h.rotation]
        rot_mat = h.rotation_matrix.tolist() if hasattr(h, "rotation_matrix") else None

        if any(t != 0.0 for t in trans) or any(r != 0.0 for r in rot[1:]):
            has_poses = True

        scans_info.append({
            "scan_index": idx,
            "guid": getattr(h, "guid", None),
            "point_count": n_pts,
            "bounds": {
                "x_min": round(x_min, 3),
                "x_max": round(x_max, 3),
                "y_min": round(y_min, 3),
                "y_max": round(y_max, 3),
                "z_min": round(z_min, 3),
                "z_max": round(z_max, 3),
            },
            "translation_m": [round(v, 4) for v in trans],
            "rotation_quaternion": [round(v, 6) for v in rot],
            "rotation_matrix": rot_mat,
        })

    attr_list = sorted(list(all_attributes))

    return {
        "file_name": path.name,
        "file_size_gb": round(path.stat().st_size / (1024 ** 3), 3),
        "scan_count": scan_count,
        "total_points": total_points,
        "coordinate_bounds": {
            "x_min": round(global_x_min, 3),
            "x_max": round(global_x_max, 3),
            "y_min": round(global_y_min, 3),
            "y_max": round(global_y_max, 3),
            "z_min": round(global_z_min, 3),
            "z_max": round(global_z_max, 3),
        },
        "registered": has_poses,
        "scanner_positions_available": has_poses,
        "raw_attributes": attr_list,
        "scans": scans_info,
    }


def read_scan_points(
    file_path: str,
    scan_index: int,
    step: int = 1,
    apply_pose_transform: bool = True,
) -> Dict[str, np.ndarray]:
    """
    Read point data for a single scan index with strided sampling.

    Args:
        file_path: Path to E57 file
        scan_index: Index of scan (0 to scan_count - 1)
        step: Strided sampling step factor (e.g. 200 = sample every 200th point)
        apply_pose_transform: If True, applies registered pose matrix (transform=True)

    Returns:
        Dictionary of numpy arrays for cartesianX, Y, Z, intensity, colorRed, Green, Blue
    """
    path = Path(file_path)
    e57 = pye57.E57(str(path))

    # Read scan data with colors & intensity
    data = e57.read_scan(
        scan_index,
        colors=True,
        intensity=True,
        transform=apply_pose_transform,
    )

    if step > 1:
        sampled_data = {}
        for key, arr in data.items():
            if isinstance(arr, np.ndarray):
                sampled_data[key] = arr[::step]
            else:
                sampled_data[key] = arr
        return sampled_data

    return data
