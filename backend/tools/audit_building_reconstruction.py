"""
Aam Khas Bagh -- Reconstruction Data Validation Audit

Performs an exhaustive, non-destructive audit of the entire reconstruction
pipeline from classified point cloud to PLY mesh, WITHOUT modifying any data.

Audit sections:
  1. Selected Building Point Geometry
  2. 3D Coverage / Height Distribution
  3. Building vs Vegetation/Outlier Classification Analysis
  4. Input Points vs Mesh Bounds Comparison
  5. Poisson Mesh Support Analysis
  6. Normal Estimation Audit
  7. Four-Orientation Diagnostic Analysis
  8. Height Consistency Investigation

Output: data/aam_khas_bagh/derived/building_point_geometry_audit.json

coordinate_system: AAM_KHAS_BAGH_LOCAL
georeferenced: false
"""

import json
import sys
from pathlib import Path
import numpy as np

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def load_building_points_from_classified_cloud(cloud_path: Path) -> np.ndarray:
    """Load selected_building_points from the classified cloud JSON.
    Format: flat list [x,y,z,r,g,b, x,y,z,r,g,b, ...]
    Returns (N, 3) XYZ array.
    """
    with open(cloud_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    flat = data.get("selected_building_points", [])
    num_pts = len(flat) // 6
    pts = np.zeros((num_pts, 3), dtype=np.float64)
    for i in range(num_pts):
        base = i * 6
        pts[i, 0] = flat[base]
        pts[i, 1] = flat[base + 1]
        pts[i, 2] = flat[base + 2]
    return pts, data


def load_all_cloud_layers(data: dict):
    """Load ground, non-ground, and building points from classified cloud."""
    layers = {}
    for key in ["ground_points", "non_ground_points", "selected_building_points"]:
        flat = data.get(key, [])
        num_pts = len(flat) // 6
        pts = np.zeros((num_pts, 3), dtype=np.float64)
        colors = np.zeros((num_pts, 3), dtype=np.uint8)
        for i in range(num_pts):
            base = i * 6
            pts[i, 0] = flat[base]
            pts[i, 1] = flat[base + 1]
            pts[i, 2] = flat[base + 2]
            colors[i, 0] = int(flat[base + 3])
            colors[i, 1] = int(flat[base + 4])
            colors[i, 2] = int(flat[base + 5])
        layers[key] = {"points": pts, "colors": colors}
    return layers


def audit_1_point_geometry(pts: np.ndarray) -> dict:
    """Audit 1: Selected Building Point Geometry."""
    print("\n" + "=" * 60)
    print("AUDIT 1: SELECTED BUILDING POINT GEOMETRY")
    print("=" * 60)

    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]

    result = {
        "point_count": len(pts),
        "x_min": round(float(x.min()), 4),
        "x_max": round(float(x.max()), 4),
        "y_min": round(float(y.min()), 4),
        "y_max": round(float(y.max()), 4),
        "z_min": round(float(z.min()), 4),
        "z_max": round(float(z.max()), 4),
        "x_range": round(float(x.max() - x.min()), 4),
        "y_range": round(float(y.max() - y.min()), 4),
        "z_range": round(float(z.max() - z.min()), 4),
        "mean_x": round(float(np.mean(x)), 4),
        "mean_y": round(float(np.mean(y)), 4),
        "mean_z": round(float(np.mean(z)), 4),
        "median_x": round(float(np.median(x)), 4),
        "median_y": round(float(np.median(y)), 4),
        "median_z": round(float(np.median(z)), 4),
        "p05_z": round(float(np.percentile(z, 5)), 4),
        "p95_z": round(float(np.percentile(z, 95)), 4),
        "p01_z": round(float(np.percentile(z, 1)), 4),
        "p99_z": round(float(np.percentile(z, 99)), 4),
        "std_x": round(float(np.std(x)), 4),
        "std_y": round(float(np.std(y)), 4),
        "std_z": round(float(np.std(z)), 4),
    }

    for k, v in result.items():
        print(f"  {k}: {v}")

    return result


