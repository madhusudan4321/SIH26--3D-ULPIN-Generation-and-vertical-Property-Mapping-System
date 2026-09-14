"""
Mesh Reconstructor Module — LiDAR-Derived 3D Surface Reconstruction

Converts isolated building LiDAR point clouds into triangulated 3D surface meshes
using real surface reconstruction algorithms (Poisson, Ball Pivoting).

TERMINOLOGY: All outputs are "LiDAR-derived reconstructed 3D mesh" — NOT "actual measured 3D model".

CRITICAL CONSTRAINTS:
- Source must be real E57 LiDAR building points (no synthetic geometry)
- Reconstruction must never fall back to cuboid/bounding box/polygon extrusion
- All coordinates remain in AAM_KHAS_BAGH_LOCAL (no geographic transformation)
- Failure is reported honestly with status: "FAILED" and reason
- Poisson-interpolated regions are explicitly identified as such

Dependencies: open3d, numpy, scipy
"""

import time
import json
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path


def compute_point_spacing(points: np.ndarray) -> Dict[str, float]:
    """
    Compute nearest-neighbor distance statistics for a point cloud.

    These are SURFACE observation spacings, NOT volumetric density.
    Used to inform reconstruction parameters.

    Returns:
        Dict with mean_m, median_m, p25_m, p75_m, p95_m of NN distances.
    """
    from scipy.spatial import KDTree

    if len(points) < 3:
        return {"mean_m": 0, "median_m": 0, "p25_m": 0, "p75_m": 0, "p95_m": 0}

    tree = KDTree(points)
    # Query 2 nearest neighbors (first is self at distance 0)
    dists, _ = tree.query(points, k=2)
    nn_dists = dists[:, 1]  # Skip self-distance

    return {
        "mean_m": round(float(np.mean(nn_dists)), 4),
        "median_m": round(float(np.median(nn_dists)), 4),
        "p25_m": round(float(np.percentile(nn_dists, 25)), 4),
        "p75_m": round(float(np.percentile(nn_dists, 75)), 4),
        "p95_m": round(float(np.percentile(nn_dists, 95)), 4),
    }


def remove_outliers(
    pcd,
    nb_neighbors: int = 20,
    std_ratio: float = 2.0,
) -> Tuple:
    """
    Remove statistical outliers from Open3D point cloud.

    Args:
        pcd: Open3D PointCloud object
        nb_neighbors: Number of neighbors for statistical analysis
        std_ratio: Standard deviation multiplier threshold

    Returns:
        (cleaned_pcd, inlier_count, outlier_count)
    """
    import open3d as o3d

    original_count = len(pcd.points)
    cl, ind = pcd.remove_statistical_outlier(
        nb_neighbors=nb_neighbors, std_ratio=std_ratio
    )
    cleaned = pcd.select_by_index(ind)
    outlier_count = original_count - len(cleaned.points)
    return cleaned, len(cleaned.points), outlier_count


def estimate_normals(pcd, search_radius: float = None, max_nn: int = 30):
    """
    Estimate point normals and orient them consistently.

    Args:
        pcd: Open3D PointCloud
        search_radius: Search radius for normal estimation (auto-computed if None)
        max_nn: Max number of neighbors for normal estimation

    Returns:
        pcd with normals estimated and oriented
    """
    import open3d as o3d

    if search_radius is None:
        # Compute from point spacing
        pts = np.asarray(pcd.points)
        spacing = compute_point_spacing(pts)
        search_radius = spacing["p75_m"] * 3.0
        if search_radius < 0.05:
            search_radius = 0.15

    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=search_radius, max_nn=max_nn
        )
    )

    # Orient normals consistently
    try:
        pcd.orient_normals_consistent_tangent_plane(k=15)
    except Exception:
        # Fallback: orient towards camera (centroid above point cloud)
        centroid = pcd.get_center()
        camera_loc = centroid + np.array([0, 0, 10.0])
        pcd.orient_normals_towards_camera_location(camera_loc)

    return pcd


def reconstruct_poisson(pcd, depth: int = 8) -> Tuple:
    """
    Screened Poisson Surface Reconstruction at a specific depth.

    Returns:
        (mesh, densities_array) or (None, None) on failure
    """
    import open3d as o3d

    try:
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=depth, width=0, scale=1.1, linear_fit=False
        )
        if mesh is None or len(mesh.vertices) == 0:
            return None, None
        return mesh, np.asarray(densities)
    except Exception as e:
        print(f"  Poisson depth={depth} failed: {e}")
        return None, None


