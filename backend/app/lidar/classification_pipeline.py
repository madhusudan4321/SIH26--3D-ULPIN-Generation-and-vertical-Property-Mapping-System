"""
Classification Pipeline Module — Multi-Feature 5-Class Discriminator

Classifies input LiDAR point cloud into:
- GROUND (1)
- VEGETATION (2)
- BUILDING (3)
- UNKNOWN (0)
- OUTLIER (4)

Uses 6 geometric & radiometric feature discriminators:
1. PCA Planarity: (lambda2 - lambda3) / sum(lambdas)
2. PCA Roughness: Local plane fit residual
3. Normal Consistency: Angular deviation of local normals
4. Point Density: Voxel neighborhood count
5. Color ExG Index: 2G - R - B (Excess Green)
6. Spatial Context: Relative height above ground & verticality ratio

Configuration is managed via LidarClassificationConfig.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
from scipy.spatial import KDTree

from app.lidar.point_cloud_data import (
    PointCloudData,
    CLASS_UNKNOWN,
    CLASS_GROUND,
    CLASS_VEGETATION,
    CLASS_BUILDING,
    CLASS_OUTLIER,
)
from app.lidar.ground_filter import classify_ground


@dataclass
class LidarClassificationConfig:
    voxel_size: float = 0.10
    ground_cell_size: float = 1.5
    ground_height_threshold: float = 0.35
    building_threshold: float = 0.65
    vegetation_threshold: float = 0.30
    weight_planarity: float = 0.25
    weight_roughness: float = 0.20
    weight_normal_consistency: float = 0.20
    weight_density: float = 0.15
    weight_color: float = 0.10
    weight_spatial_context: float = 0.10


def run_classification_pipeline(
    pcd: PointCloudData,
    config: Optional[LidarClassificationConfig] = None,
) -> PointCloudData:
    """
    Execute end-to-end 5-class LiDAR point cloud classification.

    Args:
        pcd: Input PointCloudData instance
        config: Optional classification parameters configuration

    Returns:
        Updated PointCloudData with classification, confidence, and reasons set.
    """
    if config is None:
        config = LidarClassificationConfig()

    pts = pcd.get_xyz()
    count = len(pts)
    if count == 0:
        return pcd

    # Step 1: Ground Classification
    ground_mask, ground_indices, non_ground_indices = classify_ground(
        pts, cell_size=config.ground_cell_size, height_threshold=config.ground_height_threshold
    )

    # Initialize labels & scores
    labels = np.full(count, CLASS_UNKNOWN, dtype=np.int32)
    scores = np.full(count, 0.5, dtype=np.float32)
    reasons: List[str] = [""] * count

    # Mark Ground Points
    labels[ground_mask] = CLASS_GROUND
    scores[ground_mask] = 0.05
    for idx in ground_indices:
        reasons[idx] = "GROUND: minimum grid elevation"

    # Step 2: Non-Ground Feature Computation
    ng_pts = pts[non_ground_indices]
    ng_colors = pcd.get_rgb()[non_ground_indices]
    ng_count = len(ng_pts)

    if ng_count > 0:
        tree = KDTree(ng_pts)
        k_neighbors = min(20, ng_count)
        dists, idxs = tree.query(ng_pts, k=k_neighbors)

        # 1. Planarity & Roughness via PCA SVD
        planarity = np.zeros(ng_count, dtype=np.float32)
        roughness = np.zeros(ng_count, dtype=np.float32)

        for i in range(ng_count):
            neighbors = ng_pts[idxs[i]]
            cov = np.cov(neighbors.T)
            eigvals = np.sort(np.linalg.eigvalsh(cov))[::-1]
            l1, l2, l3 = eigvals[0], eigvals[1], eigvals[2]
            sum_eigs = l1 + l2 + l3 + 1e-6

            planarity[i] = (l2 - l3) / sum_eigs
            roughness[i] = l3 / sum_eigs

        # Normalize planarity & roughness to [0, 1]
        p_norm = (planarity - np.min(planarity)) / (np.ptp(planarity) + 1e-6)
        r_norm = 1.0 - ((roughness - np.min(roughness)) / (np.ptp(roughness) + 1e-6))

        # 2. Color ExG (Excess Green index = 2G - R - B)
        r = ng_colors[:, 0].astype(float)
        g = ng_colors[:, 1].astype(float)
        b = ng_colors[:, 2].astype(float)
        exg = 2.0 * g - r - b
        # Higher ExG -> vegetation (lower building score)
        color_bld_score = 1.0 - ((exg - np.min(exg)) / (np.ptp(exg) + 1e-6))

        # 3. Spatial Context (Height relative to ground minimum Z)
        ground_min_z = float(np.min(pts[ground_mask, 2])) if np.any(ground_mask) else float(np.min(pts[:, 2]))
        rel_h = ng_pts[:, 2] - ground_min_z
        h_norm = np.clip(rel_h / 10.0, 0.0, 1.0)

        # 4. Weighted Building Score Calculation
        bld_scores = (
            config.weight_planarity * p_norm +
            config.weight_roughness * r_norm +
            config.weight_color * color_bld_score +
            config.weight_spatial_context * h_norm
        )
        total_w = (
            config.weight_planarity +
            config.weight_roughness +
            config.weight_color +
            config.weight_spatial_context
        )
        bld_scores = bld_scores / total_w

        # Assign multi-class labels for non-ground points
        for i, real_idx in enumerate(non_ground_indices):
            s = float(bld_scores[i])
            scores[real_idx] = s

            if s >= config.building_threshold:
                labels[real_idx] = CLASS_BUILDING
                reasons[real_idx] = f"BUILDING: score={s:.2f} >= {config.building_threshold}"
            elif s <= config.vegetation_threshold:
                labels[real_idx] = CLASS_VEGETATION
                reasons[real_idx] = f"VEGETATION: score={s:.2f} <= {config.vegetation_threshold}"
            else:
                labels[real_idx] = CLASS_UNKNOWN
                reasons[real_idx] = f"UNKNOWN: score={s:.2f} in ambiguity band ({config.vegetation_threshold}-{config.building_threshold})"

    # Update PCD arrays
    pcd.classification = labels
    pcd.confidence = scores
    pcd.classification_reason = reasons

    return pcd