def audit_2_height_distribution(pts: np.ndarray) -> dict:
    """Audit 2: Height Distribution -- Are the building points actually 3D?"""
    print("\n" + "=" * 60)
    print("AUDIT 2: HEIGHT DISTRIBUTION / 3D COVERAGE")
    print("=" * 60)

    z = pts[:, 2]
    z_min = float(z.min())
    z_shifted = z - z_min  # Shift to 0-based bins

    # Create 1m bins
    bin_edges = list(range(0, int(np.ceil(z_shifted.max())) + 2))
    bins = {}
    total = len(z)

    for i in range(len(bin_edges) - 1):
        lo = bin_edges[i]
        hi = bin_edges[i + 1]
        mask = (z_shifted >= lo) & (z_shifted < hi)
        count = int(np.sum(mask))
        pct = round(count / total * 100, 2)
        label = f"{lo}-{hi}m"
        bins[label] = {"count": count, "pct": pct}
        marker = "#" * int(pct)
        print(f"  Z bin {label:>8s}: {count:>6d} pts ({pct:>6.2f}%) {marker}")

    # XY density: average points per square meter (2D projection)
    x_range = float(pts[:, 0].max() - pts[:, 0].min())
    y_range = float(pts[:, 1].max() - pts[:, 1].min())
    z_range = float(z.max() - z.min())
    xy_area = x_range * y_range
    volume = xy_area * z_range

    xy_density = round(total / max(xy_area, 0.01), 2)
    vol_density = round(total / max(volume, 0.01), 2)

    # Vertical extent assessment
    # A truly 3D building should have substantial points across many Z levels
    occupied_bins = sum(1 for b in bins.values() if b["count"] > 0)
    total_bins = len(bins)

    # Check if roof-dominated: what % is in top 25% of height?
    z_75pct = np.percentile(z, 75)
    top_quarter_count = int(np.sum(z >= z_75pct))
    top_quarter_pct = round(top_quarter_count / total * 100, 2)

    # Check if bottom-dominated: what % is in bottom 25%?
    z_25pct = np.percentile(z, 25)
    bottom_quarter_count = int(np.sum(z <= z_25pct))
    bottom_quarter_pct = round(bottom_quarter_count / total * 100, 2)

    # Middle 50% for walls
    mid_mask = (z > z_25pct) & (z < z_75pct)
    mid_count = int(np.sum(mid_mask))
    mid_pct = round(mid_count / total * 100, 2)

    result = {
        "z_bins_1m": bins,
        "z_min_absolute": round(float(z.min()), 4),
        "z_max_absolute": round(float(z.max()), 4),
        "z_range_m": round(z_range, 4),
        "xy_footprint_area_m2": round(xy_area, 2),
        "bounding_volume_m3": round(volume, 2),
        "xy_density_pts_per_m2": xy_density,
        "volume_density_pts_per_m3": vol_density,
        "occupied_z_bins": occupied_bins,
        "total_z_bins": total_bins,
        "vertical_coverage_pct": round(occupied_bins / max(total_bins, 1) * 100, 1),
        "bottom_25pct_z_threshold": round(float(z_25pct), 4),
        "bottom_25pct_point_count": bottom_quarter_count,
        "bottom_25pct_of_total": bottom_quarter_pct,
        "middle_50pct_point_count": mid_count,
        "middle_50pct_of_total": mid_pct,
        "top_25pct_z_threshold": round(float(z_75pct), 4),
        "top_25pct_point_count": top_quarter_count,
        "top_25pct_of_total": top_quarter_pct,
    }

    print(f"\n  XY footprint area: {xy_area:.2f} m2")
    print(f"  Bounding volume:   {volume:.2f} m3")
    print(f"  XY density:        {xy_density} pts/m2")
    print(f"  Volume density:    {vol_density} pts/m3")
    print(f"  Occupied Z bins:   {occupied_bins}/{total_bins}")
    print(f"  Bottom 25% Z:      {bottom_quarter_count} pts ({bottom_quarter_pct}%)")
    print(f"  Middle 50% (walls):{mid_count} pts ({mid_pct}%)")
    print(f"  Top 25% Z:         {top_quarter_count} pts ({top_quarter_pct}%)")

    # Diagnosis
    if mid_pct < 15:
        diagnosis = "ROOF_DOMINATED -- very few wall/vertical points"
    elif mid_pct < 30:
        diagnosis = "PARTIAL_3D -- some wall points but likely incomplete coverage"
    else:
        diagnosis = "GOOD_3D -- reasonable vertical distribution"

    result["3d_coverage_diagnosis"] = diagnosis
    print(f"\n  DIAGNOSIS: {diagnosis}")

    return result


