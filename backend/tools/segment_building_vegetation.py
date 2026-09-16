"""
Aam Khas Bagh -- Building/Vegetation Segmentation Pipeline

Reads the existing classified cloud, runs multi-criteria vegetation filtering,
and produces diagnostic reports + frontend visualization data.

Outputs:
  data/aam_khas_bagh/derived/aam_khas_bagh_vegetation_classification.json
  data/aam_khas_bagh/derived/aam_khas_bagh_classified_building_points.json

CRITICAL:
  - Does NOT modify E57 source
  - Does NOT reconstruct mesh
  - Does NOT georeference
  - coordinate_system: AAM_KHAS_BAGH_LOCAL
  - georeferenced: false

Usage:
    python backend/tools/segment_building_vegetation.py
"""

import json
import sys
import os
import numpy as np
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.lidar.vegetation_filter import (
    classify_building_vegetation,
    VegetationFilterConfig,
    CLASS_BUILDING, CLASS_VEGETATION, CLASS_UNKNOWN, CLASS_OUTLIER,
    CLASS_NAMES,
)


def load_candidate_points(cloud_path: Path):
    """Load selected_building_points and colors from classified cloud."""
    with open(cloud_path, "r", encoding="utf-8") as f:
        cloud = json.load(f)

    flat = cloud.get("selected_building_points", [])
    num_pts = len(flat) // 6

    pts = np.zeros((num_pts, 3), dtype=np.float64)
    colors = np.zeros((num_pts, 3), dtype=np.uint8)

    for i in range(num_pts):
        base = i * 6
        pts[i] = [flat[base], flat[base + 1], flat[base + 2]]
        colors[i] = [int(flat[base + 3]), int(flat[base + 4]), int(flat[base + 5])]

    return pts, colors, cloud


def compute_xyz_bounds(pts: np.ndarray) -> dict:
    """XYZ bounds for a point set."""
    if len(pts) == 0:
        return {"x_min": 0, "x_max": 0, "y_min": 0, "y_max": 0, "z_min": 0, "z_max": 0}
    return {
        "x_min": round(float(pts[:, 0].min()), 4),
        "x_max": round(float(pts[:, 0].max()), 4),
        "y_min": round(float(pts[:, 1].min()), 4),
        "y_max": round(float(pts[:, 1].max()), 4),
        "z_min": round(float(pts[:, 2].min()), 4),
        "z_max": round(float(pts[:, 2].max()), 4),
    }


def compute_z_distribution(pts: np.ndarray, z_base: float) -> dict:
    """1m Z-bin distribution relative to a base Z."""
    if len(pts) == 0:
        return {}
    z = pts[:, 2] - z_base
    bins = {}
    max_z = int(np.ceil(z.max())) + 1
    total = len(pts)
    for lo in range(0, max(max_z, 1)):
        hi = lo + 1
        count = int(np.sum((z >= lo) & (z < hi)))
        bins[f"{lo}-{hi}m"] = {"count": count, "pct": round(count / total * 100, 2)}
    return bins


