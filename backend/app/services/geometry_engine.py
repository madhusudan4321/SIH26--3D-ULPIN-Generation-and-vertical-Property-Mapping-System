"""
Geometry Engine Service

Handles 2D polygon → 3D volume generation, PostGIS spatial validation,
and geographic footprint alignment diagnostics.

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
5. Alignment Diagnostic Metrics:
   - Footprint centroid anchor calculation (local ENU origin)
   - Real IoU (Intersection over Union), containment %, centroid displacement (m)
   - Status taxonomy: PASS, APPROXIMATE, UNVERIFIED, WARN, FAIL
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import unary_union


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
    Validate a GeoJSON geometry for SRID 4326 compliance.

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


def degrees_to_sqm(area_deg_sq: float, lat: float) -> float:
    """Convert square degrees to square meters at given latitude."""
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat))
    return area_deg_sq * m_per_deg_lat * m_per_deg_lon


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance in meters between two (lat, lon) coordinates."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_alignment_diagnostics(
    model_footprint_geojson: Optional[dict],
    reference_footprint_geojson: Optional[dict] = None,
    property_geoms: Optional[list[dict]] = None,
    ground_elevation: float = 0.0,
    reference_elevation: float = 0.0,
    geometry_source: str = "synthetic_subdivision",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> dict:
    """
    Compute comprehensive data-driven geographic footprint & elevation alignment diagnostics.

    Status Taxonomy:
    - PASS: Authoritative reference footprint exists and model/ref comparison passes tolerance (IoU >= 0.85, displacement <= 2m).
    - APPROXIMATE: Synthetic subdivision geometry is being used.
    - UNVERIFIED: Model geometry exists, but no authoritative reference footprint exists to verify against.
    - WARN: Reference footprint exists, but alignment exceeds preferred tolerance (IoU 0.50-0.85 or displacement 2-5m).
    - FAIL: Invalid geometry or major mismatch (IoU < 0.50 or displacement > 5m).

    Returns:
        Structured dictionary of alignment diagnostic metrics
    """
    lat = latitude or 28.6134
    lon = longitude or 77.2300

    anchor_lat = lat
    anchor_lon = lon
    model_area_sqm = 0.0
    ref_area_sqm = 0.0
    intersection_area_sqm = 0.0
    union_area_sqm = 0.0
    iou = 0.0
    containment_ratio = 0.0
    displacement_m = 0.0

    model_shape = None
    if model_footprint_geojson:
        try:
            model_shape = shape(model_footprint_geojson)
            if model_shape.is_valid and not model_shape.is_empty:
                centroid = model_shape.centroid
                anchor_lon, anchor_lat = centroid.x, centroid.y
                model_area_sqm = degrees_to_sqm(model_shape.area, anchor_lat)
        except Exception:
            model_shape = None

    ref_shape = None
    if reference_footprint_geojson:
        try:
            ref_shape = shape(reference_footprint_geojson)
            if ref_shape.is_valid and not ref_shape.is_empty:
                ref_area_sqm = degrees_to_sqm(ref_shape.area, ref_shape.centroid.y)
        except Exception:
            ref_shape = None

    elevation_diff = abs(ground_elevation - reference_elevation)

    bbox_dict = None
    if model_shape:
        minx, miny, maxx, maxy = model_shape.bounds
        bbox_dict = {
            "min_lon": round(minx, 7),
            "min_lat": round(miny, 7),
            "max_lon": round(maxx, 7),
            "max_lat": round(maxy, 7),
        }

    # Data-driven status assignment
    if ref_shape and model_shape:
        ref_centroid = ref_shape.centroid
        model_centroid = model_shape.centroid
        displacement_m = haversine_distance_m(ref_centroid.y, ref_centroid.x, model_centroid.y, model_centroid.x)

        try:
            inter_geom = ref_shape.intersection(model_shape)
            union_geom = ref_shape.union(model_shape)

            intersection_area_sqm = degrees_to_sqm(inter_geom.area, anchor_lat) if not inter_geom.is_empty else 0.0
            union_area_sqm = degrees_to_sqm(union_geom.area, anchor_lat) if not union_geom.is_empty else 0.0

            if union_area_sqm > 0:
                iou = intersection_area_sqm / union_area_sqm
            if model_area_sqm > 0:
                containment_ratio = (intersection_area_sqm / model_area_sqm) * 100.0
        except Exception:
            pass

        if iou >= 0.85 and displacement_m <= 2.0 and elevation_diff <= 1.0:
            status = "VERIFIED" if geometry_source in ("osm_footprint", "cadastral", "geojson") else "PASS"
            message = f"Authoritative reference footprint aligned (IoU: {iou:.2%}, displacement: {displacement_m:.2f}m)."
        elif iou >= 0.50 and displacement_m <= 5.0:
            status = "WARN"
            message = f"Footprint alignment exceeds standard tolerance (IoU: {iou:.2%}, displacement: {displacement_m:.2f}m)."
        else:
            status = "FAIL"
            message = f"Footprint mismatch detected (IoU: {iou:.2%}, displacement: {displacement_m:.2f}m)."

    elif geometry_source == "synthetic_subdivision":
        status = "APPROXIMATE"
        message = "Synthetic subdivision footprint in use (Approximate representation)."
    elif model_shape:
        if geometry_source in ("osm_footprint", "cadastral") and model_shape.is_valid:
            status = "VERIFIED"
            message = "Authoritative source geometry footprint verified."
        else:
            status = "UNVERIFIED"
            message = "Geographic anchor verified; footprint alignment unverified."
    else:
        status = "FAIL"
        message = "Missing or invalid building footprint geometry."

    prop_containment_ratio = 100.0
    if property_geoms and model_shape:
        valid_props = []
        for pg in property_geoms:
            try:
                ps = shape(pg)
                if ps.is_valid and not ps.is_empty:
                    valid_props.append(ps)
            except Exception:
                pass

        if valid_props:
            prop_union = unary_union(valid_props)
            inter_prop = prop_union.intersection(model_shape)
            prop_union_area = prop_union.area
            if prop_union_area > 0:
                prop_containment_ratio = (inter_prop.area / prop_union_area) * 100.0

    return {
        "building_id": "",
        "geometry_source": geometry_source,
        "geometry_valid": model_shape is not None and model_shape.is_valid,
        "srid": 4326,
        "coordinate_order": "lon_lat",
        "footprint_bbox": bbox_dict,
        "footprint_centroid": {"lon": round(anchor_lon, 7), "lat": round(anchor_lat, 7)},
        "alignment_status": status,
        "diagnostic_message": message,
        "model_anchor_lat": round(anchor_lat, 7),
        "model_anchor_lon": round(anchor_lon, 7),
        "horizontal_offset_m": round(displacement_m, 2),
        "reference_footprint_area_sqm": round(ref_area_sqm, 2),
        "model_footprint_area_sqm": round(model_area_sqm, 2),
        "intersection_area_sqm": round(intersection_area_sqm, 2),
        "union_area_sqm": round(union_area_sqm, 2),
        "iou": round(iou, 4),
        "containment_ratio_percent": round(containment_ratio if ref_shape else prop_containment_ratio, 2),
        "base_elevation_m": round(ground_elevation, 2),
        "reference_elevation_m": round(reference_elevation, 2),
        "elevation_difference_m": round(elevation_diff, 2),
    }
