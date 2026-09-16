"""
Photogrammetry Pipeline CLI Tool

Usage:
  python backend/tools/run_photogrammetry_pipeline.py \
    --dataset medanta_drone \
    --images data/sample/drone_images \
    --matcher exhaustive \
    --camera-model SIMPLE_RADIAL \
    --single-camera \
    --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.photogrammetry.pipeline import run_photogrammetry_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("photogrammetry_cli")


def main():
    parser = argparse.ArgumentParser(description="3D ULPIN Drone Photogrammetry Processing Tool")
    parser.add_argument("--dataset", required=True, help="Name of the dataset (e.g. medanta_drone)")
    parser.add_argument("--images", required=True, help="Path to directory containing drone images")
    parser.add_argument("--matcher", default="exhaustive", choices=["exhaustive", "sequential", "spatial", "auto"], help="COLMAP feature matcher algorithm")
    parser.add_argument("--camera-model", default="SIMPLE_RADIAL", help="COLMAP camera model (e.g. SIMPLE_RADIAL, PINHOLE, OPENCV)")
    parser.add_argument("--single-camera", action="store_true", default=None, help="Treat all images as taken by a single camera")
    parser.add_argument("--colmap-path", default=None, help="Explicit path to COLMAP binary executable")
    parser.add_argument("--dry-run", action="store_true", help="Run discovery, EXIF extraction, and validation without running COLMAP SfM/MVS")
    parser.add_argument("--voxel-size", type=float, default=0.05, help="Voxel downsampling size in meters for Open3D (default: 0.05)")

    args = parser.parse_args()

    images_path = Path(args.images).resolve()
    colmap_bin = Path(args.colmap_path).resolve() if args.colmap_path else None

    logger.info(f"Starting photogrammetry CLI run for dataset '{args.dataset}'")
    logger.info(f"Images path: {images_path}")
    logger.info(f"Dry run mode: {args.dry_run}")

    report = run_photogrammetry_pipeline(
        dataset_name=args.dataset,
        images_dir=images_path,
        matcher=args.matcher,
        camera_model=args.camera_model,
        single_camera=args.single_camera,
        colmap_path=colmap_bin,
        dry_run=args.dry_run,
        voxel_size=args.voxel_size,
    )

    print("\n" + "=" * 60)
    print("PHOTOGRAMMETRY PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Dataset:            {report['dataset']['name']}")
    print(f"Status:             {report['dataset']['pipeline_status']}")
    print(f"Readiness:          {report['readiness']}")
    print(f"Discovered Images:  {report['images']['total_discovered']} ({report['images']['valid']} valid, {report['images']['warning']} warning, {report['images']['invalid']} invalid)")
    print(f"GPS Available:      {report['exif']['gps_metadata_available']} ({report['exif']['gps_image_count']} images)")
    print(f"Coordinate Frame:   {report['georeferencing']['coordinate_frame']}")
    print(f"COLMAP Installed:   {report['colmap']['installed']} (Version: {report['colmap']['version'] or 'N/A'}, CUDA: {report['colmap']['cuda_available']})")
    print(f"SfM Registered:     {report['sfm'].get('registered_images', 0)} / {report['sfm'].get('total_images', 0)} ({report['sfm'].get('registration_percentage', 0.0)}%)")
    print(f"Mean Reproj Error:  {report['sfm'].get('mean_reprojection_error_px', 0.0)} px")
    print(f"Dense Point Count:  {report['pointcloud'].get('processed_point_count', 0)}")

    if report.get("blocking_reasons"):
        print("\nBLOCKING REASONS:")
        for r in report["blocking_reasons"]:
            print(f"  [X] {r}")

    if report.get("warnings"):
        print("\nWARNINGS:")
        for w in report["warnings"]:
            print(f"  [!] {w}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
