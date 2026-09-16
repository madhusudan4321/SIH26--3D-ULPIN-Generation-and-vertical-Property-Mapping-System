"""
Vegetation Filter Module -- Multi-Criteria Building/Vegetation Point Classifier

Separates candidate building LiDAR points into:
  BUILDING, VEGETATION, UNKNOWN, OUTLIER

using six normalized feature scores combined with configurable weights.

Features:
  1. Local surface planarity (PCA eigenvalue analysis)
  2. Local surface roughness (point-to-plane distance std)
  3. Normal consistency (angular variance of local normals)
  4. Local point density (neighbor count within radius)
  5. Color/RGB analysis (green ratio -- secondary only)
  6. Spatial context (height relative to local planar surfaces)

All features are normalized to [0, 1] using robust percentile-based scaling.
Higher composite score => more building-like.

CONSTRAINTS:
  - No feature is a hard classifier by itself
  - RGB is secondary evidence only (weight <= 0.05)
  - Normal variance does NOT automatically mean vegetation (Hammam has domes/arches)
  - Ambiguous points go to UNKNOWN, not forced into BUILDING or VEGETATION
  - OUTLIER is determined by spatial isolation, not low composite score
  - All counts must sum exactly to input count
  - coordinate_system: AAM_KHAS_BAGH_LOCAL, georeferenced: false
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict


# ============================================================
# Configuration
# ============================================================

@dataclass
class VegetationFilterConfig:
    """Configurable parameters for the vegetation filter."""

    # Feature weights (must sum to 1.0)
    weight_planarity: float = 0.30
    weight_roughness: float = 0.25
    weight_normal_consistency: float = 0.20
    weight_density: float = 0.10
    weight_color: float = 0.05
    weight_spatial_context: float = 0.10

    # PCA / planarity parameters
    k_neighbors: int = 15  # neighbors for PCA and roughness computation

    # Normal estimation
    normal_search_radius: float = 0.45  # meters
    normal_max_nn: int = 30
    normal_angular_radius: float = 0.5  # radius for angular variance computation

    # Density
    density_radius: float = 0.3  # meters

    # Outlier detection
    outlier_radius: float = 0.5  # meters
    outlier_min_neighbors: int = 3  # fewer than this => OUTLIER

    # Classification thresholds
    building_threshold: float = 0.65
    vegetation_threshold: float = 0.30
    # UNKNOWN: vegetation_threshold < score < building_threshold

    # Normalization percentiles (robust against outliers)
    norm_low_pct: float = 2.0
    norm_high_pct: float = 98.0

    # RGB availability flag (set automatically)
    rgb_available: bool = True

    def validate(self):
        """Verify weight sum and threshold ordering."""
        total = (self.weight_planarity + self.weight_roughness +
                 self.weight_normal_consistency + self.weight_density +
                 self.weight_color + self.weight_spatial_context)
        assert abs(total - 1.0) < 0.001, f"Weights must sum to 1.0, got {total}"
        assert self.vegetation_threshold < self.building_threshold, \
            "vegetation_threshold must be < building_threshold"

    def get_active_weights(self) -> Dict[str, float]:
        """Return weights, redistributing color weight if RGB unavailable."""
        weights = {
            "planarity": self.weight_planarity,
            "roughness": self.weight_roughness,
            "normal_consistency": self.weight_normal_consistency,
            "density": self.weight_density,
            "color": self.weight_color,
            "spatial_context": self.weight_spatial_context,
        }
        if not self.rgb_available:
            # Redistribute color weight proportionally to other features
            color_w = weights.pop("color")
            remaining_sum = sum(weights.values())
            for k in weights:
                weights[k] += color_w * (weights[k] / remaining_sum)
            weights["color"] = 0.0
        return weights

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# Feature computation
# ============================================================

def _compute_planarity_and_roughness(
    points: np.ndarray, k: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute per-point local surface planarity and roughness using PCA.

    Planarity = (lambda2 - lambda3) / (lambda1 + 1e-10)
    Roughness = std of point-to-local-plane distances

    Returns:
        (planarity_raw, roughness_raw) each of shape (N,)
    """
    from scipy.spatial import KDTree

    n = len(points)
    planarity = np.zeros(n, dtype=np.float64)
    roughness = np.zeros(n, dtype=np.float64)

    tree = KDTree(points)
    # Query k+1 because first result is the point itself
    dists, indices = tree.query(points, k=min(k + 1, n))

    for i in range(n):
        nbr_idx = indices[i, 1:]  # skip self
        valid = nbr_idx[nbr_idx < n]
        if len(valid) < 3:
            planarity[i] = 0.0
            roughness[i] = 0.0
            continue

        nbr_pts = points[valid]
        centroid = nbr_pts.mean(axis=0)
        centered = nbr_pts - centroid

        try:
            cov = np.cov(centered.T)
            eigvals = np.sort(np.linalg.eigvalsh(cov))[::-1]
            l1, l2, l3 = eigvals[0], eigvals[1], max(eigvals[2], 0)

            planarity[i] = (l2 - l3) / (l1 + 1e-10)

            # Roughness: fit plane using smallest eigenvector (normal)
            _, eigvecs = np.linalg.eigh(cov)
            normal = eigvecs[:, 0]  # smallest eigenvalue eigenvector
            # Project query point onto plane
            query_centered = points[i] - centroid
            dist_to_plane = abs(np.dot(query_centered, normal))
            # Also compute std of all neighbors to plane
            plane_dists = np.abs(centered @ normal)
            roughness[i] = float(np.std(plane_dists))
        except Exception:
            planarity[i] = 0.0
            roughness[i] = 0.0

    return planarity, roughness