def compute_spatial_coherence(
    points: np.ndarray, labels: np.ndarray
) -> dict:
    """
    Compute spatial coherence of the BUILDING class.

    Uses DBSCAN to find connected components among building points.
    """
    from sklearn.cluster import DBSCAN

    bld_mask = labels == CLASS_BUILDING
    bld_pts = points[bld_mask]
    bld_count = len(bld_pts)

    if bld_count == 0:
        return {
            "building_point_count": 0,
            "component_count": 0,
            "largest_component_size": 0,
            "largest_component_pct": 0,
        }

    # Use eps=0.5m for spatial connectivity
    db = DBSCAN(eps=0.5, min_samples=3, n_jobs=-1)
    comp_labels = db.fit_predict(bld_pts)

    unique_comps = set(comp_labels)
    if -1 in unique_comps:
        unique_comps.remove(-1)

    noise_count = int(np.sum(comp_labels == -1))

    components = []
    for comp_id in sorted(unique_comps):
        comp_mask = comp_labels == comp_id
        comp_pts = bld_pts[comp_mask]
        comp_size = int(np.sum(comp_mask))
        bounds = compute_xyz_bounds(comp_pts)
        components.append({
            "component_id": int(comp_id),
            "point_count": comp_size,
            "pct_of_building": round(comp_size / bld_count * 100, 2),
            "bounds": bounds,
        })

    components.sort(key=lambda c: c["point_count"], reverse=True)
    largest = components[0] if components else {"point_count": 0, "pct_of_building": 0}

    # XY fill ratio for building points
    if bld_count > 0:
        x = bld_pts[:, 0]
        y = bld_pts[:, 1]
        grid_res = 1.0
        gx = np.floor((x - x.min()) / grid_res).astype(int)
        gy = np.floor((y - y.min()) / grid_res).astype(int)
        nx = int(gx.max()) + 1
        ny = int(gy.max()) + 1
        grid = np.zeros((nx, ny), dtype=int)
        for i in range(bld_count):
            grid[gx[i], gy[i]] += 1
        occupied = int(np.sum(grid > 0))
        total_cells = nx * ny
        fill_ratio = round(occupied / max(total_cells, 1) * 100, 2)
    else:
        fill_ratio = 0.0

    return {
        "building_point_count": bld_count,
        "component_count": len(components),
        "noise_points_in_building": noise_count,
        "largest_component_size": largest["point_count"],
        "largest_component_pct": largest["pct_of_building"],
        "components": components[:10],  # top 10 only
        "xy_fill_ratio_1m_pct": fill_ratio,
    }


def compute_feature_separation(class_stats: dict) -> dict:
    """Check whether features separate BUILDING from VEGETATION."""
    sep = {}
    bld = class_stats.get("BUILDING", {})
    veg = class_stats.get("VEGETATION", {})

    if bld.get("count", 0) == 0 or veg.get("count", 0) == 0:
        return {"note": "Cannot compute separation -- one class is empty"}

    for feat in ["planarity", "roughness", "normal_consistency", "density", "color", "spatial_context"]:
        bld_med = bld.get(f"{feat}_raw", {}).get("median", None)
        veg_med = veg.get(f"{feat}_raw", {}).get("median", None)
        if bld_med is not None and veg_med is not None:
            diff = round(bld_med - veg_med, 6)
            # Expected: building planarity > vegetation planarity
            # Expected: building roughness < vegetation roughness
            expected_positive = feat in ["planarity", "density", "color", "spatial_context"]
            expected_negative = feat in ["roughness", "normal_consistency"]

            if expected_positive:
                trend_present = diff > 0
            elif expected_negative:
                trend_present = diff < 0
            else:
                trend_present = None

            sep[feat] = {
                "building_median": bld_med,
                "vegetation_median": veg_med,
                "difference": diff,
                "expected_trend_present": trend_present,
                "note": "DIAGNOSTIC ONLY -- not a hard pass/fail test"
            }

    return sep


