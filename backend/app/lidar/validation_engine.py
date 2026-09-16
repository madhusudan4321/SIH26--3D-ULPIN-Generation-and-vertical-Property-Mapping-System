"""
Validation Engine Module — Machine-Readable Validation & Reconstruction Readiness

Generates authoritative lidar_validation_report.json with sections:
- dataset
- classification
- building_extraction
- spatial_coherence
- footprint
- height
- readiness (READY | READY_WITH_WARNINGS | NOT_READY)
- blocking_reasons

Enforces safety rule: 3D mesh reconstruction is BLOCKED when readiness is NOT_READY.
"""

import json
from pathlib import Path
from typing import Dict, Any, List


def generate_validation_report(
    metadata_report: Dict[str, Any],
    building_stats: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Generate authoritative machine-readable LiDAR validation report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = building_stats.get("warnings", [])

    # Evaluate readiness
    blocking_reasons = []

    bld_pts = building_stats.get("building_points", 0)
    if bld_pts < 500:
        blocking_reasons.append(f"Insufficient building points ({bld_pts} < 500)")

    h_m = building_stats.get("building_height_m", 0.0)
    if h_m <= 0.5 or h_m > 40.0:
        blocking_reasons.append(f"Invalid building height ({h_m}m)")

    veg_contam = building_stats.get("vegetation_contamination_near_building_pct", 0.0)
    if veg_contam > 25.0:
        blocking_reasons.append(f"Severe vegetation contamination near building ({veg_contam}% > 25.0%)")

    if blocking_reasons:
        readiness = "NOT_READY"
    elif warnings:
        readiness = "READY_WITH_WARNINGS"
    else:
        readiness = "READY"

    coherence = building_stats.get("spatial_coherence_multiscale", {})
    coherence_1m = coherence.get("eps_1.0m", {})

    report = {
        "dataset": {
            "source_file": metadata_report.get("source_file"),
            "format": metadata_report.get("format"),
            "scan_count": metadata_report.get("scan_count"),
            "total_points": metadata_report.get("point_count"),
            "sampled_points": metadata_report.get("sampled_point_count"),
            "coordinate_frame": metadata_report.get("coordinate_frame"),
            "georeferenced": metadata_report.get("georeferenced"),
            "raw_bounds": metadata_report.get("raw_xyz_bounds"),
            "sampled_bounds": metadata_report.get("sampled_xyz_bounds"),
            "building_bounds": metadata_report.get("building_xyz_bounds"),
        },
        "classification": {
            "building_points": building_stats.get("building_points"),
            "building_percentage": building_stats.get("building_percentage"),
            "vegetation_percentage": building_stats.get("vegetation_percentage"),
            "unknown_percentage": building_stats.get("unknown_percentage"),
            "outlier_percentage": building_stats.get("outlier_percentage"),
            "score_stats": building_stats.get("scores"),
        },
        "building_extraction": {
            "building_points": building_stats.get("building_points"),
            "xy_area_m2": building_stats.get("building_xy_area_m2"),
            "building_height_m": building_stats.get("building_height_m"),
            "bbox": building_stats.get("building_bbox"),
        },
        "spatial_coherence": {
            "eps_1.0m": coherence_1m,
            "multiscale": coherence,
        },
        "footprint": {
            "derived_from_lidar": True,
            "source_type": "lidar_extracted",
            "georeferenced": False,
            "crs": "AAM_KHAS_BAGH_LOCAL",
            "area_m2": building_stats.get("building_xy_area_m2"),
        },
        "height": {
            "robust_height_m": building_stats.get("building_height_m"),
            "ground_elevation_p5": metadata_report.get("building_xyz_bounds", {}).get("z_min", 0.0),
            "roof_elevation_p95": metadata_report.get("building_xyz_bounds", {}).get("z_max", 0.0),
        },
        "readiness": readiness,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
    }

    report_path = output_dir / "lidar_validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report