def _compute_normal_consistency(
    points: np.ndarray, normals: np.ndarray, radius: float
) -> np.ndarray:
    """
    Compute angular variance of normals within a radius.

    Lower angular variance => more consistent => more building-like.

    Returns:
        angular_variance_raw of shape (N,) in degrees
    """
    from scipy.spatial import KDTree

    n = len(points)
    angular_var = np.zeros(n, dtype=np.float64)

    tree = KDTree(points)
    neighbors_list = tree.query_ball_point(points, r=radius)

    for i in range(n):
        nbrs = neighbors_list[i]
        if len(nbrs) < 2:
            angular_var[i] = 90.0  # maximum uncertainty
            continue

        nbr_normals = normals[nbrs]
        # Mean normal direction
        mean_normal = nbr_normals.mean(axis=0)
        mean_norm = np.linalg.norm(mean_normal)
        if mean_norm < 1e-10:
            angular_var[i] = 90.0
            continue

        mean_normal /= mean_norm

        # Angular deviation from mean
        dots = np.clip(np.abs(nbr_normals @ mean_normal), 0, 1)
        angles_deg = np.degrees(np.arccos(dots))
        angular_var[i] = float(np.std(angles_deg))

    return angular_var


def _compute_density(points: np.ndarray, radius: float) -> np.ndarray:
    """Count neighbors within radius for each point."""
    from scipy.spatial import KDTree

    tree = KDTree(points)
    neighbors = tree.query_ball_point(points, r=radius)
    # Subtract 1 to exclude self
    return np.array([len(n) - 1 for n in neighbors], dtype=np.float64)


def _compute_color_score(colors: np.ndarray) -> np.ndarray:
    """
    Compute per-point color score. Higher = more building-like.

    Uses inverse green ratio: building materials (stone, plaster, brick)
    tend to have lower green dominance than vegetation.

    Returns:
        color_raw of shape (N,) in [0, 1] range.
        Higher value = less green = more building-like.
    """
    rgb_sum = colors.astype(np.float64).sum(axis=1) + 1.0
    green_ratio = colors[:, 1].astype(np.float64) / rgb_sum
    # Invert: low green ratio => high building score
    return 1.0 - green_ratio