def reconstruct_ball_pivoting(pcd, radii: List[float] = None) -> Optional[Any]:
    """
    Ball Pivoting Algorithm reconstruction.

    Args:
        pcd: Open3D PointCloud with normals
        radii: List of ball radii (auto-computed from NN distances if None)

    Returns:
        Open3D TriangleMesh or None
    """
    import open3d as o3d

    if radii is None:
        pts = np.asarray(pcd.points)
        spacing = compute_point_spacing(pts)
        base = spacing["mean_m"]
        if base < 0.01:
            base = 0.1
        radii = [base * 1.0, base * 2.0, base * 4.0]

    try:
        radii_dv = o3d.utility.DoubleVector(radii)
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, radii_dv
        )
        if mesh is None or len(mesh.vertices) == 0:
            return None
        return mesh
    except Exception as e:
        print(f"  Ball Pivoting failed: {e}")
        return None


def analyze_connected_components(mesh) -> List[Dict[str, Any]]:
    """
    Compute all connected components of a mesh.

    Does NOT silently delete any components. Reports all.

    Returns:
        List of component dicts with: component_id, triangle_count, vertex_count,
        area_m2, bounds, centroid
    """
    import open3d as o3d

    triangle_clusters, cluster_n_triangles, cluster_area = (
        mesh.cluster_connected_triangles()
    )
    triangle_clusters = np.asarray(triangle_clusters)
    cluster_n_triangles = np.asarray(cluster_n_triangles)
    cluster_area = np.asarray(cluster_area)

    num_components = len(cluster_n_triangles)
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)

    components = []
    for i in range(num_components):
        tri_mask = triangle_clusters == i
        comp_tris = triangles[tri_mask]
        comp_vert_indices = np.unique(comp_tris.flatten())
        comp_verts = vertices[comp_vert_indices]

        bounds = {
            "x_min": round(float(comp_verts[:, 0].min()), 3),
            "x_max": round(float(comp_verts[:, 0].max()), 3),
            "y_min": round(float(comp_verts[:, 1].min()), 3),
            "y_max": round(float(comp_verts[:, 1].max()), 3),
            "z_min": round(float(comp_verts[:, 2].min()), 3),
            "z_max": round(float(comp_verts[:, 2].max()), 3),
        }

        centroid = [
            round(float(comp_verts[:, 0].mean()), 3),
            round(float(comp_verts[:, 1].mean()), 3),
            round(float(comp_verts[:, 2].mean()), 3),
        ]

        components.append({
            "component_id": i,
            "triangle_count": int(cluster_n_triangles[i]),
            "vertex_count": int(len(comp_vert_indices)),
            "area_m2": round(float(cluster_area[i]), 3),
            "bounds": bounds,
            "centroid": centroid,
        })

    # Sort by triangle count descending
    components.sort(key=lambda c: c["triangle_count"], reverse=True)
    return components


def compute_point_to_mesh_distance(
    points: np.ndarray, mesh
) -> Dict[str, Any]:
    """
    Compute actual point-to-nearest-triangle-surface distance.

    Does NOT invent a universal pass/fail threshold.
    Reports raw statistics for human interpretation.

    Returns:
        Dict with mean_m, median_m, p95_m, p99_m, max_m
    """
    import open3d as o3d

    # Create raycasting scene for accurate distance computation
    scene = o3d.t.geometry.RaycastingScene()
    mesh_t = o3d.t.geometry.TriangleMesh.from_legacy(mesh)
    scene.add_triangles(mesh_t)

    query_pts = o3d.core.Tensor(points.astype(np.float32), dtype=o3d.core.float32)
    distances = scene.compute_distance(query_pts).numpy()

    return {
        "mean_m": round(float(np.mean(distances)), 4),
        "median_m": round(float(np.median(distances)), 4),
        "p95_m": round(float(np.percentile(distances, 95)), 4),
        "p99_m": round(float(np.percentile(distances, 99)), 4),
        "max_m": round(float(np.max(distances)), 4),
        "raw_distances": distances,  # kept for coverage computation
    }


