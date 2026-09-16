"""Pre-implementation investigation: RGB survival, point count tracing, data schema."""
import json
import numpy as np
from pathlib import Path

data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "aam_khas_bagh" / "derived"

# ============================================================
# INVESTIGATION 1: RGB availability in classified cloud
# ============================================================
print("=" * 60)
print("INVESTIGATION 1: RGB AVAILABILITY")
print("=" * 60)

with open(data_dir / "aam_khas_bagh_classified_cloud.json", "r") as f:
    cloud = json.load(f)

flat = cloud["selected_building_points"]
num_pts = len(flat) // 6
pts = np.zeros((num_pts, 3), dtype=np.float64)
colors = np.zeros((num_pts, 3), dtype=np.float64)

for i in range(num_pts):
    base = i * 6
    pts[i] = [flat[base], flat[base+1], flat[base+2]]
    colors[i] = [flat[base+3], flat[base+4], flat[base+5]]

print(f"Points: {num_pts}")
print(f"R range: [{colors[:,0].min():.0f}, {colors[:,0].max():.0f}]")
print(f"G range: [{colors[:,1].min():.0f}, {colors[:,1].max():.0f}]")
print(f"B range: [{colors[:,2].min():.0f}, {colors[:,2].max():.0f}]")
print(f"R mean/std: {colors[:,0].mean():.1f} / {colors[:,0].std():.1f}")
print(f"G mean/std: {colors[:,1].mean():.1f} / {colors[:,1].std():.1f}")
print(f"B mean/std: {colors[:,2].mean():.1f} / {colors[:,2].std():.1f}")

# Check how many have all-zero RGB (missing)
zero_rgb = np.sum(np.all(colors == 0, axis=1))
print(f"All-zero RGB points: {zero_rgb} ({zero_rgb/num_pts*100:.1f}%)")

# Check if all same color (uniform = unreliable)
unique_colors = len(np.unique(colors, axis=0))
print(f"Unique RGB values: {unique_colors}")

# Green ratio distribution
rgb_sum = colors.sum(axis=1) + 1  # avoid div by zero
green_ratio = colors[:, 1] / rgb_sum
print(f"Green ratio: min={green_ratio.min():.3f}, median={np.median(green_ratio):.3f}, "
      f"max={green_ratio.max():.3f}, std={green_ratio.std():.3f}")

# RGB was averaged during voxelization (check downsampler code)
print("\nRGB PIPELINE:")
print("  E57 -> per-point RGB uint8")
print("  -> voxel_grid_downsample: np.add.at + /counts -> mean RGB per voxel -> clip uint8")
print("  -> ground filter: no RGB modification")
print("  -> DBSCAN: no RGB modification, indices into non_ground array")
print("  -> selected_building_points: RGB from ds_colors[non_ground_idx[c_indices]]")
print("  CONCLUSION: RGB is voxel-averaged. Present but potentially smoothed.")

# ============================================================
# INVESTIGATION 2: 11,049 vs 21,124 definitive trace
# ============================================================
print("\n" + "=" * 60)
print("INVESTIGATION 2: 11,049 vs 21,124 DEFINITIVE TRACE")
print("=" * 60)

# Current classified cloud
print(f"classified_cloud.json selected_building_points: {num_pts}")
print(f"classified_cloud.json extraction report candidate_id: "
      f"{cloud.get('extracted_building', {}).get('candidate_id', 'N/A')}")
print(f"classified_cloud.json extracted_building point_count: "
      f"{cloud.get('extracted_building', {}).get('point_count', 'N/A')}")

# Mesh metadata
with open(data_dir / "aam_khas_bagh_mesh_metadata.json", "r") as f:
    mesh_meta = json.load(f)

print(f"\nmesh_metadata.json input_point_count: {mesh_meta.get('input_point_count')}")
print(f"mesh_metadata.json points_after_cleaning: {mesh_meta.get('points_after_cleaning')}")
print(f"mesh_metadata.json reconstruction_method: {mesh_meta.get('reconstruction_method')}")

# The mesh reconstruction script reads selected_building_points from classified_cloud.json
# If the classified cloud was regenerated AFTER the mesh was built, the counts diverge
# Check file timestamps
import os
cloud_mtime = os.path.getmtime(data_dir / "aam_khas_bagh_classified_cloud.json")
mesh_mtime = os.path.getmtime(data_dir / "aam_khas_bagh_hammam_mesh.ply")
meta_mtime = os.path.getmtime(data_dir / "aam_khas_bagh_mesh_metadata.json")

from datetime import datetime
print(f"\nFile timestamps:")
print(f"  classified_cloud.json: {datetime.fromtimestamp(cloud_mtime)}")
print(f"  hammam_mesh.ply:       {datetime.fromtimestamp(mesh_mtime)}")
print(f"  mesh_metadata.json:    {datetime.fromtimestamp(meta_mtime)}")

if cloud_mtime > mesh_mtime:
    print("  => classified_cloud.json is NEWER than the mesh")
    print("  => mesh was built from an OLDER cloud with 21,124 pts")
    print("  => they are from DIFFERENT pipeline runs")
else:
    print("  => mesh is newer than or same age as classified cloud")
    print("  => investigate further")

# Building candidates detail
cands = cloud.get("building_candidates", [])
print(f"\nBuilding candidates in current classified cloud: {len(cands)}")
for c in cands:
    print(f"  #{c['candidate_id']}: {c['point_count']} pts, score={c['building_score']}, "
          f"dims={c['width_m']}x{c['length_m']}x{c['height_m']}m, "
          f"centroid={c['centroid']}")

total_c = sum(c['point_count'] for c in cands)
print(f"  Sum of all candidates: {total_c}")
print(f"  Non-ground total: {len(cloud.get('non_ground_points', []))//6}")

# ============================================================
# INVESTIGATION 3: Previous audit count inconsistency
# ============================================================
print("\n" + "=" * 60)
print("INVESTIGATION 3: PREVIOUS AUDIT COUNT INCONSISTENCY")
print("=" * 60)
print("Previous audit reported:")
print("  Building-like:    6,188")
print("  Vegetation-like:  3,652")
print("  Isolated/outlier: 1,440")
print(f"  Sum: {6188 + 3652 + 1440} (should be 11,049)")
print(f"  Difference: {6188 + 3652 + 1440 - 11049}")
print()
print("CAUSE: The audit heuristic used overlapping masks.")
print("  vegetation_like_mask used (local_z_var > threshold) & (local_z_range > 0.3)")
print("  isolated_mask used (neighbor_count <= 2)")
print("  building_like_mask = ~vegetation_like & ~isolated")
print("  BUT: a point can be BOTH vegetation-like AND isolated.")
print("  The building-like mask excludes both, but reporting counts each separately.")
print()
print("FIX: In the new classifier, each point gets EXACTLY ONE class.")
print("  Sum will equal 11,049 by construction (enforced by assertion).")
