"""
EXIF Metadata & GPS Extraction Module

Extracts camera metadata (make, model, focal length) and GPS coordinates from drone images.
Maintains strict separation between metadata GPS availability and authoritative georeferencing:
- gps_metadata_available: True/False
- photogrammetry_georeferenced: False (always False at this stage)
- coordinate_frame: PHOTOGRAMMETRIC_LOCAL
"""

import json
import logging
from pathlib import Path
from PIL import Image, ExifTags
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _convert_to_degrees(value: Tuple[float, float, float]) -> float:
    """Convert EXIF GPS tuple (degrees, minutes, seconds) to decimal degrees."""
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return 0.0


def _extract_gps_info(gps_dict: Dict[int, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Extract lat, lon, alt in decimal degrees from EXIF GPS IFD dictionary."""
    lat = None
    lon = None
    alt = None

    try:
        # GPS Tag IDs:
        # 1: GPSLatitudeRef ('N', 'S')
        # 2: GPSLatitude
        # 3: GPSLongitudeRef ('E', 'W')
        # 4: GPSLongitude
        # 6: GPSAltitude

        lat_ref = gps_dict.get(1, "N")
        lat_val = gps_dict.get(2)
        lon_ref = gps_dict.get(3, "E")
        lon_val = gps_dict.get(4)
        alt_val = gps_dict.get(6)

        if lat_val:
            lat = _convert_to_degrees(lat_val)
            if lat_ref == "S":
                lat = -lat

        if lon_val:
            lon = _convert_to_degrees(lon_val)
            if lon_ref == "W":
                lon = -lon

        if alt_val is not None:
            try:
                alt = float(alt_val)
            except (TypeError, ValueError):
                alt = None
    except Exception as e:
        logger.debug(f"Error parsing GPS tags: {e}")

    return lat, lon, alt


def extract_image_exif(image_path: Path) -> Dict[str, Any]:
    """Extract EXIF camera info and GPS from a single image."""
    res = {
        "filename": image_path.name,
        "camera_make": None,
        "camera_model": None,
        "focal_length_mm": None,
        "timestamp": None,
        "has_gps": False,
        "latitude": None,
        "longitude": None,
        "altitude_m": None,
    }

    try:
        with Image.open(image_path) as img:
            exif_raw = img._getexif()
            if not exif_raw:
                return res

            exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}

            res["camera_make"] = str(exif.get("Make", "")).strip() or None
            res["camera_model"] = str(exif.get("Model", "")).strip() or None
            res["timestamp"] = str(exif.get("DateTimeOriginal", exif.get("DateTime", ""))).strip() or None

            focal = exif.get("FocalLength")
            if focal is not None:
                try:
                    res["focal_length_mm"] = float(focal)
                except (TypeError, ValueError):
                    pass

            gps_info = exif.get("GPSInfo")
            if gps_info and isinstance(gps_info, dict):
                lat, lon, alt = _extract_gps_info(gps_info)
                if lat is not None and lon is not None:
                    res["has_gps"] = True
                    res["latitude"] = round(lat, 7)
                    res["longitude"] = round(lon, 7)
                    res["altitude_m"] = round(alt, 2) if alt is not None else None
    except Exception as e:
        logger.debug(f"EXIF extraction skipped for {image_path.name}: {e}")

    return res


def process_dataset_exif(
    manifest: Dict[str, Any],
    reports_dir: Path,
) -> Dict[str, Any]:
    """
    Process EXIF for all discovered images in a dataset.

    Returns:
        dict: Summary of camera models, GPS coverage, and coordinate frame rules.
    """
    images_info = manifest.get("images", [])
    exif_records: List[Dict[str, Any]] = []

    cameras_detected = set()
    gps_count = 0

    for item in images_info:
        p = Path(item["path"])
        rec = extract_image_exif(p)
        exif_records.append(rec)

        if rec["camera_make"] or rec["camera_model"]:
            cam_str = f"{rec['camera_make'] or 'Unknown'} {rec['camera_model'] or 'Unknown'}".strip()
            cameras_detected.add(cam_str)

        if rec["has_gps"]:
            gps_count += 1

    total_images = len(images_info)
    gps_percentage = round((gps_count / total_images * 100.0), 1) if total_images > 0 else 0.0
    single_camera_consistent = len(cameras_detected) <= 1

    summary = {
        "dataset_name": manifest.get("dataset_name", ""),
        "total_images": total_images,
        "cameras_detected": sorted(list(cameras_detected)),
        "single_camera_consistent": single_camera_consistent,
        "gps_metadata_available": gps_count > 0,
        "gps_image_count": gps_count,
        "gps_image_percentage": gps_percentage,
        "georeferencing": {
            "photogrammetry_georeferenced": False,
            "coordinate_frame": "PHOTOGRAMMETRIC_LOCAL",
            "crs": None,
            "note": "EXIF GPS metadata present but does NOT constitute authoritative georeferencing. Requires GCP alignment or explicit geo-registration.",
        },
        "exif_details": exif_records,
    }

    # Save summary report
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_file = reports_dir / "photogrammetry_metadata.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"EXIF processing complete: {gps_count}/{total_images} images have GPS metadata ({gps_percentage}%).")
    return summary
