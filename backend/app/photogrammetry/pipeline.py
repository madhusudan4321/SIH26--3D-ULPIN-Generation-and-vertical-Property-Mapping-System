"""
Photogrammetry Pipeline Orchestrator

Top-level entry point orchestrating end-to-end drone image photogrammetry:
1. Load PhotogrammetryConfig
2. Image discovery & manifest generation (image_ingestion.py)
3. Image quality, sharpness, brightness & duplicate validation (image_validation.py)
4. EXIF & GPS metadata extraction (exif.py)
5. COLMAP SfM & MVS execution wrapper (colmap_runner.py)
6. Sparse reconstruction metric parsing (sfm.py)
7. Open3D dense point cloud filtering & downsampling (pointcloud.py)
8. Readiness assessment & unified validation report (validation.py)

Supports --dry-run mode: validates images/EXIF/COLMAP availability without generating fake models.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .config import PhotogrammetryConfig
from .image_ingestion import discover_images
from .image_validation import validate_images
from .exif import process_dataset_exif
from .colmap_runner import run_colmap_pipeline
from .sfm import parse_sparse_model
from .pointcloud import process_dense_pointcloud
from .validation import generate_validation_report

logger = logging.getLogger(__name__)


def run_photogrammetry_pipeline(
    dataset_name: str,
    images_dir: Path,
    base_data_dir: Optional[Path] = None,
    matcher: str = "exhaustive",
    camera_model: str = "SIMPLE_RADIAL",
    single_camera: Optional[bool] = None,
    colmap_path: Optional[Path] = None,
    dry_run: bool = False,
    voxel_size: Optional[float] = 0.05,
) -> Dict[str, Any]:
    """
    Execute full photogrammetry pipeline.

    Returns:
        dict: Complete pipeline validation report.
    """
    logger.info(f"Starting photogrammetry pipeline for dataset '{dataset_name}' (dry_run={dry_run})...")

    # 1. Initialize Configuration
    config = PhotogrammetryConfig(
        dataset_name=dataset_name,
        base_data_dir=base_data_dir,
        matcher=matcher,
        camera_model=camera_model,
        single_camera=single_camera if single_camera is not None else True,
        colmap_bin_path=colmap_path,
        dry_run=dry_run,
    )

    colmap_info = {
        "installed": config.colmap_installed,
        "version": config.colmap_version,
        "cuda_available": config.cuda_available,
        "colmap_bin": str(config.colmap_bin) if config.colmap_bin else None,
    }

    # 2. Image Discovery & Manifest Generation
    manifest = discover_images(
        images_dir=images_dir,
        dataset_name=dataset_name,
        reports_dir=config.reports_dir,
    )

    total_images = manifest.get("total_discovered", 0)
    if total_images == 0:
        logger.warning(f"No valid images found in {images_dir}.")
        pipeline_status = "WAITING_FOR_IMAGES"
        empty_report = {
            "dataset_name": dataset_name,
            "total_discovered": 0,
            "valid": 0,
            "warning": 0,
            "invalid": 0,
            "mean_sharpness_score": 0.0,
            "resolution_range": {},
            "images": [],
        }
        empty_exif = {
            "dataset_name": dataset_name,
            "total_images": 0,
            "cameras_detected": [],
            "single_camera_consistent": True,
            "gps_metadata_available": False,
            "gps_image_count": 0,
            "gps_image_percentage": 0.0,
            "georeferencing": {
                "photogrammetry_georeferenced": False,
                "coordinate_frame": "PHOTOGRAMMETRIC_LOCAL",
                "crs": None,
                "note": "No images available.",
            },
            "exif_details": [],
        }
        empty_sfm = {"model_exists": False, "registered_images": 0}
        empty_colmap = {"status": "WAITING_FOR_IMAGES", "mvs_status": "NOT_RUN"}
        empty_pts = {"status": "NOT_RUN", "processed_point_count": 0}

        return generate_validation_report(
            dataset_name=dataset_name,
            images_dir=images_dir,
            pipeline_status=pipeline_status,
            image_report=empty_report,
            exif_summary=empty_exif,
            colmap_config_info=colmap_info,
            sfm_metrics=empty_sfm,
            colmap_run_results=empty_colmap,
            pointcloud_stats=empty_pts,
            reports_dir=config.reports_dir,
        )

    # 3. Image Validation (Sharpness, exposure, duplicates)
    image_report = validate_images(
        manifest=manifest,
        reports_dir=config.reports_dir,
        workspace_dir=config.workspace_dir,
    )

    # 4. EXIF & GPS Extraction
    exif_summary = process_dataset_exif(
        manifest=manifest,
        reports_dir=config.reports_dir,
    )

    # Determine single camera override if not specified
    if single_camera is None:
        single_camera = exif_summary.get("single_camera_consistent", True)

    # 5. COLMAP Reconstruction (SfM + MVS)
    colmap_results = run_colmap_pipeline(
        config=config,
        images_dir=images_dir,
        image_list_path=Path(image_report["image_list_path"]) if image_report.get("image_list_path") else None,
        single_camera=single_camera,
    )

    pipeline_status = colmap_results.get("status", "NOT_RUN")

    # 6. Parse SfM Sparse Metrics
    sfm_metrics = parse_sparse_model(
        sparse_dir=config.sparse_dir,
        total_discovered_images=total_images,
    )

    # 7. Process Dense Point Cloud with Open3D
    fused_ply = config.dense_dir / "fused.ply"
    pointcloud_stats = process_dense_pointcloud(
        dense_ply_path=fused_ply,
        derived_dir=config.derived_dir,
        voxel_size=voxel_size,
    )

    # 8. Unified Validation Report
    report = generate_validation_report(
        dataset_name=dataset_name,
        images_dir=images_dir,
        pipeline_status=pipeline_status,
        image_report=image_report,
        exif_summary=exif_summary,
        colmap_config_info=colmap_info,
        sfm_metrics=sfm_metrics,
        colmap_run_results=colmap_results,
        pointcloud_stats=pointcloud_stats,
        reports_dir=config.reports_dir,
    )

    logger.info(f"Photogrammetry pipeline for dataset '{dataset_name}' complete.")
    return report
