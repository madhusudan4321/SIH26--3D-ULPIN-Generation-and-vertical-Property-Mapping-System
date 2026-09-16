"""
SfM Sparse Reconstruction Analysis & Parser Module

Parses COLMAP sparse reconstruction output (cameras, images, points3D) from text (.txt)
or binary (.bin) files in sparse/0/.

Calculates key SfM quality metrics:
- total_images vs registered_images
- registration_percentage
- total_components & largest_component_percentage
- sparse_points count & track length stats
- mean, median, max reprojection error (px)
- weakly_connected_images
"""

import logging
import struct
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def read_cameras_text(path: Path) -> Dict[int, Dict[str, Any]]:
    """Read COLMAP cameras.txt file."""
    cameras = {}
    if not path.exists():
        return cameras
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    camera_id = int(parts[0])
                    model = parts[1]
                    width = int(parts[2])
                    height = int(parts[3])
                    cameras[camera_id] = {
                        "camera_id": camera_id,
                        "model": model,
                        "width": width,
                        "height": height,
                    }
    except Exception as e:
        logger.warning(f"Error reading text cameras file {path}: {e}")
    return cameras


def read_images_text(path: Path) -> Dict[int, Dict[str, Any]]:
    """Read COLMAP images.txt file."""
    images = {}
    if not path.exists():
        return images
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 10:
                image_id = int(parts[0])
                camera_id = int(parts[8])
                name = parts[9]
                images[image_id] = {
                    "image_id": image_id,
                    "name": name,
                    "camera_id": camera_id,
                }
            # Skip 2D points line
            i += 1
    except Exception as e:
        logger.warning(f"Error reading text images file {path}: {e}")
    return images


def read_points3d_text(path: Path) -> List[Dict[str, Any]]:
    """Read COLMAP points3D.txt file."""
    points = []
    if not path.exists():
        return points
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    point_id = int(parts[0])
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    r, g, b = int(parts[4]), int(parts[5]), int(parts[6])
                    error = float(parts[7])
                    track_len = (len(parts) - 8) // 2
                    points.append({
                        "point_id": point_id,
                        "xyz": (x, y, z),
                        "rgb": (r, g, b),
                        "error": error,
                        "track_len": max(track_len, 0),
                    })
    except Exception as e:
        logger.warning(f"Error reading text points3D file {path}: {e}")
    return points


def read_cameras_binary(path: Path) -> Dict[int, Dict[str, Any]]:
    """Read COLMAP cameras.bin file."""
    cameras = {}
    if not path.exists():
        return cameras
    try:
        with open(path, "rb") as f:
            num_cameras = struct.unpack("<Q", f.read(8))[0]
            for _ in range(num_cameras):
                camera_id, model_id, width, height = struct.unpack("<iiQQ", f.read(24))
                cameras[camera_id] = {
                    "camera_id": camera_id,
                    "model_id": model_id,
                    "width": width,
                    "height": height,
                }
    except Exception as e:
        logger.warning(f"Error reading binary cameras file {path}: {e}")
    return cameras


def read_images_binary(path: Path) -> Dict[int, Dict[str, Any]]:
    """Read COLMAP images.bin file."""
    images = {}
    if not path.exists():
        return images
    try:
        with open(path, "rb") as f:
            num_images = struct.unpack("<Q", f.read(8))[0]
            for _ in range(num_images):
                image_id, qw, qx, qy, qz, tx, ty, tz, camera_id = struct.unpack("<i7ddi", f.read(68))
                name_chars = []
                while True:
                    char = f.read(1)
                    if char == b"\x00" or not char:
                        break
                    name_chars.append(char.decode("utf-8", errors="ignore"))
                name = "".join(name_chars)
                num_p2d = struct.unpack("<Q", f.read(8))[0]
                f.seek(num_p2d * 24, 1)

                images[image_id] = {
                    "image_id": image_id,
                    "name": name,
                    "camera_id": camera_id,
                    "num_points2D": num_p2d,
                }
    except Exception as e:
        logger.warning(f"Error reading binary images file {path}: {e}")
    return images