def _compute_spatial_context(
    points: np.ndarray, planarity: np.ndarray, k: int
) -> np.ndarray:
    """
    Spatial context score: points near highly-planar neighbors get higher scores.

    This captures the idea that building surfaces have planar spatial context
    while isolated vegetation tips do not.

    Returns:
        spatial_context_raw of shape (N,)
    """
    from scipy.spatial import KDTree

    n = len(points)
    context = np.zeros(n, dtype=np.float64)

    tree = KDTree(points)
    dists, indices = tree.query(points, k=min(k + 1, n))

    for i in range(n):
        nbr_idx = indices[i, 1:]
        valid = nbr_idx[nbr_idx < n]
        if len(valid) == 0:
            context[i] = 0.0
            continue
        # Mean planarity of neighbors
        context[i] = float(np.mean(planarity[valid]))

    return context


# ============================================================
# Normalization
# ============================================================

def _percentile_normalize(
    values: np.ndarray, low_pct: float, high_pct: float, invert: bool = False
) -> np.ndarray:
    """
    Robust percentile-based normalization to [0, 1].

    Args:
        values: raw feature values
        low_pct: lower percentile (e.g., 2.0)
        high_pct: upper percentile (e.g., 98.0)
        invert: if True, higher raw value => lower normalized score

    Returns:
        normalized values clipped to [0, 1]
    """
    p_low = np.percentile(values, low_pct)
    p_high = np.percentile(values, high_pct)

    if abs(p_high - p_low) < 1e-10:
        # No variation -- return 0.5 for all
        return np.full_like(values, 0.5, dtype=np.float64)

    normalized = (values - p_low) / (p_high - p_low)
    normalized = np.clip(normalized, 0.0, 1.0)

    if invert:
        normalized = 1.0 - normalized

    return normalized


def _compute_feature_stats(values: np.ndarray) -> Dict[str, float]:
    """Compute distribution statistics for a feature."""
    return {
        "min": round(float(np.min(values)), 6),
        "p05": round(float(np.percentile(values, 5)), 6),
        "median": round(float(np.median(values)), 6),
        "p95": round(float(np.percentile(values, 95)), 6),
        "max": round(float(np.max(values)), 6),
        "mean": round(float(np.mean(values)), 6),
        "std": round(float(np.std(values)), 6),
    }


def _compute_class_feature_stats(
    raw_features: Dict[str, np.ndarray],
    norm_features: Dict[str, np.ndarray],
    labels: np.ndarray,
    class_name: str,
    class_id: int,
) -> Dict[str, Any]:
    """Compute feature stats for a specific class."""
    mask = labels == class_id
    count = int(np.sum(mask))
    if count == 0:
        return {"count": 0, "note": "no points in this class"}

    stats = {"count": count}
    for feat_name in raw_features:
        raw_vals = raw_features[feat_name][mask]
        norm_vals = norm_features[feat_name][mask]
        stats[f"{feat_name}_raw"] = _compute_feature_stats(raw_vals)
        stats[f"{feat_name}_norm"] = _compute_feature_stats(norm_vals)
    return stats


# ============================================================
# Main classifier
# ============================================================

# Class ID constants
CLASS_BUILDING = 0
CLASS_VEGETATION = 1
CLASS_UNKNOWN = 2
CLASS_OUTLIER = 3

CLASS_NAMES = {
    CLASS_BUILDING: "BUILDING",
    CLASS_VEGETATION: "VEGETATION",
    CLASS_UNKNOWN: "UNKNOWN",
    CLASS_OUTLIER: "OUTLIER",
}


