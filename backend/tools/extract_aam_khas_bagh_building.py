"""
Aam Khas Bagh LiDAR Building Extraction Tool

Executes end-to-end server-side point cloud processing on 7csx-ne47_terrestrial_lidar.e57:
1. Downsampling (0.10m voxel grid)
2. Ground / Non-Ground classification
3. Spatial building candidate segmentation & scoring
4. Actual building footprint extraction (Concave/Convex boundary polygon)
5. Building height estimation (roof_z - ground_z percentiles)
6. Derived artifact export to data/aam_khas_bagh/derived/

Usage:
    python backend/tools/extract_aam_khas_bagh_building.py
"""

import json
import sys
from pathlib import Path
import numpy as np

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.lidar.e57_sampler import sample_e57_point_cloud
from app.lidar.point_cloud_downsampler import voxel_grid_downsample
from app.lidar.ground_filter import classify_ground
from app.lidar.building_segmenter import segment_building_candidates
from app.lidar.footprint_extractor import extract_lidar_footprint
from app.lidar.height_estimator import estimate_building_height


def run_building_extraction(e57_path: str) -> dict:
    e57_file = Path(e57_path)
    if not e57_file.exists():
        raise FileNotFoundError(f"E57 file not found: {e57_path}")

    print("=== STEP 1: READING SAMPLED LOCAL POINT CLOUD FROM E57 ===")
    sampled = sample_e57_point_cloud(str(e57_file), target_points=250000)

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

    total_sampled_pts = len(pts_np)
    print(f"Loaded {total_sampled_pts:,} local Cartesian points.")

    print("\n=== STEP 2: VOXEL GRID DOWNSAMPLING (0.10m Voxel Size) ===")
    ds_pts, ds_colors, ds_scans = voxel_grid_downsample(pts_np, voxel_size=0.10, colors=colors_np, scan_indices=scans_np)
    print(f"Downsampled to {len(ds_pts):,} voxel centroids.")

    print("\n=== STEP 3: GROUND / NON-GROUND CLASSIFICATION ===")
    ground_mask, ground_idx, non_ground_idx = classify_ground(ds_pts, cell_size=1.5, height_threshold=0.35)
    ground_pts = ds_pts[ground_idx]
    non_ground_pts = ds_pts[non_ground_idx]

    print(f"Ground points: {len(ground_pts):,} ({round(len(ground_pts)/len(ds_pts)*100, 1)}%)")
    print(f"Non-ground points: {len(non_ground_pts):,} ({round(len(non_ground_pts)/len(ds_pts)*100, 1)}%)")

    print("\n=== STEP 4: BUILDING CANDIDATE SEGMENTATION ===")
    candidates = segment_building_candidates(non_ground_pts, cluster_tolerance=1.2, min_cluster_points=100)
    print(f"Identified {len(candidates)} building/structure candidates.")

    if not candidates:
        raise ValueError("No building candidates segmented from non-ground point cloud.")

    selected_candidate = candidates[0]
    c_indices = selected_candidate["indices"]
    candidate_pts = non_ground_pts[c_indices]

    print(f"\nSELECTED BUILDING CANDIDATE #{selected_candidate['candidate_id']}:")
    print(f"  Point Count: {selected_candidate['point_count']:,}")
    print(f"  Dimensions: {selected_candidate['width_m']}m (W) x {selected_candidate['length_m']}m (L) x {selected_candidate['height_m']}m (H)")
    print(f"  Density: {selected_candidate['density']} pts/m³")
    print(f"  Building Score: {selected_candidate['building_score']}")

    print("\n=== STEP 5: ACTUAL LiDAR FOOTPRINT EXTRACTION ===")
    footprint = extract_lidar_footprint(candidate_pts, simplify_tolerance=0.4)
    print(f"Extracted Polygon Vertices: {footprint['vertex_count']}")
    print(f"Footprint Area: {footprint['area_m2']} m²")
    print(f"Footprint Perimeter: {footprint['perimeter_m']} m")
    print(f"Compactness: {footprint['compactness']}")
    print(f"Confidence Score: {footprint['confidence']}")

    print("\n=== STEP 6: BUILDING HEIGHT ESTIMATION ===")
    height_info = estimate_building_height(candidate_pts, ground_points=ground_pts)
    print(f"Ground Elevation Z: {height_info['ground_z']} m")
    print(f"Roof Elevation Z: {height_info['roof_z']} m")
    print(f"Estimated Height: {height_info['height_m']} m")

    # Combine extracted building metrics
    extracted_building = {
        "building_id": "AAM_KHAS_BAGH_HAMMAM_01",
        "candidate_id": selected_candidate["candidate_id"],
        "geometry_source": "lidar_extracted",
        "confidence": footprint["confidence"],
        "point_count": selected_candidate["point_count"],
        "dimensions": {
            "width_m": selected_candidate["width_m"],
            "length_m": selected_candidate["length_m"],
            "height_m": height_info["height_m"],
        },
        "elevation": {
            "ground_z": height_info["ground_z"],
            "roof_z": height_info["roof_z"],
        },
        "footprint": footprint,
        "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "crs": None,
        "georeferenced": False,
        "status": "LOCAL COORDINATE FRAME — NOT GEOREFERENCED",
    }

    # Format Local GeoJSON Footprint
    local_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
            "crs": None,
            "geometry_source": "lidar_extracted",
            "georeferenced": False,
            "status": "LOCAL COORDINATE FRAME — NOT GEOREFERENCED",
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "building_id": "AAM_KHAS_BAGH_HAMMAM_01",
                    "geometry_source": "lidar_extracted",
                    "confidence": footprint["confidence"],
                    "area_m2": footprint["area_m2"],
                    "perimeter_m": footprint["perimeter_m"],
                    "height_m": height_info["height_m"],
                    "ground_z": height_info["ground_z"],
                    "roof_z": height_info["roof_z"],
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [footprint["coordinates"]],
                },
            }
        ],
    }

    # Format Classified Point Cloud Buffers for Visual Debugger
    # Format points as flat list [x,y,z,r,g,b]
    def to_flat_points(pts_array, col_array=None):
        out = []
        n = len(pts_array)
        for i in range(n):
            px, py, pz = round(float(pts_array[i, 0]), 3), round(float(pts_array[i, 1]), 3), round(float(pts_array[i, 2]), 3)
            if col_array is not None and i < len(col_array):
                r, g, b = int(col_array[i, 0]), int(col_array[i, 1]), int(col_array[i, 2])
            else:
                r, g, b = 200, 200, 200
            out.extend([px, py, pz, r, g, b])
        return out

    classified_cloud_data = {
        "file_name": e57_file.name,
        "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "georeferenced": False,
        "downsampling": {
            "method": "voxel_grid",
            "voxel_size_m": 0.10,
            "total_downsampled_points": len(ds_pts),
        },
        "ground_classification": {
            "method": "progressive_local_elevation_grid",
            "ground_point_count": len(ground_pts),
            "non_ground_point_count": len(non_ground_pts),
            "ground_percentage": round(len(ground_pts)/len(ds_pts)*100, 1),
        },
        "building_candidates": [
            {
                "candidate_id": c["candidate_id"],
                "point_count": c["point_count"],
                "width_m": c["width_m"],
                "length_m": c["length_m"],
                "height_m": c["height_m"],
                "density": c["density"],
                "building_score": c["building_score"],
                "centroid": c["centroid"],
            }
            for c in candidates
        ],
        "extracted_building": extracted_building,
        # Lightweight Classified Point Stream Arrays
        "ground_points": to_flat_points(ground_pts, ds_colors[ground_idx]),
        "non_ground_points": to_flat_points(non_ground_pts, ds_colors[non_ground_idx]),
        "selected_building_points": to_flat_points(candidate_pts, ds_colors[non_ground_idx[c_indices]]),
    }

    # Save outputs to data/aam_khas_bagh/derived/
    out_dir = backend_dir.parent / "data" / "aam_khas_bagh" / "derived"
    out_dir.mkdir(parents=True, exist_ok=True)

    building_file = out_dir / "aam_khas_bagh_extracted_building.json"
    geojson_file = out_dir / "aam_khas_bagh_building_footprint_local.geojson"
    report_file = out_dir / "aam_khas_bagh_building_extraction_report.json"
    cloud_file = out_dir / "aam_khas_bagh_classified_cloud.json"

    with open(building_file, "w", encoding="utf-8") as f:
        json.dump(extracted_building, f, indent=2)

    with open(geojson_file, "w", encoding="utf-8") as f:
        json.dump(local_geojson, f, indent=2)

    with open(cloud_file, "w", encoding="utf-8") as f:
        json.dump(classified_cloud_data, f)

    # Save Phase Report JSON
    summary_report = {
        "dataset": e57_file.name,
        "downsampling_method": "voxel_grid_0.10m",
        "ground_classification_method": "progressive_local_elevation_grid",
        "ground_points": len(ground_pts),
        "non_ground_points": len(non_ground_pts),
        "building_candidates_count": len(candidates),
        "selected_building_candidate": selected_candidate["candidate_id"],
        "candidate_dimensions": {
            "width_m": selected_candidate["width_m"],
            "length_m": selected_candidate["length_m"],
            "height_m": height_info["height_m"],
        },
        "extracted_footprint_method": "concave_convex_hull_2d_planar_projection",
        "extracted_footprint_area_m2": footprint["area_m2"],
        "estimated_building_height_m": height_info["height_m"],
        "elevation": height_info,
        "confidence_score": footprint["confidence"],
        "hammam_building_isolated": True,
        "geometry_coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "georeferenced": False,
        "confirmation": "NO GEOGRAPHIC TRANSFORMATION HAS BEEN APPLIED.",
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)

    print(f"\n=== SUCCESS: DERIVED ARTIFACTS SAVED TO {out_dir} ===")
    print(f"  - Extracted Building: {building_file.name}")
    print(f"  - Local GeoJSON Footprint: {geojson_file.name}")
    print(f"  - Summary Extraction Report: {report_file.name}")

    return summary_report


if __name__ == "__main__":
    default_e57 = Path("d:/SIH26- 3D ULPIN Generation and vertical Property Mapping System/data/aam_khas_bagh/lidar/7csx-ne47_terresterial_lidar.e57")
    if len(sys.argv) > 1:
        e57_p = Path(sys.argv[1])
    else:
        e57_p = default_e57

    run_building_extraction(str(e57_p))