def audit_3_classification_analysis(layers: dict, building_pts: np.ndarray) -> dict:
    """Audit 3: Separate building from vegetation/outliers."""
    print("\n" + "=" * 60)
    print("AUDIT 3: CLASSIFICATION ANALYSIS (BUILDING vs VEGETATION vs OUTLIERS)")
    print("=" * 60)

    non_ground = layers["non_ground_points"]["points"]
    building = building_pts

    b_z = building[:, 2]
    total = len(building)

    # --- Heuristic vegetation detection ---
    # Vegetation tends to have:
    # 1. High local Z variance (irregular surface)
    # 2. Low XY planarity
    # 3. Points that are isolated vertically

    from scipy.spatial import KDTree

    tree = KDTree(building)

    # Compute local Z variance in a 0.5m radius
    local_z_var = np.zeros(total)
    local_z_range = np.zeros(total)
    local_count = np.zeros(total, dtype=int)

    # Use batch query for efficiency
    neighbors = tree.query_ball_point(building, r=0.5)
    for i, nbrs in enumerate(neighbors):
        if len(nbrs) > 1:
            nbr_z = b_z[nbrs]
            local_z_var[i] = float(np.var(nbr_z))
            local_z_range[i] = float(nbr_z.max() - nbr_z.min())
            local_count[i] = len(nbrs)
        else:
            local_z_var[i] = 0
            local_z_range[i] = 0
            local_count[i] = 1

    # High local Z variance in small radius -> likely vegetation
    z_var_p90 = float(np.percentile(local_z_var[local_z_var > 0], 90)) if np.sum(local_z_var > 0) > 0 else 1.0
    vegetation_like_mask = (local_z_var > z_var_p90 * 0.7) & (local_z_range > 0.3)
    vegetation_count = int(np.sum(vegetation_like_mask))

    # Isolated points (very few neighbors in 0.3m)
    neighbors_tight = tree.query_ball_point(building, r=0.3)
    isolated_mask = np.array([len(n) <= 2 for n in neighbors_tight])
    isolated_count = int(np.sum(isolated_mask))

    # Building-like: neither vegetation-like nor isolated
    building_like_mask = ~vegetation_like_mask & ~isolated_mask
    building_like_count = int(np.sum(building_like_mask))

    # Color-based analysis: check if green-dominant points exist
    # (would need color data, but we can use spatial heuristics for now)

    # Analyze height profile of each category
    result = {
        "total_selected_building_points": total,
        "building_like_points": building_like_count,
        "building_like_pct": round(building_like_count / total * 100, 2),
        "vegetation_like_points": vegetation_count,
        "vegetation_like_pct": round(vegetation_count / total * 100, 2),
        "isolated_outlier_points": isolated_count,
        "isolated_outlier_pct": round(isolated_count / total * 100, 2),
        "local_z_variance_stats": {
            "mean": round(float(np.mean(local_z_var)), 4),
            "median": round(float(np.median(local_z_var)), 4),
            "p90": round(float(np.percentile(local_z_var, 90)), 4),
            "p99": round(float(np.percentile(local_z_var, 99)), 4),
        },
        "local_z_range_stats": {
            "mean": round(float(np.mean(local_z_range)), 4),
            "median": round(float(np.median(local_z_range)), 4),
            "p90": round(float(np.percentile(local_z_range, 90)), 4),
        },
        "classification_confidence": "HEURISTIC -- not ground truth",
        "note": "Vegetation detection uses local Z variance heuristic. "
                "Uncertain classifications preserved. No data deleted.",
    }

    # Z profile by category
    if vegetation_count > 0:
        veg_z = b_z[vegetation_like_mask]
        result["vegetation_z_profile"] = {
            "z_min": round(float(veg_z.min()), 4),
            "z_max": round(float(veg_z.max()), 4),
            "z_mean": round(float(np.mean(veg_z)), 4),
            "z_range": round(float(veg_z.max() - veg_z.min()), 4),
        }

    if building_like_count > 0:
        bld_z = b_z[building_like_mask]
        result["building_z_profile"] = {
            "z_min": round(float(bld_z.min()), 4),
            "z_max": round(float(bld_z.max()), 4),
            "z_mean": round(float(np.mean(bld_z)), 4),
            "z_range": round(float(bld_z.max() - bld_z.min()), 4),
        }

    print(f"  Total selected building points: {total}")
    print(f"  Building-like points:            {building_like_count} ({result['building_like_pct']}%)")
    print(f"  Vegetation-like points:          {vegetation_count} ({result['vegetation_like_pct']}%)")
    print(f"  Isolated/outlier points:         {isolated_count} ({result['isolated_outlier_pct']}%)")
    print(f"\n  NOTE: Classification is HEURISTIC. No data deleted.")

    # Check how many non-ground points total vs selected building
    non_ground_total = len(non_ground)
    result["non_ground_total"] = non_ground_total
    result["building_fraction_of_non_ground"] = round(total / max(non_ground_total, 1) * 100, 2)
    print(f"\n  Non-ground total:       {non_ground_total}")
    print(f"  Building fraction:      {result['building_fraction_of_non_ground']}%")

    return result


