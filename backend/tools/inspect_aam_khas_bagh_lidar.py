"""
Aam Khas Bagh LiDAR Local Inspection Script (Phase 1 & Phase 2)

Utility script to inspect read-only E57 point cloud dataset for Aam Khas Bagh,
read scan poses, extract sampled local point cloud (~1,000,000 points), and
generate `backend/tools/aam_khas_bagh_lidar_report.json`.

Usage:
  python backend/tools/inspect_aam_khas_bagh_lidar.py
"""

import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.lidar.e57_reader import read_e57_scan_headers
from app.lidar.e57_sampler import sample_e57_point_cloud
from app.lidar.lidar_metadata import DEFAULT_GEOREFERENCING_CONFIG


def run_inspection(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"E57 dataset not found at {file_path}")

    print(f"=== PHASE 1: INSPECTING E57 DATASET: {path.name} ===")
    headers_info = read_e57_scan_headers(str(path))

    print(f"File Size: {headers_info['file_size_gb']} GB")
    print(f"Scan Count: {headers_info['scan_count']}")
    print(f"Total Points: {headers_info['total_points']:,}")
    print(f"Registered Poses: {headers_info['registered']}")

    print("\n=== PHASE 1: SAMPLING LIGHTWEIGHT POINT CLOUD (TARGET ~150K POINTS FOR INSTANT PREVIEW) ===")
    sampled_data = sample_e57_point_cloud(str(path), target_points=150000)

    print(f"Sampled Points: {sampled_data['sampled_points']:,} (Stride Step: {sampled_data['stride_step']})")
    print(f"Local Bounds: X[{sampled_data['coordinate_bounds']['x_min']} to {sampled_data['coordinate_bounds']['x_max']}], Y[{sampled_data['coordinate_bounds']['y_min']} to {sampled_data['coordinate_bounds']['y_max']}], Z[{sampled_data['coordinate_bounds']['z_min']} to {sampled_data['coordinate_bounds']['z_max']}]")

    # Format Phase 2 Report JSON
    scan_transforms = []
    scanner_positions = []

    for s in headers_info["scans"]:
        idx = s["scan_index"]
        t = s["translation_m"]
        rot_q = s["rotation_quaternion"]
        rot_m = s["rotation_matrix"]

        scanner_positions.append({
            "scan_index": idx,
            "position_m": t,
        })

        scan_transforms.append({
            "scan_index": idx,
            "guid": s["guid"],
            "translation_m": t,
            "rotation_quaternion": rot_q,
            "rotation_matrix": rot_m,
        })

    report = {
        "file": path.name,
        "file_size_gb": headers_info["file_size_gb"],
        "scan_count": headers_info["scan_count"],
        "total_points": headers_info["total_points"],
        "coordinate_system": "local",
        "crs": None,
        "registered": headers_info["registered"],
        "bounds": sampled_data["coordinate_bounds"],
        "sampled_points": sampled_data["sampled_points"],
        "stride_step": sampled_data["stride_step"],
        "scanner_positions": scanner_positions,
        "scan_transforms": scan_transforms,
        "lidar_georeferencing": DEFAULT_GEOREFERENCING_CONFIG,
    }

    # Save Phase 2 Report JSON to backend/tools/aam_khas_bagh_lidar_report.json
    out_dir = backend_dir / "tools"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "aam_khas_bagh_lidar_report.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n=== PHASE 2: REPORT SAVED TO {report_file} ===")

    # Also save sampled points JSON asset for Phase 3 Local Coordinate Viewer
    sampled_asset_file = out_dir / "aam_khas_bagh_sampled_points.json"
    with open(sampled_asset_file, "w", encoding="utf-8") as f:
        json.dump(sampled_data, f)

    print(f"=== PHASE 3: SAMPLED POINT CLOUD ASSET SAVED TO {sampled_asset_file} ({round(sampled_asset_file.stat().st_size / (1024 * 1024), 2)} MB) ===")

    return report


def main():
    default_path = Path("d:/SIH26- 3D ULPIN Generation and vertical Property Mapping System/data/aam_khas_bagh/lidar/7csx-ne47_terresterial_lidar.e57")
    if len(sys.argv) > 1:
        e57_path = Path(sys.argv[1])
    else:
        e57_path = default_path

    run_inspection(str(e57_path))


if __name__ == "__main__":
    main()
