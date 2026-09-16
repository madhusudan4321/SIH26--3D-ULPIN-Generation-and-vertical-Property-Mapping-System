"""
Image Ingestion Module — Drone Image Discovery & Manifest Generation

Discovers supported image files in a directory and produces a machine-readable
photogrammetry_image_manifest.json recording each image's path, extension,
file size, width, height, and format.

Supported formats (Phase 2): .jpg, .jpeg, .png, .tif, .tiff
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image

from app.photogrammetry.config import SUPPORTED_IMAGE_EXTENSIONS


def discover_images(
    images_dir: Path,
    dataset_name: str = "unnamed_dataset",
    reports_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Discover all supported image files in images_dir and save manifest.json if reports_dir is provided.

    Returns:
        dict: Manifest dictionary containing discovered images.
    """
    if not images_dir.exists():
        manifest = {
            "dataset_name": dataset_name,
            "source_directory": str(images_dir),
            "total_discovered": 0,
            "images": [],
        }
        if reports_dir:
            reports_dir.mkdir(parents=True, exist_ok=True)
            with open(reports_dir / "photogrammetry_image_manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        return manifest

    image_files = []
    for entry in sorted(images_dir.iterdir()):
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            image_files.append(entry)
        elif entry.is_dir():
            for sub_entry in sorted(entry.iterdir()):
                if sub_entry.is_file() and sub_entry.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                    image_files.append(sub_entry)

    images_info = [_build_image_info(img_path, images_dir) for img_path in image_files]

    manifest = {
        "dataset_name": dataset_name,
        "source_directory": str(images_dir),
        "total_discovered": len(images_info),
        "images": images_info,
    }

    if reports_dir:
        reports_dir.mkdir(parents=True, exist_ok=True)
        with open(reports_dir / "photogrammetry_image_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    return manifest


def _build_image_info(img_path: Path, base_dir: Path) -> Dict[str, Any]:
    """Build metadata dict for a single image file."""
    info = {
        "filename": img_path.name,
        "path": str(img_path),
        "relative_path": str(img_path.relative_to(base_dir)),
        "extension": img_path.suffix.lower(),
        "file_size_bytes": img_path.stat().st_size,
        "size_mb": round(img_path.stat().st_size / (1024 * 1024), 3),
        "width": 0,
        "height": 0,
        "format": None,
        "readable": True,
    }

    try:
        with Image.open(img_path) as img:
            info["width"] = img.width
            info["height"] = img.height
            info["format"] = img.format
    except Exception as e:
        info["readable"] = False
        info["error"] = str(e)

    return info
