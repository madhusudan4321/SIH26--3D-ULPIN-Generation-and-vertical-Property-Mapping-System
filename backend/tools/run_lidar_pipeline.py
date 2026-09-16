"""
Run LiDAR Pipeline Tool — End-to-End LiDAR Processing Pipeline Runner

Executes the production LiDAR pipeline on Aam Khas Bagh E57 dataset:
1. E57 sampling & metadata extraction
2. Voxel grid downsampling (0.10m)
3. Standardized PointCloudData construction
4. Ground & 5-class multi-feature classification (Ground, Vegetation, Building, Unknown, Outlier)
5. Building-only point cloud extraction & spatial coherence analysis
6. Footprint & height estimation
7. Validation report generation (lidar_validation_report.json)
8. Reconstruction safety check: Mesh generation consuming ONLY validated building-only points

Usage:
    python backend/tools/run_lidar_pipeline.py
"""

import sys
import json
from pathlib import Path
import numpy as np

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.lidar.e57_sampler import sample_e57_point_cloud
from app.lidar.point_cloud_downsampler import voxel_grid_downsample
from app.lidar.point_cloud_data import PointCloudData
from app.lidar.metadata_validator import validate_dataset_metadata
from app.lidar.classification_pipeline import run_classification_pipeline, LidarClassificationConfig
from app.lidar.building_extractor import export_building_only_assets
from app.lidar.validation_engine import generate_validation_report
from app.lidar.mesh_reconstructor import reconstruct_building_mesh


def run_pipeline():
    print("=== STEP 1: LOCATING E57 DATASET & OUTPUT DIRECTORY ===")
    root_dir = backend_dir.parent
    e57_path = root_dir / "data" / "aam_khas_bagh" / "lidar" / "7csx-ne47_terresterial_lidar.e57"
    if not e57_path.exists():
        e57_path = backend_dir / "data" / "aam_khas_bagh" / "lidar" / "7csx-ne47_terresterial_lidar.e57"

    if not e57_path.exists():
        raise FileNotFoundError(f"E57 file not found at: {e57_path}")

    derived_dir = root_dir / "data" / "aam_khas_bagh" / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    print(f"Dataset path: {e57_path.name}")
    print(f"Output directory: {derived_dir}")

    print("\n=== STEP 2: SAMPLING POINT CLOUD (250,000 pts) ===")
    sampled = sample_e57_point_cloud(str(e57_path), target_points=250000)

    # Reconstruct NumPy arrays [N, 3] XYZ, [N, 3] RGB, [N] scan_indices
    all_pts = []
    all_colors = []
    all_scans = []

    for sc in sampled.get("scans", []):
        s_idx = sc["scan_index"]
        pts_flat = sc["points"]
        num_pts = len(pts_flat) // 6
        for i in range(num_pts):
            base = i * 6
            x, y, z = pts_flat[base], pts_flat[base+1], pts_flat[base+2]
            r, g, b = pts_flat[base+3], pts_flat[base+4], pts_flat[base+5]
            all_pts.append([x, y, z])
            all_colors.append([r, g, b])
            all_scans.append(s_idx)

    pts_np = np.array(all_pts, dtype=np.float64)
    colors_np = np.array(all_colors, dtype=np.uint8)
    scans_np = np.array(all_scans, dtype=int)
    print(f"Sampled {len(pts_np):,} local Cartesian points.")

    print("\n=== STEP 3: VOXEL GRID DOWNSAMPLING (0.10m Voxel Size) ===")
    ds_pts, ds_colors, ds_scans = voxel_grid_downsample(pts_np, voxel_size=0.10, colors=colors_np, scan_indices=scans_np)
    print(f"Downsampled to {len(ds_pts):,} voxel centroids.")

    print("\n=== STEP 4: CONSTRUCTING STANDARDIZED PointCloudData ===")
    pcd = PointCloudData.from_arrays(
        pts=ds_pts,
        colors=ds_colors,
        scans=ds_scans,
    )

    print("\n=== STEP 5: RUNNING 5-CLASS CLASSIFICATION PIPELINE ===")
    config = LidarClassificationConfig(
        voxel_size=0.10,
        ground_cell_size=1.5,
        ground_height_threshold=0.35,
        building_threshold=0.65,
        vegetation_threshold=0.30,
    )
    classified_pcd = run_classification_pipeline(pcd, config)
    counts = classified_pcd.get_class_counts()
    print("Classification Distribution:")
    for cls_name, cnt in counts.items():
        pct = round(cnt / classified_pcd.count * 100, 2)
        print(f"  - {cls_name:12s}: {cnt:6,} pts ({pct:5.2f}%)")

    print("\n=== STEP 6: ISOLATING BUILDING-ONLY POINTS & SPATIAL COHERENCE ===")
    bld_pcd, bld_stats = export_building_only_assets(classified_pcd, derived_dir)
    print(f"Isolated {bld_pcd.count:,} BUILDING points.")
    print(f"Building Height: {bld_stats['building_height_m']}m")
    print(f"Building Footprint Area: {bld_stats['building_xy_area_m2']}m²")
    print(f"Largest Component (1.0m): {bld_stats['largest_component_1m']} pts ({bld_stats['largest_component_pct_1m']}%)")
    if bld_stats["warnings"]:
        print("Sanity Warnings:")
        for w in bld_stats["warnings"]:
            print(f"  [WARNING] {w}")

    print("\n=== STEP 7: METADATA & VALIDATION REPORT GENERATION ===")
    meta_report = validate_dataset_metadata(str(e57_path), sampled_pcd=pcd, building_pcd=bld_pcd)
    val_report = generate_validation_report(meta_report, bld_stats, derived_dir)
    readiness = val_report["readiness"]
    print(f"RECONSTRUCTION READINESS STATUS: >>> {readiness} <<<")

    print("\n=== STEP 8: RECONSTRUCTION SAFETY CHECK ===")
    if readiness == "NOT_READY":
        print("[BLOCKED] RECONSTRUCTION BLOCKED: Dataset failed validation readiness check.")
        print(f"Blocking reasons: {val_report['blocking_reasons']}")
        sys.exit(1)

    print("[APPROVED] READINESS APPROVED. Generating 3D Mesh using ONLY validated BUILDING points...")
    bld_pts_np = bld_pcd.get_xyz()
    mesh_meta = reconstruct_building_mesh(
        building_points=bld_pts_np,
        output_dir=derived_dir,
        source_file=e57_path.name,
    )

    print("\n=== PIPELINE EXECUTION COMPLETE ===")
    print(f"Reconstruction Method: {mesh_meta.get('reconstruction_method')}")
    print(f"Mesh Vertices: {mesh_meta.get('vertex_count'):,}")
    print(f"Mesh Triangles: {mesh_meta.get('triangle_count'):,}")
    print(f"Validation Report: {derived_dir / 'lidar_validation_report.json'}")


if __name__ == "__main__":
    run_pipeline()
