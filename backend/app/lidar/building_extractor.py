"""
Building Extractor Module — Validated Building-Only Point Cloud Isolation

Extracts ONLY validated BUILDING (class 3) points and generates:
- building_only.ply (Binary PLY)
- building_only.json (Flat web representation)
- building_only.geojson (Local 2D GeoJSON polygon)
- building_statistics.json (Full metrics, spatial coherence, & sanity warnings)

Executes spatial coherence testing across multiple radii (0.5m, 0.75m, 1.0m, 1.5m)
and performs automated sanity checks.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
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
from app.lidar.footprint_extractor import extract_lidar_footprint
from app.lidar.height_estimator import estimate_building_height


def analyze_spatial_coherence(bld_pts: np.ndarray, eps_radii: List[float] = [0.5, 0.75, 1.0, 1.5]) -> Dict[str, Any]:
    """Analyze building spatial connectivity across multiple neighborhood radii."""
    if len(bld_pts) == 0:
        return {}

    coherence_results = {}
    try:
        from sklearn.cluster import DBSCAN
        for eps in eps_radii:
            db = DBSCAN(eps=eps, min_samples=5, n_jobs=-1).fit(bld_pts)
            labels = db.labels_
            unique_labels = set(labels)
            if -1 in unique_labels:
                unique_labels.remove(-1)

            counts = sorted([int(np.sum(labels == l)) for l in unique_labels], reverse=True)
            comp_count = len(counts)
            largest = counts[0] if comp_count > 0 else 0
            second_largest = counts[1] if comp_count > 1 else 0

            coherence_results[f"eps_{eps}m"] = {
                "eps_m": eps,
                "component_count": comp_count,
                "largest_component": largest,
                "largest_component_pct": round((largest / len(bld_pts)) * 100, 2) if len(bld_pts) > 0 else 0.0,
                "second_largest_component": second_largest,
                "component_sizes_top5": counts[:5],
            }
    except ImportError:
        # Fallback grid estimation
        for eps in eps_radii:
            xy = bld_pts[:, :2]
            grid = np.floor(xy / eps).astype(int)
            unique_cells = len(set(tuple(row) for row in grid))
            coherence_results[f"eps_{eps}m"] = {
                "eps_m": eps,
                "component_count": unique_cells,
                "largest_component": len(bld_pts),
                "largest_component_pct": 100.0,
                "second_largest_component": 0,
            }

    return coherence_results


def export_building_only_assets(
    full_pcd: PointCloudData,
    output_dir: Path,
) -> Tuple[PointCloudData, Dict[str, Any]]:
    """
    Isolate BUILDING (class 3) points, compute statistics, export assets, and run sanity checks.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    building_pcd = full_pcd.filter_by_class(CLASS_BUILDING)
    bld_pts = building_pcd.get_xyz()

    total_pts = full_pcd.count
    bld_pts_count = building_pcd.count

    counts = full_pcd.get_class_counts()
    veg_count = counts.get("VEGETATION", 0)
    unk_count = counts.get("UNKNOWN", 0)
    out_count = counts.get("OUTLIER", 0)

    bld_pct = round((bld_pts_count / max(total_pts, 1)) * 100, 2)
    veg_pct = round((veg_count / max(total_pts, 1)) * 100, 2)
    unk_pct = round((unk_count / max(total_pts, 1)) * 100, 2)
    out_pct = round((out_count / max(total_pts, 1)) * 100, 2)

    # Footprint & Height
    if bld_pts_count >= 10:
        footprint_dict = extract_lidar_footprint(bld_pts, simplify_tolerance=0.4)
        ground_pcd = full_pcd.filter_by_class(CLASS_GROUND)
        height_dict = estimate_building_height(bld_pts, ground_pcd.get_xyz())
    else:
        footprint_dict = {"vertex_count": 0, "area_m2": 0.0, "perimeter_m": 0.0, "geometry": None}
        height_dict = {"robust_height_m": 0.0, "roof_elevation_p95": 0.0, "ground_elevation_p5": 0.0}

    # Scores statistics
    bld_scores = building_pcd.confidence
    if len(bld_scores) > 0:
        mean_s = round(float(np.mean(bld_scores)), 3)
        med_s = round(float(np.median(bld_scores)), 3)
        p05_s = round(float(np.percentile(bld_scores, 5)), 3)
        p95_s = round(float(np.percentile(bld_scores, 95)), 3)
    else:
        mean_s = med_s = p05_s = p95_s = 0.0

    # Spatial Coherence Multi-Scale Analysis
    coherence = analyze_spatial_coherence(bld_pts, eps_radii=[0.5, 0.75, 1.0, 1.5])
    coherence_1m = coherence.get("eps_1.0m", {})

    # Sanity Checks & Warnings Engine
    warnings = []
    if bld_pts_count < 500:
        warnings.append(f"Low building point count: {bld_pts_count} < 500 points")

    if footprint_dict.get("area_m2", 0.0) < 50.0:
        warnings.append(f"Small XY coverage area: {footprint_dict.get('area_m2', 0.0)}m² < 50m²")

    if unk_pct > 60.0:
        warnings.append(f"High UNKNOWN class ratio: {unk_pct}% > 60%")

    h_m = height_dict.get("height_m") or height_dict.get("robust_height_m") or 0.0
    ground_p5 = height_dict.get("ground_z", 0.0)
    roof_p95 = height_dict.get("roof_z", 0.0)
    if h_m < 1.5 or h_m > 30.0:
        warnings.append(f"Unusual building height: {h_m}m (expected 1.5m to 30.0m)")

    comp_cnt_1m = coherence_1m.get("component_count", 0)
    if comp_cnt_1m > 30:
        warnings.append(f"Highly fragmented spatial structure: {comp_cnt_1m} components at eps=1.0m")

    # Proximity vegetation contamination check
    veg_pcd = full_pcd.filter_by_class(CLASS_VEGETATION)
    veg_pts = veg_pcd.get_xyz()
    adjacent_veg_pct = 0.0
    if len(veg_pts) > 0 and len(bld_pts) > 0:
        tree_bld = KDTree(bld_pts)
        dists, _ = tree_bld.query(veg_pts, k=1)
        adjacent_veg_cnt = int(np.sum(dists < 0.30))
        adjacent_veg_pct = round((adjacent_veg_cnt / max(len(veg_pts), 1)) * 100, 2)
        if adjacent_veg_pct > 5.0:
            warnings.append(f"Vegetation contamination near building (<0.3m): {adjacent_veg_pct}% > 5.0%")

    # Statistics Dictionary
    stats = {
        "dataset_name": "Aam Khas Bagh Terrestrial LiDAR",
        "input_points": total_pts,
        "building_points": bld_pts_count,
        "building_percentage": bld_pct,
        "vegetation_percentage": veg_pct,
        "unknown_percentage": unk_pct,
        "outlier_percentage": out_pct,
        "building_bbox": building_pcd.get_bounds(),
        "building_height_m": h_m,
        "building_xy_area_m2": footprint_dict.get("area_m2", 0.0),
        "largest_component_1m": coherence_1m.get("largest_component", 0),
        "largest_component_pct_1m": coherence_1m.get("largest_component_pct", 0.0),
        "component_count_1m": comp_cnt_1m,
        "scores": {
            "mean": mean_s,
            "median": med_s,
            "p05": p05_s,
            "p95": p95_s,
        },
        "spatial_coherence_multiscale": coherence,
        "vegetation_contamination_near_building_pct": adjacent_veg_pct,
        "warnings": warnings,
    }

    # 1. Export building_statistics.json
    with open(output_dir / "building_statistics.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # 2. Export building_only.json
    with open(output_dir / "building_only.json", "w", encoding="utf-8") as f:
        json.dump(building_pcd.to_dict_flat(), f)

    # 3. Export building_only.geojson
    local_geojson = {
        "type": "FeatureCollection",
        "derived_from_lidar": True,
        "source_type": "lidar_extracted",
        "georeferenced": False,
        "crs": "AAM_KHAS_BAGH_LOCAL",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "building_id": "AAM_KHAS_BAGH_HAMMAM",
                    "height_m": h_m,
                    "area_m2": footprint_dict.get("area_m2", 0.0),
                    "perimeter_m": footprint_dict.get("perimeter_m", 0.0),
                    "derived_from_lidar": True,
                    "source_type": "lidar_extracted",
                    "georeferenced": False,
                },
                "geometry": footprint_dict.get("geometry"),
            }
        ],
    }
    with open(output_dir / "building_only.geojson", "w", encoding="utf-8") as f:
        json.dump(local_geojson, f, indent=2)

    # 4. Export building_only.ply (Binary PLY)
    save_binary_ply(output_dir / "building_only.ply", building_pcd)

    return building_pcd, stats


def save_binary_ply(ply_path: Path, pcd: PointCloudData):
    """Write PointCloudData as binary PLY format."""
    count = pcd.count
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {count}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    )

    with open(ply_path, "wb") as f:
        f.write(header.encode("ascii"))
        if count > 0:
            dtype = np.dtype([
                ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                ("r", "u1"), ("g", "u1"), ("b", "u1")
            ])
            arr = np.zeros(count, dtype=dtype)
            arr["x"] = pcd.x.astype(np.float32)
            arr["y"] = pcd.y.astype(np.float32)
            arr["z"] = pcd.z.astype(np.float32)
            arr["r"] = pcd.r
            arr["g"] = pcd.g
            arr["b"] = pcd.b
            f.write(arr.tobytes())