def compute_point_coverage(distances: np.ndarray) -> Dict[str, float]:
    """
    Calculate % of input LiDAR points within various distance thresholds of mesh.

    Does NOT fabricate values. Uses actual computed distances.

    Returns:
        Dict with pct_within_005m, pct_within_010m, pct_within_020m, pct_within_050m
    """
    n = len(distances)
    if n == 0:
        return {
            "pct_within_005m": 0.0,
            "pct_within_010m": 0.0,
            "pct_within_020m": 0.0,
            "pct_within_050m": 0.0,
        }

    return {
        "pct_within_005m": round(float(np.sum(distances <= 0.05) / n * 100), 2),
        "pct_within_010m": round(float(np.sum(distances <= 0.10) / n * 100), 2),
        "pct_within_020m": round(float(np.sum(distances <= 0.20) / n * 100), 2),
        "pct_within_050m": round(float(np.sum(distances <= 0.50) / n * 100), 2),
    }


def compute_mesh_support(
    mesh, source_points: np.ndarray, sample_count: int = 10000
) -> Dict[str, Any]:
    """
    Sample mesh surface points and check whether they are near measured LiDAR points.

    Poisson can create plausible surfaces where the scanner did NOT observe geometry.
    This metric identifies unsupported (interpolated) mesh regions.

    Returns:
        Dict with total_samples, supported counts at various thresholds,
        and pct_supported values.
    """
    import open3d as o3d
    from scipy.spatial import KDTree

    # Sample points uniformly from mesh surface
    try:
        sampled_pcd = mesh.sample_points_uniformly(number_of_points=sample_count)
        mesh_samples = np.asarray(sampled_pcd.points)
    except Exception:
        return {
            "total_samples": 0,
            "error": "Failed to sample mesh surface",
        }

    if len(mesh_samples) == 0:
        return {"total_samples": 0, "error": "No mesh surface samples generated"}

    # Build KDTree from source LiDAR points
    tree = KDTree(source_points)
    dists, _ = tree.query(mesh_samples, k=1)

    actual_samples = len(mesh_samples)
    thresholds = [0.10, 0.20, 0.50, 1.00]
    support = {"total_samples": actual_samples}

    for t in thresholds:
        key_count = f"supported_within_{str(t).replace('.', '')}m"
        key_pct = f"pct_supported_within_{str(t).replace('.', '')}m"
        count = int(np.sum(dists <= t))
        support[key_count] = count
        support[key_pct] = round(float(count / actual_samples * 100), 2)

    support["mesh_sample_to_lidar_distance"] = {
        "mean_m": round(float(np.mean(dists)), 4),
        "median_m": round(float(np.median(dists)), 4),
        "p95_m": round(float(np.percentile(dists, 95)), 4),
        "max_m": round(float(np.max(dists)), 4),
    }

    return support


def trim_poisson_by_density(mesh, densities: np.ndarray, quantile: float = 0.05):
    """
    Remove low-density Poisson faces (interpolated regions without LiDAR support).

    Args:
        mesh: Open3D TriangleMesh from Poisson reconstruction
        densities: Per-vertex density values from Poisson
        quantile: Bottom quantile threshold to remove

    Returns:
        (trimmed_mesh, removed_vertex_count)
    """
    threshold = np.quantile(densities, quantile)
    vertices_to_remove = densities < threshold
    removed_count = int(np.sum(vertices_to_remove))

    mesh.remove_vertices_by_mask(vertices_to_remove)
    return mesh, removed_count


