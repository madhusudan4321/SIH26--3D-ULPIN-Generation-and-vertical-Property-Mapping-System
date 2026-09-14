"""
LiDAR Metadata & Georeferencing Configuration Module

Defines the LiDAR local coordinate metadata schema and geospatial transformation
configuration structure.

Architectural Rule:
Separates LiDAR LOCAL FRAME from GEOGRAPHIC REFERENCE FRAME.
State: "GEOSPATIAL TRANSFORM PENDING"
"""

from typing import Dict, Any, Optional
from pathlib import Path
import pye57

DEFAULT_GEOREFERENCING_CONFIG = {
    "source_crs": None,
    "target_crs": "EPSG:4326",
    "method": "pending",
    "control_points": [],
    "translation": None,
    "rotation": None,
    "scale": None,
    "confidence": None,
    "status": "GEOSPATIAL TRANSFORM PENDING",
}

def get_lidar_georeferencing_config() -> Dict[str, Any]:
    """Return the current geospatial transformation configuration status."""
    return DEFAULT_GEOREFERENCING_CONFIG.copy()

def get_e57_file_info(file_path: str) -> Dict[str, Any]:
    """Inspect file path and basic size info."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"LiDAR file not found: {file_path}")

    size_bytes = path.stat().st_size
    size_gb = round(size_bytes / (1024 ** 3), 3)

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_size_gb": size_gb,
    }
