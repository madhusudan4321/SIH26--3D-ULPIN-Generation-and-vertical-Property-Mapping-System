"""
Image Quality & Integrity Validation Module

Validates image integrity, corruption, sharpness (via scipy Laplacian variance),
brightness/exposure, and near-duplicates.
Classifies images as VALID, WARNING, or INVALID, and optionally generates
image_list.txt for COLMAP filtering.
"""

import hashlib
import json
import logging
import numpy as np
from pathlib import Path
from PIL import Image, ImageStat
from scipy.ndimage import laplace
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


def compute_partial_hash(file_path: Path, block_size: int = 65536) -> str:
    """Compute MD5 hash of the first block of a file for fast duplicate detection."""
    hasher = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            buf = f.read(block_size)
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to read partial hash for {file_path}: {e}")
        return ""


def calculate_sharpness(img: Image.Image) -> float:
    """
    Calculate image sharpness score using variance of Laplacian via scipy.
    Higher values indicate sharper images.
    """
    try:
        gray = img.convert("L")
        arr = np.asarray(gray, dtype=np.float64)
        lap = laplace(arr)
        variance = float(np.var(lap))
        return variance
    except Exception as e:
        logger.warning(f"Error calculating sharpness: {e}")
        return 0.0


def calculate_brightness(img: Image.Image) -> float:
    """Calculate mean pixel brightness (0.0 to 255.0)."""
    try:
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        return float(stat.mean[0])
    except Exception as e:
        logger.warning(f"Error calculating brightness: {e}")
        return 128.0


def validate_images(
    manifest: Dict[str, Any],
    reports_dir: Path,
    workspace_dir: Path,
    min_sharpness: float = 30.0,
    min_brightness: float = 20.0,
    max_brightness: float = 235.0,
) -> Dict[str, Any]:
    """
    Validate images listed in manifest.

    Returns:
        dict: Image quality validation report.
    """
    images_info = manifest.get("images", [])
    total_count = len(images_info)

    valid_count = 0
    warning_count = 0
    invalid_count = 0

    image_details: List[Dict[str, Any]] = []
    seen_hashes: Dict[Tuple[int, int, int, str], str] = {}  # (size, w, h, hash) -> first_filename
    colmap_image_list: List[str] = []

    sharpness_scores: List[float] = []
    min_w, max_w = float("inf"), 0
    min_h, max_h = float("inf"), 0

    for item in images_info:
        file_path = Path(item["path"])
        filename = item["filename"]
        file_size = item.get("file_size_bytes", 0)
        width = item.get("width", 0)
        height = item.get("height", 0)

        status = "VALID"
        reasons: List[str] = []

        if width > 0 and height > 0:
            min_w = min(min_w, width)
            max_w = max(max_w, width)
            min_h = min(min_h, height)
            max_h = max(max_h, height)

        # 1. Integrity check
        try:
            with Image.open(file_path) as img:
                img.verify()
            with Image.open(file_path) as img:
                img.load()
                sharpness = calculate_sharpness(img)
                brightness = calculate_brightness(img)
                sharpness_scores.append(sharpness)
        except Exception as e:
            status = "INVALID"
            reasons.append(f"Corrupted or unreadable image file: {str(e)}")
            sharpness = 0.0
            brightness = 0.0

        if status != "INVALID":
            # 2. Near-duplicate check
            partial_hash = compute_partial_hash(file_path)
            dup_key = (file_size, width, height, partial_hash)
            if dup_key in seen_hashes:
                status = "WARNING"
                reasons.append(f"Potential duplicate of {seen_hashes[dup_key]}")
            else:
                seen_hashes[dup_key] = filename

            # 3. Sharpness check
            if sharpness < min_sharpness:
                status = "WARNING" if status == "VALID" else status
                reasons.append(f"Low sharpness score ({sharpness:.1f} < {min_sharpness})")

            # 4. Exposure check
            if brightness < min_brightness:
                status = "WARNING" if status == "VALID" else status
                reasons.append(f"Underexposed image (mean brightness {brightness:.1f} < {min_brightness})")
            elif brightness > max_brightness:
                status = "WARNING" if status == "VALID" else status
                reasons.append(f"Overexposed image (mean brightness {brightness:.1f} > {max_brightness})")

        # Increment counts
        rel_path = item.get("relative_path", filename)
        if status == "VALID":
            valid_count += 1
            colmap_image_list.append(rel_path)
        elif status == "WARNING":
            warning_count += 1
            colmap_image_list.append(rel_path)  # Include WARNING images in COLMAP image_list
        else:
            invalid_count += 1

        image_details.append({
            "filename": filename,
            "path": str(file_path),
            "status": status,
            "reasons": reasons,
            "sharpness_score": round(sharpness, 2),
            "brightness_score": round(brightness, 2),
            "width": width,
            "height": height,
        })

    # Summary report structure
    mean_sharpness = round(float(np.mean(sharpness_scores)), 2) if sharpness_scores else 0.0
    res_range = {
        "min_w": int(min_w) if min_w != float("inf") else 0,
        "max_w": int(max_w) if max_w > 0 else 0,
        "min_h": int(min_h) if min_h != float("inf") else 0,
        "max_h": int(max_h) if max_h > 0 else 0,
    }

    report = {
        "dataset_name": manifest.get("dataset_name", ""),
        "total_discovered": total_count,
        "valid": valid_count,
        "warning": warning_count,
        "invalid": invalid_count,
        "mean_sharpness_score": mean_sharpness,
        "resolution_range": res_range,
        "images": image_details,
    }

    # Save report
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "photogrammetry_image_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Save COLMAP image_list.txt in workspace
    workspace_dir.mkdir(parents=True, exist_ok=True)
    image_list_path = workspace_dir / "image_list.txt"
    with open(image_list_path, "w", encoding="utf-8") as f:
        for fname in colmap_image_list:
            f.write(f"{fname}\n")

    report["image_list_path"] = str(image_list_path)
    logger.info(f"Image validation completed: {valid_count} valid, {warning_count} warnings, {invalid_count} invalid out of {total_count}")
    return report
