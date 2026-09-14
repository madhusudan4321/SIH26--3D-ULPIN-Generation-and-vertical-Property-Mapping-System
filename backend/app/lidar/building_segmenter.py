"""
Building Segmenter Module — Spatial Clustering & Structural Analysis

Segments non-ground point cloud into spatial clusters/building candidates and calculates
geometric metrics (dimensions, density, verticality, planarity, building confidence score).
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np


def segment_building_candidates(
    non_ground_points: np.ndarray,
    ground_points: Optional[np.ndarray] = None,
    cluster_tolerance: float = 1.2,
    min_cluster_points: int = 150,
) -> List[Dict[str, Any]]:
    """
    Segment non-ground points into building candidate clusters.

    Calculates per-candidate geometric properties:
    - point_count
    - width_m, length_m, height_m (extents)
    - density
    - planar_score, verticality_score
    - building_score (0.0 to 1.0)

    Args:
        non_ground_points: NumPy array of shape (N, 3) containing non-ground XYZ
        ground_points: Optional NumPy array of shape (M, 3) containing ground XYZ
        cluster_tolerance: Spatial Euclidean distance threshold in meters (1.2m)
        min_cluster_points: Minimum points required for a valid candidate cluster (150)

    Returns:
        List of candidate dicts ordered by building_score descending.
    """
    if non_ground_points is None or len(non_ground_points) < min_cluster_points:
        return []

    # Use DBSCAN or scipy KD-tree clustering
    try:
        from sklearn.cluster import DBSCAN
        db = DBSCAN(eps=cluster_tolerance, min_samples=20, n_jobs=-1)
        labels = db.fit_predict(non_ground_points)
    except ImportError:
        # Fallback 2D grid clustering if sklearn unavailable
        xy = non_ground_points[:, :2]
        min_xy = xy.min(axis=0)
        grid_idx = np.floor((xy - min_xy) / cluster_tolerance).astype(np.int64)
        labels = grid_idx[:, 0] * 10000 + grid_idx[:, 1]

    unique_labels = set(labels)
    if -1 in unique_labels:
        unique_labels.remove(-1)  # Remove noise cluster

    candidates = []
    candidate_id = 1

    for label in unique_labels:
        cluster_indices = np.where(labels == label)[0]
        if len(cluster_indices) < min_cluster_points:
            continue

        c_pts = non_ground_points[cluster_indices]
        pt_count = len(c_pts)

        x_min, x_max = float(c_pts[:, 0].min()), float(c_pts[:, 0].max())
        y_min, y_max = float(c_pts[:, 1].min()), float(c_pts[:, 1].max())
        z_min, z_max = float(c_pts[:, 2].min()), float(c_pts[:, 2].max())

        dx = x_max - x_min
        dy = y_max - y_min
        dz = z_max - z_min

        # Dimensions: width is min horizontal, length is max horizontal
        width_m = round(min(dx, dy), 2)
        length_m = round(max(dx, dy), 2)
        height_m = round(dz, 2)

        # Ignore tiny or ultra-flat objects (e.g. bushes < 1.0m height or < 3.0m width/length)
        if height_m < 1.0 or length_m < 3.0:
            continue

        # Compute Bounding Box Volume & Density
        volume_m3 = dx * dy * dz
        density = round(pt_count / max(volume_m3, 0.1), 2)

        # Compute Eigenvalue Planarity & Verticality via PCA SVD
        cov = np.cov(c_pts[:, :3].T)
        eigvals = np.sort(np.linalg.eigvalsh(cov))[::-1]
        lambda1, lambda2, lambda3 = eigvals[0], eigvals[1], eigvals[2]
        sum_eigs = lambda1 + lambda2 + lambda3 + 1e-6

        # Planarity: (lambda2 - lambda3) / lambda1 (high for walls & roof planes)
        planarity = round(float((lambda2 - lambda3) / sum_eigs), 3)

        # Verticality: ratio of points forming steep wall faces vs roof
        z_range = dz + 1e-3
        wall_mask = (c_pts[:, 2] < z_min + 0.7 * z_range)
        verticality = round(float(np.sum(wall_mask) / pt_count), 3)

        # Calculate composite Building Score (0.00 to 1.00)
        # Buildings have substantial volume, height > 2.0m, footprint > 15m², high planarity
        footprint_approx_area = dx * dy
        score = 0.0

        if height_m >= 2.5: score += 0.25
        elif height_m >= 1.5: score += 0.15

        if footprint_approx_area >= 50.0: score += 0.30
        elif footprint_approx_area >= 20.0: score += 0.20
        elif footprint_approx_area >= 10.0: score += 0.10

        if pt_count >= 1000: score += 0.25
        elif pt_count >= 400: score += 0.15

        if planarity >= 0.15: score += 0.20

        building_score = round(min(score, 1.0), 2)

        candidates.append({
            "candidate_id": candidate_id,
            "point_count": pt_count,
            "indices": cluster_indices.tolist(),
            "width_m": width_m,
            "length_m": length_m,
            "height_m": height_m,
            "bbox": {
                "x_min": round(x_min, 3), "x_max": round(x_max, 3),
                "y_min": round(y_min, 3), "y_max": round(y_max, 3),
                "z_min": round(z_min, 3), "z_max": round(z_max, 3),
            },
            "density": density,
            "planarity_score": planarity,
            "verticality_score": verticality,
            "building_score": building_score,
            "centroid": [
                round(float((x_min + x_max) / 2), 3),
                round(float((y_min + y_max) / 2), 3),
                round(float((z_min + z_max) / 2), 3),
            ],
        })

        candidate_id += 1

    # Sort candidates by building_score descending
    candidates.sort(key=lambda c: (c["building_score"], c["point_count"]), reverse=True)
    return candidates