def evaluate_reconstruction(
    mesh,
    source_points: np.ndarray,
    method_name: str,
    depth: int = None,
) -> Dict[str, Any]:
    """
    Evaluate a single reconstruction result with full diagnostics.

    Returns metrics dict for comparison between methods/depths.
    """
    import open3d as o3d

    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)

    if len(vertices) == 0 or len(triangles) == 0:
        return {
            "method": method_name,
            "depth": depth,
            "status": "EMPTY_MESH",
            "vertex_count": 0,
            "triangle_count": 0,
        }

    # Bounds
    bounds = {
        "x_min": round(float(vertices[:, 0].min()), 3),
        "x_max": round(float(vertices[:, 0].max()), 3),
        "y_min": round(float(vertices[:, 1].min()), 3),
        "y_max": round(float(vertices[:, 1].max()), 3),
        "z_min": round(float(vertices[:, 2].min()), 3),
        "z_max": round(float(vertices[:, 2].max()), 3),
    }

    dims = {
        "width_m": round(bounds["x_max"] - bounds["x_min"], 3),
        "length_m": round(bounds["y_max"] - bounds["y_min"], 3),
        "height_m": round(bounds["z_max"] - bounds["z_min"], 3),
    }

    # Surface area
    area = round(float(mesh.get_surface_area()), 3)

    # Connected components
    components = analyze_connected_components(mesh)

    # Point-to-mesh distance
    p2m = compute_point_to_mesh_distance(source_points, mesh)
    raw_dists = p2m.pop("raw_distances")

    # Point coverage
    coverage = compute_point_coverage(raw_dists)

    # Mesh support
    support = compute_mesh_support(mesh, source_points, sample_count=min(10000, len(triangles) * 3))

    return {
        "method": method_name,
        "depth": depth,
        "status": "OK",
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "surface_area_m2": area,
        "bounds": bounds,
        "dimensions": dims,
        "component_count": len(components),
        "components": components,
        "point_to_mesh_distance": p2m,
        "point_coverage": coverage,
        "mesh_support": support,
    }


