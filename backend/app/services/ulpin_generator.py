"""
ULPIN Generator Service

Generates deterministic PROTOTYPE 3D ULPINs.

Format: 3D-{parcel_id}-{building_id}-F{floor:02d}-{unit_type}{unit_id}

unit_type:
  S = Shop (commercial)
  A = Apartment (residential)
  U = Unit (mixed / other / unknown)

IMPORTANT: This is a PROTOTYPE ULPIN scheme for SIH 2026.
It is NOT an official Government of India ULPIN.
"""


def get_unit_type_prefix(property_type: str | None) -> str:
    """Map property type to ULPIN unit type prefix."""
    if not property_type:
        return "U"
    pt = property_type.lower().strip()
    if pt in ("commercial", "shop", "retail", "office"):
        return "S"
    elif pt in ("residential", "apartment", "flat", "dwelling"):
        return "A"
    return "U"


def generate_ulpin(
    parcel_id: str,
    building_id: str,
    floor_number: int,
    unit_id: str,
    property_type: str | None = None,
) -> str:
    """
    Generate a deterministic prototype 3D ULPIN.

    Same inputs always produce the same ULPIN.
    Uniqueness is enforced by the database UNIQUE constraint.

    Args:
        parcel_id: Human-readable parcel ID (e.g. "P001")
        building_id: Human-readable building ID (e.g. "B01")
        floor_number: Floor number (1-indexed)
        unit_id: Unit identifier (e.g. "101", "S101", "A301")
        property_type: Optional property type for prefix determination

    Returns:
        ULPIN string like "3D-P001-B01-F01-S101"
    """
    prefix = get_unit_type_prefix(property_type)

    # Clean the unit_id — if it already starts with a type prefix, strip it
    clean_unit = unit_id.lstrip("SAUP-")
    if not clean_unit:
        clean_unit = unit_id

    return f"3D-{parcel_id}-{building_id}-F{floor_number:02d}-{prefix}{clean_unit}"
