"""
Document Parser Service

Extracts structured building/property data from uploaded documents.
Supports: PDF, CSV, JSON, GeoJSON.

Design:
- Modular: each format has its own parser function
- Extensible: new formats can be added without modifying existing parsers
- PDF: detects scanned/image PDFs and returns clear error (no OCR yet)
- All parsers produce the same normalized data structure

The normalized output structure is:
{
    "building": {
        "building_id": "B01",
        "name": "...",
        "parcel_id": "P001",
        "latitude": ...,
        "longitude": ...,
        "height": ...,
        "num_floors": ...
    },
    "floors": [
        {
            "floor_number": 1,
            "z_min": 0,
            "z_max": 3,
            "properties": [
                {
                    "unit_id": "S101",
                    "property_type": "commercial",
                    "area": 80,
                    "ror_id": "ROR001",
                    "owner": "...",
                    "land_use": "...",
                    "rights": "...",
                    "geometry": null  // optional GeoJSON polygon
                }
            ]
        }
    ],
    "ror_records": [
        { "ror_id": "...", "owner": "...", ... }
    ],
    "metadata": {
        "source_type": "pdf",
        "crs_detected": "EPSG:4326",
        "warnings": []
    }
}
"""

import csv
import io
import json
from typing import Any

from app.services.crs_handler import ensure_wgs84


# Minimum text length to consider a PDF as having extractable text
PDF_TEXT_THRESHOLD = 50


def parse_document(file_content: bytes, filename: str, content_type: str = "") -> dict:
    """
    Parse a document and extract structured building data.

    Args:
        file_content: Raw file bytes
        filename: Original filename (used for format detection)
        content_type: MIME type (optional)

    Returns:
        Normalized data structure (see module docstring)

    Raises:
        ValueError: If format is unsupported or extraction fails
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        return parse_pdf(file_content)
    elif ext == "csv":
        return parse_csv(file_content)
    elif ext == "json":
        return parse_json(file_content)
    elif ext == "geojson":
        return parse_geojson(file_content)
    else:
        raise ValueError(
            f"Unsupported file format: '.{ext}'. "
            f"Supported formats: PDF, CSV, JSON, GeoJSON."
        )


def parse_pdf(file_content: bytes) -> dict:
    """
    Extract building data from a PDF.

    First checks if the PDF contains extractable text.
    If scanned/image-based: returns clear error (OCR not implemented).
    """
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("pdfplumber is required for PDF processing. Install with: pip install pdfplumber")

    warnings = []
    all_text = ""

    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                all_text += page_text + "\n"
    except Exception as e:
        raise ValueError(f"Failed to open PDF: {e}")

    # Check if PDF has extractable text
    if len(all_text.strip()) < PDF_TEXT_THRESHOLD:
        raise ValueError(
            "This PDF appears to be scanned or image-based. "
            "Text extraction returned insufficient content. "
            "OCR processing is planned for a future update. "
            "Please use a text-based PDF, or enter data manually."
        )

    # Parse the extracted text into structured data
    result = _parse_pdf_text(all_text)
    result["metadata"] = {
        "source_type": "pdf",
        "crs_detected": None,
        "warnings": warnings,
    }
    return result


def _parse_pdf_text(text: str) -> dict:
    """
    Parse extracted PDF text into structured building data.

    Looks for common patterns:
    - BUILDING / BUILDING ID / BUILDING NAME
    - PARCEL / PARCEL ID
    - FLOOR N
    - SHOP/APARTMENT/UNIT + ID + properties
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    building = {
        "building_id": None,
        "name": None,
        "parcel_id": None,
        "latitude": None,
        "longitude": None,
        "height": None,
        "num_floors": None,
    }
    floors = []
    ror_records = []
    current_floor = None
    warnings = []

    for line in lines:
        line_upper = line.upper()

        # Building info
        if "BUILDING ID" in line_upper or "BUILDING_ID" in line_upper:
            building["building_id"] = _extract_value(line)
        elif "BUILDING NAME" in line_upper or "BUILDING:" in line_upper:
            building["name"] = _extract_value(line)
        elif "PARCEL ID" in line_upper or "PARCEL:" in line_upper:
            building["parcel_id"] = _extract_value(line)
        elif "LATITUDE" in line_upper:
            building["latitude"] = _extract_float(line)
        elif "LONGITUDE" in line_upper:
            building["longitude"] = _extract_float(line)
        elif "HEIGHT" in line_upper and "FLOOR" not in line_upper:
            building["height"] = _extract_float(line)
        elif "NUMBER OF FLOORS" in line_upper or "FLOORS:" in line_upper:
            building["num_floors"] = _extract_int(line)

        # Floor detection
        elif line_upper.startswith("FLOOR") and any(c.isdigit() for c in line):
            floor_num = _extract_int(line)
            if floor_num is not None:
                current_floor = {
                    "floor_number": floor_num,
                    "z_min": (floor_num - 1) * 3.0,
                    "z_max": floor_num * 3.0,
                    "properties": [],
                }
                floors.append(current_floor)

        # Property detection
        elif any(kw in line_upper for kw in ["SHOP", "APARTMENT", "UNIT"]):
            if current_floor is not None:
                prop = _parse_property_line(line)
                if prop:
                    current_floor["properties"].append(prop)

        # RoR info within property context
        elif "ROR" in line_upper and ":" in line:
            ror_id = _extract_value(line)
            if ror_id and current_floor and current_floor["properties"]:
                current_floor["properties"][-1]["ror_id"] = ror_id

        elif "OWNER" in line_upper and ":" in line:
            owner = _extract_value(line)
            if owner and current_floor and current_floor["properties"]:
                current_floor["properties"][-1]["owner"] = owner

        elif "AREA" in line_upper and ":" in line:
            area = _extract_float(line)
            if area is not None and current_floor and current_floor["properties"]:
                current_floor["properties"][-1]["area"] = area

        elif "TYPE" in line_upper and ":" in line:
            ptype = _extract_value(line)
            if ptype and current_floor and current_floor["properties"]:
                current_floor["properties"][-1]["property_type"] = ptype.lower()

    if building["num_floors"] is None and floors:
        building["num_floors"] = len(floors)

    return {"building": building, "floors": floors, "ror_records": ror_records}


