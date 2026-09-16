"""
Photogrammetry Validation & Readiness Evaluation Module

Consolidates ingestion, quality validation, EXIF/GPS, SfM, MVS, and point cloud results
into a single machine-readable validation report:
`reports/photogrammetry_validation_report.json`.

Determines pipeline readiness: READY, READY_WITH_WARNINGS, or NOT_READY.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def generate_validation_report(
    dataset_name: str,
    images_dir: Path,
    pipeline_status: str,
    image_report: Dict[str, Any],
    exif_summary: Dict[str, Any],
    colmap_config_info: Dict[str, Any],
    sfm_metrics: Dict[str, Any],
    colmap_run_results: Dict[str, Any],
    pointcloud_stats: Dict[str, Any],
    reports_dir: Path,
) -> Dict[str, Any]:
    """
    Generate unified validation report and compute readiness status.

    Returns:
        dict: Photogrammetry validation report.
    """
    blocking_reasons: List[str] = []
    warnings: List[str] = []

    # 1. Ingestion checks
    total_imgs = image_report.get("total_discovered", 0)
    valid_imgs = image_report.get("valid", 0)
    warn_imgs = image_report.get("warning", 0)
    inv_imgs = image_report.get("invalid", 0)

    if total_imgs == 0:
        blocking_reasons.append("Zero images discovered in target directory.")
    if inv_imgs > 0:
        warnings.append(f"{inv_imgs} corrupted or unreadable images were detected and excluded.")
    if warn_imgs > 0:
        warnings.append(f"{warn_imgs} images flagged with quality warnings (blur, exposure, or duplicate).")

    # 2. EXIF / GPS checks
    has_gps = exif_summary.get("gps_metadata_available", False)
    if not has_gps:
        warnings.append("No EXIF GPS metadata detected in images. Photogrammetry cloud is in PHOTOGRAMMETRIC_LOCAL frame.")

    # 3. COLMAP availability & execution checks
    colmap_installed = colmap_config_info.get("installed", False)
    cuda_available = colmap_config_info.get("cuda_available", False)

    if not colmap_installed and pipeline_status != "DRY_RUN":
        blocking_reasons.append("COLMAP binary is not installed or not found on PATH.")

    if not cuda_available:
        warnings.append("NVIDIA CUDA GPU not detected. MVS stage skipped; sparse point cloud only.")

    # 4. SfM checks
    reg_pct = sfm_metrics.get("registration_percentage", 0.0)
    mean_reproj = sfm_metrics.get("mean_reprojection_error_px", 0.0)
    largest_comp_pct = sfm_metrics.get("largest_component_percentage", 0.0)
    sparse_pts = sfm_metrics.get("sparse_points", 0)

    if pipeline_status not in ["DRY_RUN", "WAITING_FOR_IMAGES", "COLMAP_NOT_INSTALLED"]:
        if reg_pct < 60.0:
            blocking_reasons.append(f"Low SfM image registration rate ({reg_pct:.1f}% < 60.0%).")
        elif reg_pct < 80.0:
            warnings.append(f"Suboptimal image registration rate ({reg_pct:.1f}% < 80.0%).")

        if mean_reproj > 4.0:
            blocking_reasons.append(f"Excessive mean reprojection error ({mean_reproj:.2f}px > 4.0px).")
        elif mean_reproj > 1.5:
            warnings.append(f"Elevated mean reprojection error ({mean_reproj:.2f}px > 1.5px).")

        if largest_comp_pct < 50.0:
            blocking_reasons.append(f"Severe reconstruction fragmentation ({largest_comp_pct:.1f}% in main component).")

    # 5. Point cloud checks
    dense_count = pointcloud_stats.get("processed_point_count", 0)
    mvs_status = colmap_run_results.get("mvs_status", "NOT_RUN")

    # Compute Readiness
    if pipeline_status == "DRY_RUN":
        readiness = "NOT_READY"
        warnings.append("Pipeline executed in dry-run mode. No reconstruction artifacts generated.")
    elif blocking_reasons:
        readiness = "NOT_READY"
    elif warnings or mvs_status == "SKIPPED_NO_CUDA" or reg_pct < 80.0:
        readiness = "READY_WITH_WARNINGS"
    else:
        readiness = "READY"

    # Assemble report schema
    report = {
        "dataset": {
            "name": dataset_name,
            "image_directory": str(images_dir),
            "pipeline_status": pipeline_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "images": {
            "total_discovered": total_imgs,
            "valid": valid_imgs,
            "warning": warn_imgs,
            "invalid": inv_imgs,
            "resolution_range": image_report.get("resolution_range", {}),
            "mean_sharpness_score": image_report.get("mean_sharpness_score", 0.0),
        },
        "exif": {
            "cameras_detected": exif_summary.get("cameras_detected", []),
            "gps_metadata_available": has_gps,
            "gps_image_count": exif_summary.get("gps_image_count", 0),
            "gps_image_percentage": exif_summary.get("gps_image_percentage", 0.0),
        },
        "georeferencing": exif_summary.get("georeferencing", {
            "photogrammetry_georeferenced": False,
            "coordinate_frame": "PHOTOGRAMMETRIC_LOCAL",
            "crs": None,
            "note": "EXIF GPS metadata present but does NOT constitute authoritative georeferencing.",
        }),
        "colmap": {
            "installed": colmap_installed,
            "version": colmap_config_info.get("version"),
            "cuda_available": cuda_available,
            "colmap_path": colmap_config_info.get("colmap_bin"),
        },
        "sfm": sfm_metrics,
        "mvs": {
            "status": mvs_status,
            "dense_point_count": dense_count,
            "dense_ply_path": pointcloud_stats.get("processed_ply_path"),
        },
        "pointcloud": pointcloud_stats,
        "readiness": readiness,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
    }

    # Save validation report
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "photogrammetry_validation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Validation report generated. Overall readiness: {readiness}.")
    return report