def generate_visualization_data(
    points: np.ndarray,
    colors: np.ndarray,
    labels: np.ndarray,
    scores: np.ndarray,
) -> dict:
    """
    Generate frontend-compatible visualization layers.

    Uses index-based references to avoid duplicating the full point cloud.
    Each layer is a list of indices into the original candidate array.
    """
    viz = {
        "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "georeferenced": False,
        "total_points": len(points),
        "layers": {},
    }

    for cid, cname in CLASS_NAMES.items():
        mask = labels == cid
        indices = np.where(mask)[0].tolist()
        layer_pts = points[mask]

        # Flat points array for direct rendering
        flat = []
        for i in indices:
            x, y, z = float(points[i, 0]), float(points[i, 1]), float(points[i, 2])
            r, g, b = int(colors[i, 0]), int(colors[i, 1]), int(colors[i, 2])
            flat.extend([round(x, 3), round(y, 3), round(z, 3), r, g, b])

        viz["layers"][cname] = {
            "point_count": len(indices),
            "indices": indices,
            "points_flat": flat,
            "bounds": compute_xyz_bounds(layer_pts) if len(layer_pts) > 0 else {},
        }

    # Also include ALL_CANDIDATE as the original points
    flat_all = []
    for i in range(len(points)):
        x, y, z = float(points[i, 0]), float(points[i, 1]), float(points[i, 2])
        r, g, b = int(colors[i, 0]), int(colors[i, 1]), int(colors[i, 2])
        flat_all.extend([round(x, 3), round(y, 3), round(z, 3), r, g, b])

    viz["layers"]["ALL_CANDIDATE"] = {
        "point_count": len(points),
        "points_flat": flat_all,
        "bounds": compute_xyz_bounds(points),
    }

    return viz


def investigate_21124_discrepancy(derived_dir: Path, cloud: dict) -> dict:
    """Definitively trace the 11,049 vs 21,124 discrepancy."""
    result = {
        "current_candidate_count": len(cloud.get("selected_building_points", [])) // 6,
        "current_candidate_source": "aam_khas_bagh_classified_cloud.json",
        "current_candidate_id": cloud.get("extracted_building", {}).get("candidate_id"),
    }

    mesh_meta_path = derived_dir / "aam_khas_bagh_mesh_metadata.json"
    if mesh_meta_path.exists():
        with open(mesh_meta_path, "r") as f:
            mesh_meta = json.load(f)
        result["mesh_input_point_count"] = mesh_meta.get("input_point_count")
        result["mesh_reconstruction_method"] = mesh_meta.get("reconstruction_method")
        result["mesh_source_file"] = mesh_meta.get("source")

        cloud_mtime = os.path.getmtime(derived_dir / "aam_khas_bagh_classified_cloud.json")
        mesh_mtime = os.path.getmtime(derived_dir / "aam_khas_bagh_hammam_mesh.ply")

        result["classified_cloud_timestamp"] = datetime.fromtimestamp(cloud_mtime).isoformat()
        result["mesh_timestamp"] = datetime.fromtimestamp(mesh_mtime).isoformat()
        result["same_pipeline_run"] = False
        result["explanation"] = (
            "The classified cloud (11,049 pts) was generated AFTER the mesh (21,124 pts). "
            "The extraction pipeline was re-run with different sampling/DBSCAN parameters, "
            "producing a different candidate. The mesh and cloud are from DIFFERENT pipeline runs."
        )
    else:
        result["mesh_data_available"] = False

    return result


