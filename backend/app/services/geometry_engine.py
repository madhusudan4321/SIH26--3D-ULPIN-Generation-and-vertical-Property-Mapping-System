"""
Geometry Engine Service

Handles 2D polygon → 3D volume generation for the prototype.

Design decisions (per user corrections):
- If individual unit geometry is available → use it
- If unavailable → geometry remains NULL, marked as unavailable
- Optional synthetic subdivision only as explicit demo/approximation
- Never silently present synthetic geometry as real cadastral boundaries

Current scope: 2D polygon → 3D extrusion prototype
Architecture is extensible for future LiDAR/photogrammetry/AI processing.
"""

import math
from typing import Optional

from shapely.geometry import Polygon, box, mapping, shape


def generate_building_footprint(
    lon: float, lat: float, width_m: float = 30.0, depth_m: float = 20.0
) -> dict:
    """
    Generate a rectangular building footprint polygon in EPSG:4326.

    Uses approximate meter-to-degree conversion at the given latitude.

    Args:
        lon: Center longitude
        lat: Center latitude
        width_m: Building width in meters (east-west)
        depth_m: Building depth in meters (north-south)

    Returns:
        GeoJSON polygon dict
    """
    # Approximate degree per meter at this latitude
    deg_per_m_lat = 1.0 / 111320.0
    deg_per_m_lon = 1.0 / (111320.0 * math.cos(math.radians(lat)))

    half_w = (width_m / 2.0) * deg_per_m_lon
    half_d = (depth_m / 2.0) * deg_per_m_lat

    footprint = box(lon - half_w, lat - half_d, lon + half_w, lat + half_d)
    return mapping(footprint)


def subdivide_footprint(
    footprint_geojson: dict,
    num_units: int,
    floor_number: int,
) -> list[dict]:
    """
    Generate synthetic rectangular subdivisions of a building footprint.

    IMPORTANT: These are APPROXIMATE/SYNTHETIC geometries for
    demonstration purposes only. They do NOT represent real
    cadastral property boundaries.

    Each returned geometry has geometry_source = "synthetic_subdivision".

    Args:
        footprint_geojson: Building footprint GeoJSON polygon
        num_units: Number of units to subdivide into
        floor_number: Floor number (for labeling)

    Returns:
        List of GeoJSON polygon dicts, one per unit
    """
    if num_units <= 0:
        return []

    footprint = shape(footprint_geojson)
    minx, miny, maxx, maxy = footprint.bounds

    # Subdivide along the longer axis
    width = maxx - minx
    height = maxy - miny

    units = []
    if width >= height:
        # Subdivide east-west
        unit_width = width / num_units
        for i in range(num_units):
            unit_box = box(
                minx + i * unit_width, miny,
                minx + (i + 1) * unit_width, maxy,
            )
            # Clip to footprint
            unit_geom = unit_box.intersection(footprint)
            if not unit_geom.is_empty:
                units.append(mapping(unit_geom))
    else:
        # Subdivide north-south
        unit_height = height / num_units
        for i in range(num_units):
            unit_box = box(
                minx, miny + i * unit_height,
                maxx, miny + (i + 1) * unit_height,
            )
            unit_geom = unit_box.intersection(footprint)
            if not unit_geom.is_empty:
                units.append(mapping(unit_geom))

    return units


def validate_geometry(geojson: dict) -> tuple[bool, Optional[str]]:
    """
    Validate a GeoJSON geometry.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        geom = shape(geojson)
        if geom.is_empty:
            return False, "Geometry is empty"
        if not geom.is_valid:
            return False, f"Invalid geometry: {geom.geom_type}"
        if geom.geom_type not in ("Polygon", "MultiPolygon"):
            return False, f"Expected Polygon, got {geom.geom_type}"
        return True, None
    except Exception as e:
        return False, f"Geometry parsing error: {e}"