def _parse_property_line(line: str) -> dict | None:
    """Parse a property line like 'SHOP 101' or 'Apartment 301'."""
    parts = line.split()
    if len(parts) < 2:
        return None

    prop_type = "commercial" if "SHOP" in parts[0].upper() else "residential"
    unit_id = parts[1] if len(parts) > 1 else None

    return {
        "unit_id": unit_id,
        "property_type": prop_type,
        "area": None,
        "ror_id": None,
        "owner": None,
        "land_use": None,
        "rights": None,
        "geometry": None,
    }


def parse_csv(file_content: bytes) -> dict:
    """
    Parse CSV file with building/property data.

    Expected columns (case-insensitive):
    building_id, building_name, parcel_id, floor_number,
    unit_id, property_type, area, ror_id, owner, land_use, rights
    """
    text = file_content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    # Normalize column names to lowercase
    rows = []
    for row in reader:
        normalized = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        rows.append(normalized)

    if not rows:
        raise ValueError("CSV file is empty or has no data rows.")

    # Extract building info from first row
    first = rows[0]
    building = {
        "building_id": first.get("building_id"),
        "name": first.get("building_name") or first.get("name"),
        "parcel_id": first.get("parcel_id"),
        "latitude": _safe_float(first.get("latitude")),
        "longitude": _safe_float(first.get("longitude")),
        "height": _safe_float(first.get("height")),
        "num_floors": None,
    }

    # Group by floor
    floor_map = {}
    ror_records = []
    for row in rows:
        floor_num = _safe_int(row.get("floor_number") or row.get("floor"))
        if floor_num is None:
            floor_num = 1

        if floor_num not in floor_map:
            floor_map[floor_num] = {
                "floor_number": floor_num,
                "z_min": (floor_num - 1) * 3.0,
                "z_max": floor_num * 3.0,
                "properties": [],
            }

        prop = {
            "unit_id": row.get("unit_id") or row.get("shop_id") or row.get("apartment_id"),
            "property_type": (row.get("property_type") or row.get("type") or "").lower() or None,
            "area": _safe_float(row.get("area")),
            "ror_id": row.get("ror_id"),
            "owner": row.get("owner") or row.get("owner_name"),
            "land_use": row.get("land_use"),
            "rights": row.get("rights"),
            "geometry": None,
        }
        floor_map[floor_num]["properties"].append(prop)

        # Collect RoR if present
        if prop["ror_id"]:
            ror_records.append({
                "ror_id": prop["ror_id"],
                "owner": prop["owner"],
                "land_use": prop["land_use"],
                "rights": prop["rights"],
            })

    floors = sorted(floor_map.values(), key=lambda f: f["floor_number"])
    building["num_floors"] = len(floors)

    return {
        "building": building,
        "floors": floors,
        "ror_records": ror_records,
        "metadata": {"source_type": "csv", "crs_detected": None, "warnings": []},
    }