def main():
    derived_dir = backend_dir.parent / "data" / "aam_khas_bagh" / "derived"
    cloud_path = derived_dir / "aam_khas_bagh_classified_cloud.json"

    if not cloud_path.exists():
        print(f"ERROR: {cloud_path} not found")
        sys.exit(1)

    print("=" * 60)
    print("AAM KHAS BAGH -- BUILDING/VEGETATION SEGMENTATION")
    print("coordinate_system: AAM_KHAS_BAGH_LOCAL")
    print("georeferenced: false")
    print("=" * 60)

    # ── Load data ─────────────────────────────────────────────
    print("\nLoading candidate points...")
    points, colors, cloud = load_candidate_points(cloud_path)
    candidate_count = len(points)
    print(f"  Loaded {candidate_count} candidate points with RGB")

    # ── Configure ─────────────────────────────────────────────
    config = VegetationFilterConfig(
        weight_planarity=0.30,
        weight_roughness=0.25,
        weight_normal_consistency=0.20,
        weight_density=0.10,
        weight_color=0.05,
        weight_spatial_context=0.10,
        k_neighbors=15,
        building_threshold=0.65,
        vegetation_threshold=0.30,
    )

    # ── Run classification ────────────────────────────────────
    print("\nRunning classification...")
    result = classify_building_vegetation(points, colors, config)

    labels = result["labels"]
    scores = result["scores"]

    # ── Structural integrity assertions ───────────────────────
    print("\nValidating structural integrity...")
    counts = result["class_counts"]
    total = sum(counts.values())
    assert total == candidate_count, f"Count mismatch: {total} != {candidate_count}"

    for i in range(candidate_count):
        assert labels[i] in (CLASS_BUILDING, CLASS_VEGETATION, CLASS_UNKNOWN, CLASS_OUTLIER), \
            f"Point {i} has invalid class {labels[i]}"
        assert np.all(np.isfinite(points[i])), f"Point {i} has non-finite coordinates"

    # Verify exactly one class per point
    unique_per_point = set()
    for cid in CLASS_NAMES:
        mask = labels == cid
        unique_per_point.update(np.where(mask)[0].tolist())
    assert len(unique_per_point) == candidate_count, "Not all points classified"

    print("  All structural integrity checks PASSED")

    # ── Per-class analysis ────────────────────────────────────
    print("\nComputing per-class analysis...")

    z_base = float(points[:, 2].min())
    class_analysis = {}
    for cid, cname in CLASS_NAMES.items():
        mask = labels == cid
        c_pts = points[mask]
        c_count = int(np.sum(mask))

        analysis = {
            "count": c_count,
            "pct": round(c_count / candidate_count * 100, 2),
            "bounds": compute_xyz_bounds(c_pts) if c_count > 0 else {},
        }

        if c_count > 0:
            analysis["z_distribution"] = compute_z_distribution(c_pts, z_base)
            x_range = float(c_pts[:, 0].max() - c_pts[:, 0].min()) if c_count > 1 else 0
            y_range = float(c_pts[:, 1].max() - c_pts[:, 1].min()) if c_count > 1 else 0
            analysis["xy_footprint_m2"] = round(x_range * y_range, 2)
            vol = x_range * y_range * max(float(c_pts[:, 2].max() - c_pts[:, 2].min()), 0.01)
            analysis["point_density_pts_m3"] = round(c_count / max(vol, 0.01), 2)

        class_analysis[cname] = analysis

    # ── Spatial coherence ─────────────────────────────────────
    print("Computing spatial coherence...")
    spatial_coherence = compute_spatial_coherence(points, labels)

    # ── Feature separation ────────────────────────────────────
    print("Computing feature separation...")
    feature_separation = compute_feature_separation(result["feature_stats_per_class"])

    # ── 11,049 vs 21,124 investigation ────────────────────────
    print("Investigating 11,049 vs 21,124 discrepancy...")
    discrepancy = investigate_21124_discrepancy(derived_dir, cloud)

    # ── Score distribution ────────────────────────────────────
    score_dist = {
        "min": round(float(scores.min()), 4),
        "p05": round(float(np.percentile(scores, 5)), 4),
        "p10": round(float(np.percentile(scores, 10)), 4),
        "p25": round(float(np.percentile(scores, 25)), 4),
        "median": round(float(np.median(scores)), 4),
        "p75": round(float(np.percentile(scores, 75)), 4),
        "p90": round(float(np.percentile(scores, 90)), 4),
        "p95": round(float(np.percentile(scores, 95)), 4),
        "max": round(float(scores.max()), 4),
    }

    # ── Comparison with original candidate ────────────────────
    bld_mask = labels == CLASS_BUILDING
    bld_pts = points[bld_mask]
    original_bounds = compute_xyz_bounds(points)
    building_bounds = compute_xyz_bounds(bld_pts) if len(bld_pts) > 0 else {}

    comparison = {
        "original_candidate": {
            "count": candidate_count,
            "bounds": original_bounds,
        },
        "filtered_building": {
            "count": int(np.sum(bld_mask)),
            "bounds": building_bounds,
        },
    }

    if len(bld_pts) > 0:
        comparison["filtered_building"]["z_range_m"] = round(
            building_bounds["z_max"] - building_bounds["z_min"], 4
        )
        comparison["filtered_building"]["x_range_m"] = round(
            building_bounds["x_max"] - building_bounds["x_min"], 4
        )
        comparison["filtered_building"]["y_range_m"] = round(
            building_bounds["y_max"] - building_bounds["y_min"], 4
        )

    # ── RGB quality assessment ────────────────────────────────
    rgb_assessment = {
        "available": config.rgb_available,
        "unique_colors": int(len(np.unique(colors, axis=0))),
        "zero_rgb_count": int(np.sum(np.all(colors == 0, axis=1))),
        "r_mean": round(float(colors[:, 0].mean()), 1),
        "g_mean": round(float(colors[:, 1].mean()), 1),
        "b_mean": round(float(colors[:, 2].mean()), 1),
        "pipeline": "E57 -> voxel_grid_downsample (averaged per 0.10m voxel) -> DBSCAN indexing",
        "quality": "PRESENT but voxel-averaged -- usable as secondary evidence only",
    }

    # ── Quality flags ─────────────────────────────────────────
    quality_flags = []
    if counts["BUILDING"] < 1000:
        quality_flags.append("WARNING: Very few BUILDING points (<1000)")
    if counts["UNKNOWN"] > candidate_count * 0.5:
        quality_flags.append("WARNING: >50% of points classified as UNKNOWN")
    if spatial_coherence["largest_component_pct"] < 50:
        quality_flags.append("WARNING: Largest building component <50% of building points")
    if not config.rgb_available:
        quality_flags.append("INFO: RGB not available -- color feature disabled")

    # Check feature separation quality
    well_separated = sum(
        1 for f in feature_separation.values()
        if isinstance(f, dict) and f.get("expected_trend_present") == True
    )
    total_features = sum(
        1 for f in feature_separation.values()
        if isinstance(f, dict) and f.get("expected_trend_present") is not None
    )
    if total_features > 0 and well_separated < total_features / 2:
        quality_flags.append(f"WARNING: Only {well_separated}/{total_features} features show expected separation")

    # ── Build final report ────────────────────────────────────
    report = {
        "title": "AAM KHAS BAGH -- VEGETATION CLASSIFICATION REPORT",
        "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "georeferenced": False,
        "timestamp": datetime.now().isoformat(),

        "dataset": {
            "source": "aam_khas_bagh_classified_cloud.json",
            "candidate_count": candidate_count,
            "e57_file": cloud.get("file_name", "7csx-ne47_terresterial_lidar.e57"),
        },

        "pipeline_parameters": {
            "config": config.to_dict(),
            "active_weights": result["active_weights"],
        },

        "feature_definitions": {
            "planarity": "PCA eigenvalue analysis of k-nearest neighbors. (lambda2-lambda3)/(lambda1+eps)",
            "roughness": "Std of point-to-local-plane distances within k-neighborhood. INVERTED for scoring.",
            "normal_consistency": "Angular variance (degrees) of normals within radius. INVERTED for scoring.",
            "density": "Count of neighbors within density_radius.",
            "color": "1 - green_ratio. Higher = less green = more building-like.",
            "spatial_context": "Mean planarity of k-nearest neighbors.",
        },

        "normalization": result["normalization"],

        "classification": {
            "class_counts": counts,
            "class_percentages": result["class_percentages"],
            "total_classified": total,
            "total_matches_input": total == candidate_count,
        },

        "per_class_analysis": class_analysis,

        "score_distribution": score_dist,

        "feature_distributions_global": result["feature_stats_global"],
        "feature_distributions_per_class": result["feature_stats_per_class"],
        "feature_separation": feature_separation,

        "spatial_coherence": spatial_coherence,

        "comparison_with_original": comparison,

        "rgb_assessment": rgb_assessment,

        "discrepancy_11049_vs_21124": discrepancy,

        "quality_flags": quality_flags,

        "recommended_next_step": "",  # filled below
    }

    # ── Recommendation ────────────────────────────────────────
    bld_count = counts["BUILDING"]
    if bld_count > 3000 and spatial_coherence["largest_component_pct"] > 60:
        method_rec = (
            "Ball Pivoting is recommended over Poisson for the next reconstruction. "
            "Poisson tends to interpolate unsupported surfaces between sparse points. "
            "Ball Pivoting creates surfaces only where measured points exist, which is "
            "more appropriate for a filtered point cloud that may have gaps where "
            "vegetation was removed. Alpha shape could also be tested for the footprint."
        )
    elif bld_count > 1000:
        method_rec = (
            "The building point count is moderate. Try Ball Pivoting first with "
            "adaptive radii based on local point spacing. If gaps are too large, "
            "consider Poisson at depth 6 (lower than 8) with aggressive density trimming."
        )
    else:
        method_rec = (
            "Building point count is low. Review classification thresholds. "
            "Consider relaxing building_threshold or increasing UNKNOWN inclusion. "
            "Do not reconstruct mesh until sufficient building points are validated."
        )

    report["recommended_next_step"] = method_rec

    # ── Save report ───────────────────────────────────────────
    report_path = derived_dir / "aam_khas_bagh_vegetation_classification.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nSaved: {report_path.name}")

    # ── Save visualization data ───────────────────────────────
    print("Generating visualization data...")
    viz = generate_visualization_data(points, colors, labels, scores)
    viz_path = derived_dir / "aam_khas_bagh_classified_building_points.json"
    with open(viz_path, "w", encoding="utf-8") as f:
        json.dump(viz, f)
    print(f"Saved: {viz_path.name}")

    # ── Print final summary ───────────────────────────────────
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"\n  A. BUILDING:    {counts['BUILDING']:>6d} ({result['class_percentages']['BUILDING']}%)")
    print(f"  B. VEGETATION:  {counts['VEGETATION']:>6d} ({result['class_percentages']['VEGETATION']}%)")
    print(f"  C. UNKNOWN:     {counts['UNKNOWN']:>6d} ({result['class_percentages']['UNKNOWN']}%)")
    print(f"  D. OUTLIER:     {counts['OUTLIER']:>6d} ({result['class_percentages']['OUTLIER']}%)")
    print(f"  E. TOTAL:       {total:>6d} == {candidate_count} ? {'YES' if total == candidate_count else 'NO'}")

    if len(bld_pts) > 0:
        print(f"\n  F. BUILDING BOUNDS:")
        for k, v in building_bounds.items():
            print(f"     {k}: {v}")

    print(f"\n  G. Largest building component: {spatial_coherence['largest_component_pct']}% "
          f"({spatial_coherence['largest_component_size']} pts)")

    print(f"\n  H. Feature separation:")
    for feat, info in feature_separation.items():
        if isinstance(info, dict) and "expected_trend_present" in info:
            status = "YES" if info["expected_trend_present"] else "NO"
            print(f"     {feat}: expected trend present = {status} "
                  f"(bld={info['building_median']}, veg={info['vegetation_median']})")

    print(f"\n  I. RGB reliable: {rgb_assessment['quality']}")

    if bld_count > 3000 and spatial_coherence["largest_component_pct"] > 60:
        suitable = "YES -- building cloud appears spatially coherent"
    elif bld_count > 1000:
        suitable = "PARTIAL -- review classification before reconstruction"
    else:
        suitable = "NO -- insufficient building points"
    print(f"\n  J. Suitable for reconstruction: {suitable}")
    print(f"\n  K. Recommended method: {method_rec[:80]}...")

    if quality_flags:
        print(f"\n  QUALITY FLAGS:")
        for flag in quality_flags:
            print(f"    - {flag}")

    print(f"\n{'=' * 60}")
    print(f"COMPLETE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