def classify_building_vegetation(
    points: np.ndarray,
    colors: Optional[np.ndarray] = None,
    config: Optional[VegetationFilterConfig] = None,
) -> Dict[str, Any]:
    """
    Multi-criteria building/vegetation point classification.

    Args:
        points: (N, 3) XYZ array in local coordinates
        colors: (N, 3) RGB uint8 array, or None if unavailable
        config: VegetationFilterConfig, or None for defaults

    Returns:
        Dict containing:
          - labels: (N,) int array of class IDs
          - scores: (N,) float array of composite scores
          - raw_features: dict of (N,) arrays for each raw feature
          - norm_features: dict of (N,) arrays for each normalized feature
          - contributions: dict of (N,) arrays for weighted contribution of each feature
          - config: the config used
          - feature_stats: distribution statistics
          - class_counts: per-class counts
          - class_stats: per-class feature distributions
    """
    if config is None:
        config = VegetationFilterConfig()

    n = len(points)
    assert n > 0, "No points to classify"

    # Check RGB availability
    if colors is None or len(colors) == 0:
        config.rgb_available = False
    else:
        zero_rgb = np.sum(np.all(colors == 0, axis=1))
        unique_rgb = len(np.unique(colors, axis=0))
        # If >80% are zero or <10 unique colors, RGB is unreliable
        if zero_rgb > n * 0.8 or unique_rgb < 10:
            config.rgb_available = False

    config.validate()
    active_weights = config.get_active_weights()

    print(f"  Points: {n}")
    print(f"  RGB available: {config.rgb_available}")
    print(f"  Active weights: {active_weights}")

    # ── Step 1: Compute raw features ──────────────────────────

    print("  Computing planarity and roughness...")
    planarity_raw, roughness_raw = _compute_planarity_and_roughness(
        points, k=config.k_neighbors
    )

    print("  Estimating normals...")
    import open3d as o3d
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=config.normal_search_radius, max_nn=config.normal_max_nn
        )
    )
    normals = np.asarray(pcd.normals)

    print("  Computing normal consistency...")
    angular_var_raw = _compute_normal_consistency(
        points, normals, radius=config.normal_angular_radius
    )

    print("  Computing density...")
    density_raw = _compute_density(points, radius=config.density_radius)

    print("  Computing color score...")
    if config.rgb_available:
        color_raw = _compute_color_score(colors)
    else:
        color_raw = np.full(n, 0.5, dtype=np.float64)

    print("  Computing spatial context...")
    spatial_raw = _compute_spatial_context(points, planarity_raw, k=config.k_neighbors)

    raw_features = {
        "planarity": planarity_raw,
        "roughness": roughness_raw,
        "normal_consistency": angular_var_raw,
        "density": density_raw,
        "color": color_raw,
        "spatial_context": spatial_raw,
    }

    # ── Step 2: Normalize to [0, 1] ──────────────────────────

    print("  Normalizing features...")
    lp, hp = config.norm_low_pct, config.norm_high_pct

    planarity_norm = _percentile_normalize(planarity_raw, lp, hp, invert=False)
    roughness_norm = _percentile_normalize(roughness_raw, lp, hp, invert=True)
    angular_norm = _percentile_normalize(angular_var_raw, lp, hp, invert=True)
    density_norm = _percentile_normalize(density_raw, lp, hp, invert=False)
    color_norm = _percentile_normalize(color_raw, lp, hp, invert=False)
    spatial_norm = _percentile_normalize(spatial_raw, lp, hp, invert=False)

    norm_features = {
        "planarity": planarity_norm,
        "roughness": roughness_norm,
        "normal_consistency": angular_norm,
        "density": density_norm,
        "color": color_norm,
        "spatial_context": spatial_norm,
    }

    # ── Step 3: Weighted composite score ──────────────────────

    print("  Computing composite scores...")
    w = active_weights
    contributions = {}
    composite = np.zeros(n, dtype=np.float64)

    for feat_name, norm_vals in norm_features.items():
        weight = w.get(feat_name, 0.0)
        contrib = norm_vals * weight
        contributions[feat_name] = contrib
        composite += contrib

    # ── Step 4: Detect outliers by spatial isolation ──────────

    print("  Detecting outliers...")
    from scipy.spatial import KDTree
    tree = KDTree(points)
    outlier_neighbors = tree.query_ball_point(points, r=config.outlier_radius)
    neighbor_counts = np.array([len(nb) - 1 for nb in outlier_neighbors], dtype=int)
    is_outlier = neighbor_counts < config.outlier_min_neighbors

    # ── Step 5: Classify ──────────────────────────────────────

    print("  Classifying points...")
    labels = np.full(n, CLASS_UNKNOWN, dtype=np.int32)

    # Outliers first (spatial isolation overrides score)
    labels[is_outlier] = CLASS_OUTLIER

    # Then building/vegetation/unknown by score (non-outliers only)
    non_outlier = ~is_outlier
    labels[non_outlier & (composite >= config.building_threshold)] = CLASS_BUILDING
    labels[non_outlier & (composite <= config.vegetation_threshold)] = CLASS_VEGETATION
    # Remaining non-outliers stay UNKNOWN

    # ── Step 6: Validate counts ──────────────────────────────

    counts = {}
    for cid, cname in CLASS_NAMES.items():
        counts[cname] = int(np.sum(labels == cid))

    total_classified = sum(counts.values())
    assert total_classified == n, \
        f"Classification count mismatch: {total_classified} != {n}"

    pcts = {}
    for cname, cnt in counts.items():
        pcts[cname] = round(cnt / n * 100, 2)

    pct_sum = sum(pcts.values())
    assert abs(pct_sum - 100.0) < 0.2, \
        f"Percentage sum error: {pct_sum} (expected ~100.0)"

    print(f"\n  Classification results:")
    for cname in CLASS_NAMES.values():
        print(f"    {cname:12s}: {counts[cname]:>6d} ({pcts[cname]:>6.2f}%)")
    print(f"    {'TOTAL':12s}: {total_classified:>6d}")

    # ── Step 7: Feature statistics ───────────────────────────

    print("  Computing feature statistics...")
    global_stats = {}
    for feat_name in raw_features:
        global_stats[feat_name] = {
            "raw": _compute_feature_stats(raw_features[feat_name]),
            "normalized": _compute_feature_stats(norm_features[feat_name]),
        }

    class_stats = {}
    for cid, cname in CLASS_NAMES.items():
        class_stats[cname] = _compute_class_feature_stats(
            raw_features, norm_features, labels, cname, cid
        )

    # ── Step 8: Normalization documentation ──────────────────

    normalization_doc = {
        "method": "percentile_based_clipped",
        "low_percentile": config.norm_low_pct,
        "high_percentile": config.norm_high_pct,
        "description": (
            "Each feature is normalized to [0,1] using robust percentile clipping. "
            f"Values below P{config.norm_low_pct} map to 0, above P{config.norm_high_pct} map to 1. "
            "This prevents extreme outliers from dominating the scale."
        ),
        "semantic_direction": {
            "planarity": "higher raw -> higher normalized (more building-like)",
            "roughness": "INVERTED: higher raw -> lower normalized (less building-like)",
            "normal_consistency": "INVERTED: higher angular variance -> lower normalized",
            "density": "higher raw -> higher normalized (more building-like)",
            "color": "higher raw (less green) -> higher normalized (more building-like)",
            "spatial_context": "higher raw -> higher normalized (more building-like)",
        },
    }

    # Compute actual normalization boundaries used
    norm_boundaries = {}
    for feat_name, raw_vals in raw_features.items():
        p_lo = float(np.percentile(raw_vals, config.norm_low_pct))
        p_hi = float(np.percentile(raw_vals, config.norm_high_pct))
        norm_boundaries[feat_name] = {
            f"p{config.norm_low_pct}": round(p_lo, 6),
            f"p{config.norm_high_pct}": round(p_hi, 6),
        }
    normalization_doc["boundaries_used"] = norm_boundaries

    # ── Return ────────────────────────────────────────────────

    return {
        "labels": labels,
        "scores": composite,
        "raw_features": raw_features,
        "norm_features": norm_features,
        "contributions": contributions,
        "neighbor_counts": neighbor_counts,
        "normals": normals,
        "config": config.to_dict(),
        "active_weights": active_weights,
        "normalization": normalization_doc,
        "class_counts": counts,
        "class_percentages": pcts,
        "feature_stats_global": global_stats,
        "feature_stats_per_class": class_stats,
    }