def reconstruct_building_mesh(
    building_points: np.ndarray,
    output_dir: Path,
    source_file: str = "7csx-ne47_terresterial_lidar.e57",
) -> Dict[str, Any]:
    """
    Main orchestrator: reconstruct a 3D surface mesh from isolated building LiDAR points.

    Pipeline:
        1. Compute point spacing statistics
        2. Remove statistical outliers
        3. Estimate normals
        4. Try Poisson at depths 6, 7, 8 — evaluate each
        5. Try Ball Pivoting as additional option
        6. Select best result by measured diagnostics
        7. Export PLY + OBJ
        8. Generate comprehensive metadata

    CRITICAL: Never falls back to synthetic geometry. Reports failure honestly.

    Args:
        building_points: (N, 3) NumPy array of isolated building XYZ
        output_dir: Directory for output files
        source_file: Original E57 filename for metadata

    Returns:
        Complete metadata dict
    """
    import open3d as o3d

    start_time = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_count = len(building_points)
    print(f"\n{'='*60}")
    print(f"MESH RECONSTRUCTION PIPELINE")
    print(f"Input: {input_count:,} isolated building LiDAR points")
    print(f"{'='*60}")

    # ── STEP 1: Point Spacing Statistics ──────────────────────
    print("\n=== STEP 1: POINT SPACING STATISTICS ===")
    spacing = compute_point_spacing(building_points)
    print(f"  Mean NN distance:   {spacing['mean_m']:.4f} m")
    print(f"  Median NN distance: {spacing['median_m']:.4f} m")
    print(f"  P25 NN distance:    {spacing['p25_m']:.4f} m")
    print(f"  P75 NN distance:    {spacing['p75_m']:.4f} m")
    print(f"  P95 NN distance:    {spacing['p95_m']:.4f} m")

    # ── STEP 2: Create Open3D Point Cloud ─────────────────────
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(building_points.astype(np.float64))

    # ── STEP 3: Outlier Removal ───────────────────────────────
    print("\n=== STEP 2: STATISTICAL OUTLIER REMOVAL ===")
    pcd_clean, inlier_count, outlier_count = remove_outliers(pcd, nb_neighbors=20, std_ratio=2.0)
    print(f"  Inliers: {inlier_count:,}  |  Outliers removed: {outlier_count:,}")

    if inlier_count < 100:
        return _fail_result(
            "Insufficient points after outlier removal",
            input_count, spacing, source_file
        )

    clean_points = np.asarray(pcd_clean.points)

    # ── STEP 4: Normal Estimation ─────────────────────────────
    print("\n=== STEP 3: NORMAL ESTIMATION ===")
    search_rad = spacing["p75_m"] * 3.0
    if search_rad < 0.05:
        search_rad = 0.15
    print(f"  Search radius: {search_rad:.3f} m")

    pcd_clean = estimate_normals(pcd_clean, search_radius=search_rad, max_nn=30)

    normals = np.asarray(pcd_clean.normals)
    if len(normals) == 0 or np.all(normals == 0):
        return _fail_result(
            "Normal estimation failed — normals are zero or empty",
            input_count, spacing, source_file
        )
    print(f"  Normals estimated for {len(normals):,} points")

    # ── STEP 5: Multi-Method Reconstruction ───────────────────
    print("\n=== STEP 4: MULTI-METHOD RECONSTRUCTION ===")
    evaluations = []

    # Try Poisson at depths 6, 7, 8
    for depth in [6, 7, 8]:
        print(f"\n  --- Poisson depth={depth} ---")
        mesh_p, densities = reconstruct_poisson(pcd_clean, depth=depth)

        if mesh_p is None:
            print(f"  Poisson depth={depth}: FAILED")
            continue

        # Trim low-density interpolated faces
        mesh_trimmed, removed_v = trim_poisson_by_density(mesh_p, densities, quantile=0.05)
        print(f"  Raw vertices: {len(np.asarray(mesh_p.vertices)):,} (trimmed {removed_v:,} low-density)")

        # Clean degenerate triangles
        mesh_trimmed.remove_degenerate_triangles()
        mesh_trimmed.remove_unreferenced_vertices()
        mesh_trimmed.remove_non_manifold_edges()

        v_count = len(mesh_trimmed.vertices)
        t_count = len(mesh_trimmed.triangles)
        print(f"  After cleanup: {v_count:,} vertices, {t_count:,} triangles")

        if t_count > 0:
            ev = evaluate_reconstruction(
                mesh_trimmed, clean_points, f"poisson_depth_{depth}", depth
            )
            ev["_mesh_obj"] = mesh_trimmed  # Keep for later export
            evaluations.append(ev)

    # Try Ball Pivoting
    print(f"\n  --- Ball Pivoting ---")
    base_rad = spacing["mean_m"]
    if base_rad < 0.01:
        base_rad = 0.1
    bp_radii = [base_rad, base_rad * 2.0, base_rad * 4.0]
    print(f"  Radii: {[round(r, 4) for r in bp_radii]}")

    mesh_bp = reconstruct_ball_pivoting(pcd_clean, radii=bp_radii)
    if mesh_bp is not None:
        mesh_bp.remove_degenerate_triangles()
        mesh_bp.remove_unreferenced_vertices()
        v_count = len(mesh_bp.vertices)
        t_count = len(mesh_bp.triangles)
        print(f"  Ball Pivoting result: {v_count:,} vertices, {t_count:,} triangles")

        if t_count > 0:
            ev = evaluate_reconstruction(
                mesh_bp, clean_points, "ball_pivoting", None
            )
            ev["_mesh_obj"] = mesh_bp
            evaluations.append(ev)
    else:
        print("  Ball Pivoting: FAILED")

    # ── STEP 6: Select Best Method ────────────────────────────
    print(f"\n=== STEP 5: METHOD COMPARISON & SELECTION ===")

    if not evaluations:
        return _fail_result(
            "All reconstruction methods failed — no valid mesh produced",
            input_count, spacing, source_file
        )

    # Print comparison table
    print(f"\n  {'Method':<25} {'Verts':>8} {'Tris':>8} {'Area m2':>10} {'P2M Mean':>10} {'P2M P95':>10} {'Comps':>6}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*6}")
    for ev in evaluations:
        p2m_mean = ev.get("point_to_mesh_distance", {}).get("mean_m", "N/A")
        p2m_p95 = ev.get("point_to_mesh_distance", {}).get("p95_m", "N/A")
        print(f"  {ev['method']:<25} {ev['vertex_count']:>8,} {ev['triangle_count']:>8,} "
              f"{ev['surface_area_m2']:>10.1f} {p2m_mean:>10} {p2m_p95:>10} {ev['component_count']:>6}")

    # Selection criteria for architectural structures:
    # Use composite score = P2M_mean * log2(component_count + 1)
    # This penalizes highly fragmented meshes (e.g. Ball Pivoting 369 comps)
    # while still rewarding low point-to-mesh distance.
    import math

    def sort_key(ev):
        p2m_mean = ev.get("point_to_mesh_distance", {}).get("mean_m", 999)
        comp_count = ev.get("component_count", 999)
        # Composite: mean P2M distance weighted by fragmentation penalty
        fragmentation_penalty = math.log2(comp_count + 1)
        return p2m_mean * fragmentation_penalty

    evaluations.sort(key=sort_key)
    best = evaluations[0]
    best_mesh = best.pop("_mesh_obj")

    # Remove _mesh_obj from non-selected evaluations
    for ev in evaluations[1:]:
        ev.pop("_mesh_obj", None)

    p2m_info = best['point_to_mesh_distance']
    print(f"\n  SELECTED: {best['method']} "
          f"(mean P2M: {p2m_info['mean_m']}m, "
          f"{best['component_count']} components)")

    # ── STEP 7: Export ────────────────────────────────────────
    print("\n=== STEP 6: EXPORT ===")

    # Compute mesh vertex colors (light stone/sandstone color for Hammam)
    best_mesh.compute_vertex_normals()

    ply_path = output_dir / "aam_khas_bagh_hammam_mesh.ply"
    obj_path = output_dir / "aam_khas_bagh_hammam_mesh.obj"

    o3d.io.write_triangle_mesh(str(ply_path), best_mesh, write_ascii=False)
    print(f"  Exported: {ply_path.name} ({ply_path.stat().st_size / 1024:.1f} KB)")

    o3d.io.write_triangle_mesh(str(obj_path), best_mesh)
    print(f"  Exported: {obj_path.name} ({obj_path.stat().st_size / 1024:.1f} KB)")

    # ── STEP 8: Comprehensive Metadata ────────────────────────
    elapsed = round(time.time() - start_time, 2)

    metadata = {
        "source": source_file,
        "scan_count": 21,
        "geometry_source": "lidar_reconstructed_mesh",
        "terminology": "LiDAR-derived reconstructed 3D mesh",
        "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "georeferenced": False,
        "reconstruction_method": best["method"],
        "input_point_count": input_count,
        "outliers_removed": outlier_count,
        "points_after_cleaning": inlier_count,
        "normals_estimated": True,
        "normal_search_radius_m": round(search_rad, 4),
        "point_spacing": spacing,
        "vertex_count": best["vertex_count"],
        "triangle_count": best["triangle_count"],
        "surface_area_m2": best["surface_area_m2"],
        "bounds": best["bounds"],
        "dimensions": best["dimensions"],
        "component_count": best["component_count"],
        "components": best["components"],
        "point_to_mesh_distance": best["point_to_mesh_distance"],
        "point_coverage": best["point_coverage"],
        "mesh_support": best["mesh_support"],
        "method_comparison": [
            {k: v for k, v in ev.items() if k != "_mesh_obj"}
            for ev in evaluations
        ],
        "output_files": {
            "ply": ply_path.name,
            "obj": obj_path.name,
        },
        "processing_time_seconds": elapsed,
        "status": "SUCCESS",
        "confirmation": "NO GEOGRAPHIC TRANSFORMATION HAS BEEN APPLIED.",
        "disclaimer": (
            "This is a LiDAR-derived reconstructed 3D mesh. "
            "Poisson reconstruction may generate interpolated surfaces in regions "
            "without direct LiDAR observations. See mesh_support metrics to identify "
            "measured vs interpolated regions."
        ),
    }

    meta_path = output_dir / "aam_khas_bagh_mesh_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"  Exported: {meta_path.name}")

    print(f"\n{'='*60}")
    print(f"RECONSTRUCTION COMPLETE in {elapsed}s")
    print(f"  Method: {best['method']}")
    print(f"  Vertices: {best['vertex_count']:,}")
    print(f"  Triangles: {best['triangle_count']:,}")
    print(f"  Components: {best['component_count']}")
    print(f"  P2M Mean: {best['point_to_mesh_distance']['mean_m']}m")
    print(f"  P2M Median: {best['point_to_mesh_distance']['median_m']}m")
    print(f"  Coverage <=0.10m: {best['point_coverage']['pct_within_010m']}%")
    print(f"{'='*60}")

    return metadata


def _fail_result(
    reason: str,
    input_count: int,
    spacing: Dict,
    source_file: str,
) -> Dict[str, Any]:
    """
    Generate an honest failure report. Never falls back to synthetic geometry.
    """
    print(f"\n*** RECONSTRUCTION FAILED: {reason} ***")
    return {
        "source": source_file,
        "geometry_source": "lidar_reconstructed_mesh",
        "coordinate_system": "AAM_KHAS_BAGH_LOCAL",
        "georeferenced": False,
        "input_point_count": input_count,
        "point_spacing": spacing,
        "status": "FAILED",
        "failure_reason": reason,
        "vertex_count": 0,
        "triangle_count": 0,
        "confirmation": "NO GEOGRAPHIC TRANSFORMATION HAS BEEN APPLIED.",
    }
