"""
Aam Khas Bagh LiDAR Mesh Reconstruction Tool

Reads the existing classified point cloud, extracts isolated building points,
and runs the full mesh reconstruction pipeline.

Usage:
    python backend/tools/reconstruct_aam_khas_bagh_mesh.py

Source: 7csx-ne47_terresterial_lidar.e57 (via classified_cloud.json)

CRITICAL:
- Does NOT overwrite aam_khas_bagh_classified_cloud.json
- All outputs go to data/aam_khas_bagh/derived/
- Coordinates remain in AAM_KHAS_BAGH_LOCAL
- No geographic transformation applied
"""

import json
import sys
import numpy as np
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.lidar.mesh_reconstructor import reconstruct_building_mesh


def main():
    derived_dir = backend_dir.parent / "data" / "aam_khas_bagh" / "derived"

    # Load the existing classified cloud (NEVER overwrite it)
    cloud_file = derived_dir / "aam_khas_bagh_classified_cloud.json"
    if not cloud_file.exists():
        print(f"ERROR: Classified cloud not found: {cloud_file}")
        print("Run extract_aam_khas_bagh_building.py first.")
        sys.exit(1)

    print(f"Loading classified cloud from: {cloud_file.name}")
    with open(cloud_file, "r", encoding="utf-8") as f:
        classified = json.load(f)

    # Extract the selected building points flat array [x,y,z,r,g,b, ...]
    building_flat = classified.get("selected_building_points", [])
    if not building_flat:
        print("ERROR: No selected_building_points in classified cloud JSON.")
        sys.exit(1)

    num_pts = len(building_flat) // 6
    print(f"Loaded {num_pts:,} isolated building points from classified cloud.")

    # Reconstruct [N, 3] XYZ array
    points = np.zeros((num_pts, 3), dtype=np.float64)
    for i in range(num_pts):
        base = i * 6
        points[i, 0] = building_flat[base]      # X
        points[i, 1] = building_flat[base + 1]   # Y
        points[i, 2] = building_flat[base + 2]   # Z

    # Run reconstruction
    source_file = classified.get("file_name", "7csx-ne47_terresterial_lidar.e57")
    metadata = reconstruct_building_mesh(
        building_points=points,
        output_dir=derived_dir,
        source_file=source_file,
    )

    if metadata.get("status") == "FAILED":
        print(f"\n*** RECONSTRUCTION FAILED: {metadata.get('failure_reason')} ***")
        print("No synthetic fallback generated. Reporting failure honestly.")
        # Still save the failure metadata
        meta_path = derived_dir / "aam_khas_bagh_mesh_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        sys.exit(1)

    print("\n=== RECONSTRUCTION SUCCESSFUL ===")
    print(f"  Method: {metadata['reconstruction_method']}")
    print(f"  Vertices: {metadata['vertex_count']:,}")
    print(f"  Triangles: {metadata['triangle_count']:,}")
    print(f"  Components: {metadata['component_count']}")
    print(f"  Point Spacing Mean: {metadata['point_spacing']['mean_m']}m")
    print(f"  P2M Distance Mean: {metadata['point_to_mesh_distance']['mean_m']}m")
    print(f"  Coverage <=0.10m: {metadata['point_coverage']['pct_within_010m']}%")
    print(f"  Mesh Support <=0.20m: {metadata['mesh_support'].get('pct_supported_within_020m', 'N/A')}%")


if __name__ == "__main__":
    main()