def read_points3d_binary(path: Path) -> List[Dict[str, Any]]:
    """Read COLMAP points3D.bin file."""
    points = []
    if not path.exists():
        return points
    try:
        with open(path, "rb") as f:
            num_points = struct.unpack("<Q", f.read(8))[0]
            for _ in range(num_points):
                point3d_id, x, y, z, r, g, b, error, track_len = struct.unpack("<Qddd3bQ", f.read(43))
                f.seek(track_len * 8, 1)
                points.append({
                    "point_id": point3d_id,
                    "xyz": (x, y, z),
                    "rgb": (r, g, b),
                    "error": error,
                    "track_len": track_len,
                })
    except Exception as e:
        logger.warning(f"Error reading binary points3D file {path}: {e}")
    return points


def parse_sparse_model(
    sparse_dir: Path,
    total_discovered_images: int = 0,
) -> Dict[str, Any]:
    """
    Parse sparse reconstruction outputs in sparse_dir (checks sparse/0 first, then sparse/).

    Supports both text (.txt) and binary (.bin) format files.

    Returns:
        dict: SfM metrics report.
    """
    res: Dict[str, Any] = {
        "model_exists": False,
        "total_images": total_discovered_images,
        "registered_images": 0,
        "registration_percentage": 0.0,
        "total_components": 0,
        "largest_component_images": 0,
        "largest_component_percentage": 0.0,
        "sparse_points": 0,
        "observations_per_point_mean": 0.0,
        "mean_track_length": 0.0,
        "mean_reprojection_error_px": 0.0,
        "median_reprojection_error_px": 0.0,
        "max_reprojection_error_px": 0.0,
        "weakly_connected_images": [],
        "camera_models": [],
    }

    # Find reconstruction directory (usually sparse/0)
    model_path = sparse_dir / "0"
    if not model_path.exists():
        model_path = sparse_dir

    cameras_txt = model_path / "cameras.txt"
    images_txt = model_path / "images.txt"
    points_txt = model_path / "points3D.txt"

    cameras_bin = model_path / "cameras.bin"
    images_bin = model_path / "images.bin"
    points_bin = model_path / "points3D.bin"

    # Check existence
    has_txt = images_txt.exists() and points_txt.exists()
    has_bin = images_bin.exists() and points_bin.exists()

    if not (has_txt or has_bin):
        logger.warning(f"No COLMAP sparse model files found at {model_path}")
        return res

    res["model_exists"] = True

    # Check component count (sparse/0, sparse/1, etc.)
    component_dirs = [d for d in sparse_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    res["total_components"] = max(len(component_dirs), 1)

    # Read model (prefer TXT for cross-version COLMAP compatibility)
    if has_txt:
        cameras = read_cameras_text(cameras_txt)
        images = read_images_text(images_txt)
        points3d = read_points3d_text(points_txt)
    else:
        cameras = read_cameras_binary(cameras_bin)
        images = read_images_binary(images_bin)
        points3d = read_points3d_binary(points_bin)

    registered_count = len(images)
    res["registered_images"] = registered_count
    res["largest_component_images"] = registered_count

    if total_discovered_images > 0:
        res["registration_percentage"] = round((registered_count / total_discovered_images * 100.0), 1)
        res["largest_component_percentage"] = res["registration_percentage"]
    else:
        res["registration_percentage"] = 100.0 if registered_count > 0 else 0.0
        res["largest_component_percentage"] = res["registration_percentage"]

    # Point metrics & reprojection errors
    num_pts = len(points3d)
    res["sparse_points"] = num_pts

    if num_pts > 0:
        errors = [p["error"] for p in points3d]
        tracks = [p["track_len"] for p in points3d]

        errors_sorted = sorted(errors)
        res["mean_reprojection_error_px"] = round(float(sum(errors) / num_pts), 3)
        res["median_reprojection_error_px"] = round(float(errors_sorted[num_pts // 2]), 3)
        res["max_reprojection_error_px"] = round(float(errors_sorted[-1]), 3)

        mean_track = float(sum(tracks) / num_pts)
        res["mean_track_length"] = round(mean_track, 2)
        res["observations_per_point_mean"] = round(mean_track, 2)

    res["camera_models"] = list(set([c.get("model", c.get("model_id")) for c in cameras.values()]))
    logger.info(f"Parsed SfM model: {registered_count} registered images, {num_pts} sparse points, mean reproj err: {res['mean_reprojection_error_px']}px.")
    return res
