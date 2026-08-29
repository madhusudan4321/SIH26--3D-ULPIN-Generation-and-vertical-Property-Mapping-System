"""
CRS Handler Service

Detects source CRS from uploaded spatial data and transforms
coordinates to the project CRS (EPSG:4326).

Does NOT silently misinterpret coordinates.
Records source CRS for provenance.
"""

from typing import Optional, Tuple

import pyproj
from shapely.geometry import shape, mapping
from shapely.ops import transform


# Project CRS — all stored geometry is in EPSG:4326
PROJECT_CRS = "EPSG:4326"


def detect_crs(geojson_data: dict) -> Optional[str]:
    """
    Detect CRS from GeoJSON data.

    GeoJSON spec (RFC 7946) mandates WGS84 (EPSG:4326),
    but some files include a `crs` field from older specs.

    Returns:
        CRS string like "EPSG:4326" or None if not detected.
    """
    # Check for explicit CRS field (older GeoJSON spec)
    crs_info = geojson_data.get("crs")
    if crs_info:
        props = crs_info.get("properties", {})
        name = props.get("name", "")
        if name:
            # Try to parse EPSG from OGC URN or name
            if "EPSG" in name.upper():
                # e.g. "urn:ogc:def:crs:EPSG::4326" or "EPSG:4326"
                parts = name.split(":")
                for i, p in enumerate(parts):
                    if p.upper() == "EPSG" and i + 1 < len(parts):
                        code = parts[-1]  # Take the last part
                        if code.isdigit():
                            return f"EPSG:{code}"
            return name  # Return raw name if we can't parse

    # No CRS field — per RFC 7946, assume WGS84
    return "EPSG:4326"


def transform_geometry(geom_dict: dict, source_crs: str, target_crs: str = PROJECT_CRS) -> dict:
    """
    Transform a GeoJSON geometry from source_crs to target_crs.

    Args:
        geom_dict: GeoJSON geometry dict ({"type": "Polygon", "coordinates": [...]})
        source_crs: Source CRS string (e.g. "EPSG:32643")
        target_crs: Target CRS string (default: EPSG:4326)

    Returns:
        Transformed GeoJSON geometry dict in target CRS.
    """
    if source_crs == target_crs:
        return geom_dict

    try:
        transformer = pyproj.Transformer.from_crs(
            source_crs, target_crs, always_xy=True
        )
        geom = shape(geom_dict)
        transformed = transform(transformer.transform, geom)
        return mapping(transformed)
    except Exception as e:
        raise ValueError(f"CRS transformation failed ({source_crs} -> {target_crs}): {e}")


def validate_coordinates_wgs84(lon: float, lat: float) -> bool:
    """Check if coordinates are plausible WGS84 values."""
    return -180 <= lon <= 180 and -90 <= lat <= 90


def ensure_wgs84(geojson_data: dict) -> Tuple[dict, str]:
    """
    Ensure all geometries in a GeoJSON FeatureCollection are in EPSG:4326.

    Returns:
        Tuple of (transformed GeoJSON data, detected source CRS)
    """
    source_crs = detect_crs(geojson_data)

    if source_crs and source_crs != PROJECT_CRS:
        # Transform all feature geometries
        if "features" in geojson_data:
            for feature in geojson_data["features"]:
                if feature.get("geometry"):
                    feature["geometry"] = transform_geometry(
                        feature["geometry"], source_crs
                    )
        elif "geometry" in geojson_data:
            geojson_data["geometry"] = transform_geometry(
                geojson_data["geometry"], source_crs
            )

    return geojson_data, source_crs or "EPSG:4326"
