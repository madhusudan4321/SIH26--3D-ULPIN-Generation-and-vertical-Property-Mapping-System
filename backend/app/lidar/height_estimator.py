"""
Height Estimator Module — Robust Building Height Analysis

Estimates ground_z, roof_z, and building height_m using robust statistical percentiles
from classified ground points and candidate building points (robust against outliers/vegetation).
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np


def estimate_building_height(
    candidate_points: np.ndarray,
    ground_points: Optional[np.ndarray] = None,
    ground_percentile: float = 5.0,
    roof_percentile: float = 95.0,
) -> Dict[str, Any]:
    """
    Estimate ground elevation, roof elevation, and building height.

    Does NOT use simple (max_z - min_z) to avoid corruption by outliers and vegetation.

    Args:
        candidate_points: NumPy array of shape (N, 3) containing building candidate XYZ
        ground_points: Optional NumPy array of shape (M, 3) containing ground XYZ
        ground_percentile: Percentile for ground baseline (5th percentile)
        roof_percentile: Percentile for roof baseline (95th percentile)

    Returns:
        Dict containing ground_z, roof_z, height_m, and min_z, max_z metrics.
    """
    if candidate_points is None or len(candidate_points) == 0:
        return {"ground_z": 0.0, "roof_z": 0.0, "height_m": 0.0}

    c_z = candidate_points[:, 2]

    # Compute ground elevation Z
    if ground_points is not None and len(ground_points) > 0:
        # Find ground points near candidate center
        c_center_xy = candidate_points[:, :2].mean(axis=0)
        dist_to_center = np.linalg.norm(ground_points[:, :2] - c_center_xy, axis=1)
        nearby_ground = ground_points[dist_to_center < 15.0]

        if len(nearby_ground) > 0:
            ground_z = float(np.percentile(nearby_ground[:, 2], ground_percentile))
        else:
            ground_z = float(np.percentile(ground_points[:, 2], ground_percentile))
    else:
        ground_z = float(np.percentile(c_z, ground_percentile))

    # Compute roof elevation Z using 95th percentile
    roof_z = float(np.percentile(c_z, roof_percentile))

    height_m = round(max(roof_z - ground_z, 0.5), 2)

    return {
        "ground_z": round(ground_z, 3),
        "roof_z": round(roof_z, 3),
        "height_m": height_m,
        "min_z": round(float(c_z.min()), 3),
        "max_z": round(float(c_z.max()), 3),
    }