def audit_4_input_vs_mesh_bounds(building_pts: np.ndarray, mesh_meta: dict) -> dict:
    """Audit 4: Compare input point cloud with current mesh bounds."""
    print("\n" + "=" * 60)
    print("AUDIT 4: INPUT POINT CLOUD vs MESH BOUNDS")
    print("=" * 60)

    x, y, z = building_pts[:, 0], building_pts[:, 1], building_pts[:, 2]

    input_bounds = {
        "x_min": float(x.min()),
        "x_max": float(x.max()),
        "y_min": float(y.min()),
        "y_max": float(y.max()),
        "z_min": float(z.min()),
        "z_max": float(z.max()),
    }

    mesh_bounds = mesh_meta.get("bounds", {})

    result = {
        "input_bounds": {k: round(v, 4) for k, v in input_bounds.items()},
        "mesh_bounds": mesh_bounds,
        "input_dimensions": {
            "x_range": round(input_bounds["x_max"] - input_bounds["x_min"], 4),
            "y_range": round(input_bounds["y_max"] - input_bounds["y_min"], 4),
            "z_range": round(input_bounds["z_max"] - input_bounds["z_min"], 4),
        },
        "mesh_dimensions": mesh_meta.get("dimensions", {}),
    }

    # Compute differences
    for axis in ["x", "y", "z"]:
        i_range = input_bounds[f"{axis}_max"] - input_bounds[f"{axis}_min"]
        m_range = mesh_bounds.get(f"{axis}_max", 0) - mesh_bounds.get(f"{axis}_min", 0)
        diff = m_range - i_range
        result[f"{axis}_range_difference_m"] = round(diff, 4)
        result[f"{axis}_mesh_expansion_pct"] = round(diff / max(i_range, 0.01) * 100, 2)

    # Mesh exceeds input bounds?
    for axis in ["x", "y", "z"]:
        i_min = input_bounds[f"{axis}_min"]
        i_max = input_bounds[f"{axis}_max"]
        m_min = mesh_bounds.get(f"{axis}_min", 0)
        m_max = mesh_bounds.get(f"{axis}_max", 0)
        result[f"{axis}_mesh_extends_below_input"] = round(i_min - m_min, 4)
        result[f"{axis}_mesh_extends_above_input"] = round(m_max - i_max, 4)

    print(f"\n  {'Axis':<6} {'Input Range':>12} {'Mesh Range':>12} {'Difference':>12} {'Expansion%':>12}")
    print(f"  {'-'*6} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
    for axis in ["x", "y", "z"]:
        i_r = result["input_dimensions"][f"{axis}_range"]
        m_r = mesh_meta.get("dimensions", {}).get(f"{'width' if axis == 'x' else 'length' if axis == 'y' else 'height'}_m", 0)
        diff = result[f"{axis}_range_difference_m"]
        exp = result[f"{axis}_mesh_expansion_pct"]
        print(f"  {axis.upper():<6} {i_r:>12.4f} {m_r:>12.3f} {diff:>+12.4f} {exp:>+12.2f}%")

    print(f"\n  Mesh extends beyond input bounds:")
    for axis in ["x", "y", "z"]:
        below = result[f"{axis}_mesh_extends_below_input"]
        above = result[f"{axis}_mesh_extends_above_input"]
        print(f"    {axis.upper()}: below input by {below:+.4f}m  |  above input by {above:+.4f}m")

    return result


def audit_5_poisson_support(mesh_meta: dict) -> dict:
    """Audit 5: Check Poisson-created unsupported surfaces from existing metadata."""
    print("\n" + "=" * 60)
    print("AUDIT 5: POISSON MESH SUPPORT ANALYSIS")
    print("=" * 60)

    support = mesh_meta.get("mesh_support", {})
    coverage = mesh_meta.get("point_coverage", {})
    p2m = mesh_meta.get("point_to_mesh_distance", {})

    result = {
        "mesh_support_from_metadata": support,
        "point_coverage_from_metadata": coverage,
        "point_to_mesh_distance_from_metadata": p2m,
    }

    # Interpret support levels
    total_samples = support.get("total_samples", 0)
    if total_samples > 0:
        supported_010 = support.get("pct_supported_within_010m", 0)
        supported_020 = support.get("pct_supported_within_020m", 0)
        supported_050 = support.get("pct_supported_within_050m", 0)
        supported_100 = support.get("pct_supported_within_100m", 0)

        unsupported_050 = round(100 - supported_050, 2)
        weakly_supported = round(supported_100 - supported_050, 2)
        well_supported = round(supported_050, 2)

        result["interpretation"] = {
            "well_supported_pct": well_supported,
            "weakly_supported_pct": weakly_supported,
            "unsupported_pct": unsupported_050,
            "note": "Well-supported = mesh within 0.50m of LiDAR point. "
                    "Weakly = 0.50-1.00m. Unsupported = >1.00m.",
        }

        total_area = mesh_meta.get("surface_area_m2", 0)
        result["estimated_area_breakdown"] = {
            "total_mesh_area_m2": total_area,
            "supported_area_m2": round(total_area * well_supported / 100, 2),
            "weakly_supported_area_m2": round(total_area * weakly_supported / 100, 2),
            "unsupported_area_m2": round(total_area * unsupported_050 / 100, 2),
        }

        print(f"  Total mesh surface samples: {total_samples}")
        print(f"  Well-supported  (<=0.50m):  {well_supported}%")
        print(f"  Weakly-supported (0.5-1.0m): {weakly_supported}%")
        print(f"  Unsupported     (>1.00m):    {unsupported_050}%")
        print(f"\n  Total mesh area:             {total_area} m2")
        print(f"  Supported area:              {result['estimated_area_breakdown']['supported_area_m2']} m2")
        print(f"  Weakly supported area:       {result['estimated_area_breakdown']['weakly_supported_area_m2']} m2")
        print(f"  Unsupported area:            {result['estimated_area_breakdown']['unsupported_area_m2']} m2")

        # Mean mesh-sample-to-LiDAR distance
        dist_info = support.get("mesh_sample_to_lidar_distance", {})
        if dist_info:
            print(f"\n  Mesh->LiDAR distance: mean={dist_info.get('mean_m', 'N/A')}m, "
                  f"median={dist_info.get('median_m', 'N/A')}m, "
                  f"p95={dist_info.get('p95_m', 'N/A')}m")
    else:
        print("  WARNING: No mesh support data found in metadata.")

    return result


def audit_6_normals(mesh_meta: dict) -> dict:
    """Audit 6: Normal estimation method and parameters."""
    print("\n" + "=" * 60)
    print("AUDIT 6: NORMAL ESTIMATION AUDIT")
    print("=" * 60)

    search_rad = mesh_meta.get("normal_search_radius_m", None)
    normals_est = mesh_meta.get("normals_estimated", False)
    spacing = mesh_meta.get("point_spacing", {})

    result = {
        "normals_estimated": normals_est,
        "normal_estimation_method": "Open3D KDTreeSearchParamHybrid",
        "search_radius_m": search_rad,
        "max_nn": 30,
        "orientation_method": "orient_normals_consistent_tangent_plane(k=15), "
                              "fallback: orient_normals_towards_camera_location(centroid + [0,0,10])",
        "point_spacing": spacing,
        "search_radius_to_median_spacing_ratio": round(search_rad / max(spacing.get("median_m", 0.1), 0.001), 2) if search_rad else None,
    }

    # Assessment
    issues = []
    if search_rad and spacing.get("median_m", 0):
        ratio = search_rad / spacing["median_m"]
        if ratio > 6:
            issues.append(f"Search radius ({search_rad}m) is {ratio:.1f}x the median spacing "
                          f"({spacing['median_m']}m) -- may over-smooth normals on fine details")
        if ratio < 2:
            issues.append(f"Search radius too small -- may produce noisy normals")

    # Tangent plane orientation can flip normals on concave surfaces
    issues.append(
        "orient_normals_consistent_tangent_plane can fail on complex architectural geometry "
        "(e.g., domes, arches, internal corners). Fallback uses a single camera-above assumption "
        "which may incorrectly orient downward-facing normals (e.g., ceiling/soffit surfaces)."
    )

    result["potential_issues"] = issues

    print(f"  Normals estimated:      {normals_est}")
    print(f"  Method:                 Open3D KDTreeSearchParamHybrid")
    print(f"  Search radius:          {search_rad} m")
    print(f"  Max neighbors:          30")
    print(f"  Orientation:            consistent_tangent_plane(k=15)")
    print(f"  Radius/median spacing:  {result['search_radius_to_median_spacing_ratio']}")
    if issues:
        print(f"\n  POTENTIAL ISSUES:")
        for iss in issues:
            print(f"    [!] {iss}")

    return result


def audit_7_orientation_diagnostics(building_pts: np.ndarray, mesh_meta: dict) -> dict:
    """Audit 7: Numerical diagnostics from four orientations."""
    print("\n" + "=" * 60)
    print("AUDIT 7: FOUR-ORIENTATION DIAGNOSTIC ANALYSIS")
    print("=" * 60)

    x, y, z = building_pts[:, 0], building_pts[:, 1], building_pts[:, 2]
    total = len(building_pts)

    mesh_dims = mesh_meta.get("dimensions", {})
    mesh_bounds = mesh_meta.get("bounds", {})
    components = mesh_meta.get("components", [])

    # TOP view analysis: XY projection
    # How many distinct XY clusters?
    xy_extent_x = float(x.max() - x.min())
    xy_extent_y = float(y.max() - y.min())

    # Compute 2D XY density map (grid-based)
    grid_res = 1.0  # 1m grid
    gx = np.floor((x - x.min()) / grid_res).astype(int)
    gy = np.floor((y - y.min()) / grid_res).astype(int)
    nx = int(gx.max()) + 1
    ny = int(gy.max()) + 1
    density_grid = np.zeros((nx, ny), dtype=int)
    for i in range(total):
        density_grid[gx[i], gy[i]] += 1

    occupied_cells = int(np.sum(density_grid > 0))
    total_cells = nx * ny
    fill_ratio = round(occupied_cells / max(total_cells, 1) * 100, 2)

    # FRONT view analysis: XZ projection
    xz_extent_x = xy_extent_x
    xz_extent_z = float(z.max() - z.min())
    front_aspect = round(xz_extent_z / max(xz_extent_x, 0.01), 3)

    # SIDE view analysis: YZ projection
    yz_extent_y = xy_extent_y
    yz_extent_z = xz_extent_z
    side_aspect = round(yz_extent_z / max(yz_extent_y, 0.01), 3)

    # Mesh component analysis
    main_comp = components[0] if components else {}
    main_tri = main_comp.get("triangle_count", 0)
    total_tri = mesh_meta.get("triangle_count", 0)
    fragment_tris = total_tri - main_tri
    num_fragments = len(components) - 1 if len(components) > 1 else 0

    result = {
        "top_view": {
            "xy_extent_x_m": round(xy_extent_x, 3),
            "xy_extent_y_m": round(xy_extent_y, 3),
            "grid_resolution_m": grid_res,
            "occupied_cells": occupied_cells,
            "total_cells": total_cells,
            "fill_ratio_pct": fill_ratio,
        },
        "front_view": {
            "xz_extent_x_m": round(xz_extent_x, 3),
            "xz_extent_z_m": round(xz_extent_z, 3),
            "height_to_width_ratio": front_aspect,
        },
        "side_view": {
            "yz_extent_y_m": round(yz_extent_y, 3),
            "yz_extent_z_m": round(yz_extent_z, 3),
            "height_to_length_ratio": side_aspect,
        },
        "perspective": {
            "mesh_component_count": len(components),
            "main_component_triangles": main_tri,
            "fragment_triangles": fragment_tris,
            "fragment_components": num_fragments,
            "main_component_fraction_pct": round(main_tri / max(total_tri, 1) * 100, 2),
        },
    }

    # Diagnosis
    # A. Complete 3D building: high fill ratio, good aspect ratios, low fragmentation
    # B. Roof-dominated: high fill but very low height/width
    # C. Partial: moderate fill
    # D. Noisy/vegetation: high fragmentation, scattered
    # E. Unsupported Poisson: mesh much larger than input points

    mesh_to_input_expansion = {}
    for axis, dim_key in [("x", "width_m"), ("y", "length_m"), ("z", "height_m")]:
        i_range = result[f"{'top' if axis != 'z' else 'front'}_view"][
            f"{'xy_extent_x' if axis == 'x' else 'xy_extent_y' if axis == 'y' else 'xz_extent_z'}_m"
        ]
        m_range = mesh_dims.get(dim_key, 0)
        expansion = round(m_range - i_range, 3)
        mesh_to_input_expansion[f"{axis}_expansion_m"] = expansion

    result["mesh_expansion_beyond_input"] = mesh_to_input_expansion

    if fill_ratio < 30 and num_fragments > 5:
        classification = "D -- NOISY/VEGETATION-CONTAMINATED"
    elif front_aspect < 0.08 or side_aspect < 0.08:
        classification = "B -- ROOF-DOMINATED SURFACE"
    elif fill_ratio > 50 and front_aspect > 0.1:
        classification = "A -- COMPLETE 3D BUILDING (or near-complete)"
    elif mesh_to_input_expansion.get("z_expansion_m", 0) > 3:
        classification = "E -- UNSUPPORTED POISSON SURFACE"
    else:
        classification = "C -- PARTIAL BUILDING"

    result["mesh_classification"] = classification

    print(f"  TOP VIEW:")
    print(f"    XY extent: {xy_extent_x:.3f} x {xy_extent_y:.3f} m")
    print(f"    Fill ratio (1m grid): {fill_ratio}% ({occupied_cells}/{total_cells} cells)")
    print(f"  FRONT VIEW:")
    print(f"    XZ extent: {xz_extent_x:.3f} x {xz_extent_z:.3f} m")
    print(f"    Height/Width ratio: {front_aspect}")
    print(f"  SIDE VIEW:")
    print(f"    YZ extent: {yz_extent_y:.3f} x {yz_extent_z:.3f} m")
    print(f"    Height/Length ratio: {side_aspect}")
    print(f"  PERSPECTIVE:")
    print(f"    Components: {len(components)} (main: {main_tri} tris, fragments: {fragment_tris} tris)")
    print(f"    Main component fraction: {result['perspective']['main_component_fraction_pct']}%")
    print(f"\n  CLASSIFICATION: {classification}")

    return result


def audit_8_height_consistency(building_pts: np.ndarray, mesh_meta: dict, report: dict) -> dict:
    """Audit 8: Height discrepancy investigation."""
    print("\n" + "=" * 60)
    print("AUDIT 8: HEIGHT CONSISTENCY INVESTIGATION")
    print("=" * 60)

    z = building_pts[:, 2]

    # Height from extraction report
    report_height = report.get("estimated_building_height_m", None)
    report_elevation = report.get("elevation", {})
    report_ground_z = report_elevation.get("ground_z", None)
    report_roof_z = report_elevation.get("roof_z", None)

    # Height from mesh metadata
    mesh_height = mesh_meta.get("dimensions", {}).get("height_m", None)
    mesh_z_min = mesh_meta.get("bounds", {}).get("z_min", None)
    mesh_z_max = mesh_meta.get("bounds", {}).get("z_max", None)

    # Actual input point Z range
    input_z_min = float(z.min())
    input_z_max = float(z.max())
    input_z_range = input_z_max - input_z_min

    # P05 to P95 range (robust building height)
    p05_z = float(np.percentile(z, 5))
    p95_z = float(np.percentile(z, 95))
    robust_height = p95_z - p05_z

    result = {
        "report_height_m": report_height,
        "report_ground_z": report_ground_z,
        "report_roof_z": report_roof_z,
        "mesh_height_m": mesh_height,
        "mesh_z_min": mesh_z_min,
        "mesh_z_max": mesh_z_max,
        "input_z_min": round(input_z_min, 4),
        "input_z_max": round(input_z_max, 4),
        "input_z_range_m": round(input_z_range, 4),
        "input_p05_z": round(p05_z, 4),
        "input_p95_z": round(p95_z, 4),
        "input_robust_height_p05_p95_m": round(robust_height, 4),
        "discrepancy_report_vs_mesh_m": round(abs(mesh_height - report_height), 4) if mesh_height and report_height else None,
    }

    print(f"  Report height:       {report_height} m  (ground_z={report_ground_z}, roof_z={report_roof_z})")
    print(f"  Mesh Z range:        {mesh_height} m  (z_min={mesh_z_min}, z_max={mesh_z_max})")
    print(f"  Input point Z range: {round(input_z_range, 4)} m  (z_min={round(input_z_min, 4)}, z_max={round(input_z_max, 4)})")
    print(f"  Input robust height: {round(robust_height, 4)} m  (P05={round(p05_z, 4)}, P95={round(p95_z, 4)})")

    # --- Investigate causes ---
    causes = []

    # Cause 1: Different Z references
    # Report uses ground_z from nearby ground points (P5 of ground)
    # Mesh uses absolute Z range of mesh vertices
    if report_ground_z is not None and mesh_z_min is not None:
        ground_vs_mesh_bottom = round(report_ground_z - mesh_z_min, 4)
        result["ground_z_vs_mesh_bottom_diff"] = ground_vs_mesh_bottom
        if abs(ground_vs_mesh_bottom) > 0.5:
            causes.append({
                "cause": "DIFFERENT_Z_REFERENCE",
                "detail": f"Report ground_z ({report_ground_z}) differs from mesh z_min ({mesh_z_min}) by {ground_vs_mesh_bottom}m. "
                          f"Report height uses nearby ground points' P5 percentile, while mesh height is raw vertex Z range.",
                "severity": "HIGH",
            })

    # Cause 2: Poisson mesh extends beyond input points
    if mesh_z_min is not None and mesh_z_max is not None:
        mesh_below_input = round(input_z_min - mesh_z_min, 4)
        mesh_above_input = round(mesh_z_max - input_z_max, 4)
        result["mesh_extends_below_input_z"] = mesh_below_input
        result["mesh_extends_above_input_z"] = mesh_above_input

        if mesh_below_input > 0.3 or mesh_above_input > 0.3:
            causes.append({
                "cause": "POISSON_INTERPOLATION_EXTENDS_BEYOND_INPUT",
                "detail": f"Mesh extends {mesh_below_input}m below and {mesh_above_input}m above input points. "
                          f"Poisson surface reconstruction creates continuous surfaces that extend beyond observed data.",
                "severity": "HIGH",
            })

    # Cause 3: Vegetation in the selected candidate
    # The candidate's Z range comes from ALL points in the DBSCAN cluster, which may include trees
    if input_z_range > report_height * 1.5 and report_height:
        causes.append({
            "cause": "VEGETATION_OR_MIXED_STRUCTURES",
            "detail": f"Input point Z range ({round(input_z_range, 2)}m) is {round(input_z_range/report_height, 1)}x "
                      f"the reported building height ({report_height}m). The DBSCAN cluster likely includes "
                      f"vegetation canopy or adjacent structures.",
            "severity": "MEDIUM",
        })

    # Cause 4: Multiple structures in candidate
    comp_count = mesh_meta.get("component_count", 0)
    if comp_count > 5:
        causes.append({
            "cause": "MULTIPLE_DISCONNECTED_STRUCTURES",
            "detail": f"Mesh has {comp_count} disconnected components. The DBSCAN cluster (eps=1.2m) "
                      f"may have merged multiple structures into one candidate.",
            "severity": "MEDIUM",
        })

    # Summary
    discrepancy = abs(mesh_height - report_height) if mesh_height and report_height else 0
    result["discrepancy_m"] = round(discrepancy, 4)
    result["identified_causes"] = causes

    # Primary cause determination
    if causes:
        primary = sorted(causes, key=lambda c: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[c["severity"]])[0]
        result["primary_cause"] = primary["cause"]
        result["primary_cause_detail"] = primary["detail"]
    else:
        result["primary_cause"] = "UNKNOWN"

    print(f"\n  DISCREPANCY: {round(discrepancy, 2)} m ({report_height}m report vs {mesh_height}m mesh)")
    print(f"\n  IDENTIFIED CAUSES:")
    for c in causes:
        print(f"    [{c['severity']}] {c['cause']}")
        print(f"        {c['detail']}")

    if causes:
        print(f"\n  PRIMARY CAUSE: {result['primary_cause']}")

    return result


def generate_final_report(audits: dict) -> dict:
    """Audit 10: Final summary report."""
    print("\n" + "=" * 60)
    print("FINAL RECONSTRUCTION AUDIT REPORT")
    print("=" * 60)

    a1 = audits["1_point_geometry"]
    a2 = audits["2_height_distribution"]
    a3 = audits["3_classification"]
    a4 = audits["4_input_vs_mesh"]
    a5 = audits["5_poisson_support"]
    a7 = audits["7_orientation_diagnostics"]
    a8 = audits["8_height_consistency"]

    # DATA QUALITY
    point_count = a1["point_count"]
    if point_count > 5000:
        data_quality = "GOOD"
    elif point_count > 1000:
        data_quality = "PARTIAL"
    else:
        data_quality = "POOR"

    # 3D COVERAGE
    diagnosis = a2.get("3d_coverage_diagnosis", "")
    if "GOOD_3D" in diagnosis:
        coverage_3d = "GOOD"
    elif "PARTIAL" in diagnosis:
        coverage_3d = "PARTIAL"
    else:
        coverage_3d = "POOR"

    # BUILDING SEGMENTATION
    veg_pct = a3.get("vegetation_like_pct", 0)
    if veg_pct < 10:
        seg_quality = "GOOD"
    elif veg_pct < 25:
        seg_quality = "PARTIAL"
    else:
        seg_quality = "POOR"

    # MESH QUALITY
    mesh_class = a7.get("mesh_classification", "")
    support_data = a5.get("interpretation", {})
    supported_pct = support_data.get("well_supported_pct", 0)

    if "COMPLETE" in mesh_class.upper() and supported_pct > 70:
        mesh_quality = "GOOD"
    elif supported_pct > 50:
        mesh_quality = "PARTIAL"
    else:
        mesh_quality = "POOR"

    # MAIN FAILURE
    causes = a8.get("identified_causes", [])
    primary_cause = a8.get("primary_cause", "UNKNOWN")
    main_failure = a8.get("primary_cause_detail", "Unable to determine")

    # If mesh is clearly contaminated, override
    if "VEGETATION" in mesh_class.upper() or "NOISY" in mesh_class.upper():
        main_failure = (f"DBSCAN cluster (eps=1.2m) merged building with surrounding vegetation/structures. "
                        f"The {point_count} 'building' points span {a1['z_range']}m vertically but include "
                        f"~{a3.get('vegetation_like_pct', 0)}% vegetation-like points. "
                        f"Poisson then interpolated across all points creating an expanded mesh "
                        f"({a4.get('z_range_difference_m', 0):+.2f}m beyond input Z range).")

    # RECOMMENDED NEXT STEP
    if "DIFFERENT_Z_REFERENCE" in primary_cause or "POISSON_INTERPOLATION" in primary_cause:
        next_step = ("Separate vegetation from building points BEFORE mesh reconstruction. "
                     "Use color-based filtering (green vegetation vs stone/plaster building surfaces) "
                     "and local planarity analysis to isolate actual building surfaces. Then reconstruct "
                     "using only verified building points.")
    elif "VEGETATION" in primary_cause:
        next_step = ("Re-segment building points using tighter DBSCAN eps or "
                     "apply vegetation filter based on local roughness + color before reconstruction.")
    else:
        next_step = ("Verify building point isolation quality. Consider manual verification "
                     "of a representative cross-section to validate automated classification.")

    report = {
        "DATA_QUALITY": data_quality,
        "3D_COVERAGE": coverage_3d,
        "BUILDING_SEGMENTATION": seg_quality,
        "MESH_QUALITY": mesh_quality,
        "MAIN_FAILURE": main_failure,
        "RECOMMENDED_NEXT_STEP": next_step,
        "mesh_classification": mesh_class,
    }

    print(f"\n  DATA QUALITY:          {data_quality}")
    print(f"  3D COVERAGE:           {coverage_3d}")
    print(f"  BUILDING SEGMENTATION: {seg_quality}")
    print(f"  MESH QUALITY:          {mesh_quality}")
    print(f"\n  MAIN FAILURE:")
    print(f"    {main_failure}")
    print(f"\n  RECOMMENDED NEXT STEP:")
    print(f"    {next_step}")

    return report


def main():
    """Execute full audit pipeline."""
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "aam_khas_bagh" / "derived"

    cloud_path = data_dir / "aam_khas_bagh_classified_cloud.json"
    mesh_meta_path = data_dir / "aam_khas_bagh_mesh_metadata.json"
    report_path = data_dir / "aam_khas_bagh_building_extraction_report.json"

    if not cloud_path.exists():
        print(f"ERROR: Classified cloud not found at {cloud_path}")
        sys.exit(1)

    print("=" * 60)
    print("AAM KHAS BAGH -- RECONSTRUCTION DATA VALIDATION AUDIT")
    print("coordinate_system: AAM_KHAS_BAGH_LOCAL")
    print("georeferenced: false")
    print("=" * 60)

    # Load data
    print("\nLoading classified point cloud...")
    building_pts, cloud_data = load_building_points_from_classified_cloud(cloud_path)
    layers = load_all_cloud_layers(cloud_data)
    print(f"  Loaded {len(building_pts)} selected building points")

    print("\nLoading mesh metadata...")
    with open(mesh_meta_path, "r", encoding="utf-8") as f:
        mesh_meta = json.load(f)
    print(f"  Mesh: {mesh_meta.get('vertex_count', 0)} vertices, {mesh_meta.get('triangle_count', 0)} triangles")

    print("\nLoading extraction report...")
    with open(report_path, "r", encoding="utf-8") as f:
        extraction_report = json.load(f)

    # Run all audits
    audits = {}
    audits["1_point_geometry"] = audit_1_point_geometry(building_pts)
    audits["2_height_distribution"] = audit_2_height_distribution(building_pts)
    audits["3_classification"] = audit_3_classification_analysis(layers, building_pts)
    audits["4_input_vs_mesh"] = audit_4_input_vs_mesh_bounds(building_pts, mesh_meta)
    audits["5_poisson_support"] = audit_5_poisson_support(mesh_meta)
    audits["6_normals"] = audit_6_normals(mesh_meta)
    audits["7_orientation_diagnostics"] = audit_7_orientation_diagnostics(building_pts, mesh_meta)
    audits["8_height_consistency"] = audit_8_height_consistency(building_pts, mesh_meta, extraction_report)

    # Final report
    audits["final_report"] = generate_final_report(audits)

    # Save output
    output = {
        "audit_title": "AAM KHAS BAGH RECONSTRUCTION DATA VALIDATION AUDIT",
        "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "georeferenced": False,
        "data_source": "aam_khas_bagh_classified_cloud.json",
        "mesh_source": "aam_khas_bagh_hammam_mesh.ply",
        "audits": audits,
    }

    output_path = data_dir / "building_point_geometry_audit.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n{'=' * 60}")
    print(f"AUDIT SAVED: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