def parse_json(file_content: bytes) -> dict:
    """
    Parse JSON file with building/property data.

    Expects a JSON object with at least "building" and "floors" keys,
    matching the normalized data structure.
    """
    try:
        data = json.loads(file_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError("JSON must be an object with 'building' and 'floors' keys.")

    building = data.get("building", {})
    floors = data.get("floors", [])
    ror_records = data.get("ror_records", [])

    # Validate minimum fields
    if not building.get("building_id") and not building.get("name"):
        raise ValueError("JSON must include building_id or name in the 'building' object.")

    # Ensure floors have properties arrays
    for floor in floors:
        if "properties" not in floor:
            floor["properties"] = []

    return {
        "building": building,
        "floors": floors,
        "ror_records": ror_records,
        "metadata": {"source_type": "json", "crs_detected": None, "warnings": []},
    }


def parse_geojson(file_content: bytes) -> dict:
    """
    Parse GeoJSON file with building/property geometry.

    Handles CRS detection and transformation to EPSG:4326.
    Extracts property data from feature properties.
    """
    try:
        data = json.loads(file_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid GeoJSON: {e}")

    # CRS handling
    data, crs_detected = ensure_wgs84(data)

    features = data.get("features", [])
    if not features:
        raise ValueError("GeoJSON contains no features.")

    # Extract building and property info from features
    building = {
        "building_id": None,
        "name": None,
        "parcel_id": None,
        "latitude": None,
        "longitude": None,
        "height": None,
        "num_floors": None,
    }

    floor_map = {}
    ror_records = []
    warnings = []

    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        # Try to extract building info from first feature
        if not building["building_id"]:
            building["building_id"] = props.get("building_id") or props.get("bldg_id")
            building["name"] = props.get("building_name") or props.get("name")
            building["parcel_id"] = props.get("parcel_id")

        floor_num = props.get("floor") or props.get("floor_number") or 1
        if isinstance(floor_num, str):
            floor_num = _safe_int(floor_num) or 1

        if floor_num not in floor_map:
            floor_map[floor_num] = {
                "floor_number": floor_num,
                "z_min": (floor_num - 1) * 3.0,
                "z_max": floor_num * 3.0,
                "properties": [],
            }

        prop = {
            "unit_id": props.get("unit_id") or props.get("shop_id") or props.get("id"),
            "property_type": (props.get("property_type") or props.get("type") or "").lower() or None,
            "area": _safe_float(props.get("area")),
            "ror_id": props.get("ror_id"),
            "owner": props.get("owner") or props.get("owner_name"),
            "land_use": props.get("land_use"),
            "rights": props.get("rights"),
            "geometry": geom,  # Actual unit geometry from GeoJSON
        }
        floor_map[floor_num]["properties"].append(prop)

        if prop["ror_id"]:
            ror_records.append({
                "ror_id": prop["ror_id"],
                "owner": prop["owner"],
                "land_use": prop["land_use"],
                "rights": prop["rights"],
            })

    floors = sorted(floor_map.values(), key=lambda f: f["floor_number"])
    building["num_floors"] = len(floors)

    return {
        "building": building,
        "floors": floors,
        "ror_records": ror_records,
        "metadata": {
            "source_type": "geojson",
            "crs_detected": crs_detected,
            "warnings": warnings,
        },
    }


# ── Helper Functions ────────────────────────────────────────

def _extract_value(line: str) -> str | None:
    """Extract value after colon or equals sign."""
    for sep in [":", "=", "-"]:
        if sep in line:
            val = line.split(sep, 1)[1].strip()
            if val:
                return val
    return line.strip() or None


def _extract_float(line: str) -> float | None:
    """Extract first float from a line."""
    import re
    match = re.search(r"[\d.]+", line)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def _extract_int(line: str) -> int | None:
    """Extract first integer from a line."""
    import re
    match = re.search(r"\d+", line)
    if match:
        try:
            return int(match.group())
        except ValueError:
            pass
    return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None
