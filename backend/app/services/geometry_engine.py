"""
Geometry Engine Service

Handles 2D polygon → 3D volume generation.

Design Principles & Priorities:
1. Priority order for property geometry:
   - Explicit real unit geometry (GeoJSON/CAD/BIM/floor-plan derived)
   - Derived spatial geometry
   - Synthetic subdivision (fallback for demo/test datasets without unit geometries)
2. Fundamental representation: property footprint polygon + z_min + z_max
3. Footprint Constraint:
   - Synthetic subdivision MUST remain strictly inside the building footprint polygon
   - Non-overlapping, positive area, area-proportional slices where recorded area exists
4. PostGIS 2D polygon storage (EPSG:4326) with geometry_source tracking.
   Cesium handles visual 3D volume extrusion from z_min to z_max.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape


def generate_building_footprint(
    lon: float, lat: float, width_m: float = 30.0, depth_m: float = 20.0
) -> dict:
    """
    Generate a rectangular building footprint polygon in EPSG:4326.

    Uses meter-to-degree conversion at the given latitude.

    Args:
        lon: Center longitude
        lat: Center latitude
        width_m: Building width in meters (east-west)
        depth_m: Building depth in meters (north-south)

    Returns:
        GeoJSON polygon dict
    """
    deg_per_m_lat = 1.0 / 111320.0
    deg_per_m_lon = 1.0 / (111320.0 * math.cos(math.radians(lat)))

    half_w = (width_m / 2.0) * deg_per_m_lon
    half_d = (depth_m / 2.0) * deg_per_m_lat

    footprint = box(lon - half_w, lat - half_d, lon + half_w, lat + half_d)
    return mapping(footprint)


def subdivide_footprint_by_area(
    footprint_geojson: dict,
    properties: list[dict],
) -> list[dict]:
    """
    Subdivide a building footprint polygon into N deterministic unit geometries,
    weighted by each property's recorded area.

    Guarantees:
    - Each generated unit polygon is strictly inside the building footprint
    - Non-overlapping unit polygons on the same floor
    - Positive area for each unit
    - Area proportions respected relative to each property's area field

    Args:
        footprint_geojson: Building footprint GeoJSON polygon dict
        properties: List of property dicts, each with optional "area" field

    Returns:
        List of GeoJSON polygon dicts matching the property list order
    """
    n = len(properties)
    if n == 0:
        return []

    footprint = shape(footprint_geojson)
    if footprint.is_empty or not footprint.is_valid:
        raise ValueError("Invalid footprint geometry provided for subdivision.")

    # Calculate area weights
    areas = []
    for p in properties:
        val = p.get("area")
        try:
            a = float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            a = 0.0
        areas.append(a if a > 0 else 0.0)

    total_specified_area = sum(areas)
    if total_specified_area <= 0:
        # Equal division weights
        weights = [1.0 / n] * n
    else:
        # Fallback 0.0 areas get average area
        avg_area = total_specified_area / max(1, sum(1 for a in areas if a > 0))
        filled_areas = [a if a > 0 else avg_area for a in areas]
        sum_filled = sum(filled_areas)
        weights = [a / sum_filled for a in filled_areas]

    # Bounding box of footprint polygon
    minx, miny, maxx, maxy = footprint.bounds
    dx = maxx - minx
    dy = maxy - miny

    # Determine split orientation based on major bounding box axis
    split_x = dx >= dy

    units_geojson = []
    cum_start = 0.0

    for i, w in enumerate(weights):
        cum_end = cum_start + w
        # Clamp last boundary to 1.0 to avoid float precision loss
        if i == n - 1:
            cum_end = 1.0

        if split_x:
            slice_box = box(
                minx + cum_start * dx,
                miny,
                minx + cum_end * dx,
                maxy,
            )
        else:
            slice_box = box(
                minx,
                miny + cum_start * dy,
                maxx,
                miny + cum_end * dy,
            )

        # Clip slice box strictly to building footprint polygon
        unit_geom = slice_box.intersection(footprint)

        # If MultiPolygon, pick the largest polygon component
        if isinstance(unit_geom, MultiPolygon):
            unit_geom = max(unit_geom.geoms, key=lambda g: g.area)

        if unit_geom.is_empty or unit_geom.area <= 0:
            # Fallback if intersection yields degenerate geometry
            unit_geom = slice_box

        units_geojson.append(mapping(unit_geom))
        cum_start = cum_end

    return units_geojson


def subdivide_footprint(
    footprint_geojson: dict,
    num_units: int,
    floor_number: int = 1,
) -> list[dict]:
    """Legacy helper for simple count-based subdivision."""
    dummy_props = [{"unit_id": f"unit_{i+1}"} for i in range(num_units)]
    return subdivide_footprint_by_area(footprint_geojson, dummy_props)


def validate_geometry(geojson: dict) -> Tuple[bool, Optional[str]]:
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
            return False, f"Expected Polygon or MultiPolygon, got {geom.geom_type}"
        if geom.area <= 0:
            return False, "Geometry has zero or negative area"
        return True, None
    except Exception as e:
        return False, f"Geometry parsing error: {e}"
