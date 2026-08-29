"""
Manual Entry Router

Endpoints:
  POST /api/manual-entry — Submit complete manual building + floors + properties

Uses the SAME building_processor.py pipeline as document upload.
Both workflows converge at the same processing point.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.building import BuildingCreate
from app.services.building_processor import ProcessingError, process_building

router = APIRouter(prefix="/api", tags=["manual-entry"])


@router.post("/manual-entry")
async def manual_entry(data: BuildingCreate, db: Session = Depends(get_db)):
    """
    Create a building via manual data entry.

    Accepts building info, floors, and properties.
    Uses the SAME processing pipeline as document upload.
    All records commit together or roll back.
    """
    # Convert Pydantic schema to normalized data dict
    # (same structure as document parser output)
    building_data = {
        "building": {
            "building_id": data.building_id,
            "name": data.name,
            "parcel_id": data.parcel_id,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "height": data.height,
            "num_floors": data.num_floors or len(data.floors),
        },
        "floors": [],
        "ror_records": data.ror_records or [],
    }

    for floor in data.floors:
        floor_data = {
            "floor_number": floor.floor_number,
            "z_min": floor.z_min,
            "z_max": floor.z_max,
            "properties": [],
        }
        building_data["floors"].append(floor_data)

    # Map properties to floors by floor_number
    for prop in data.properties:
        target_floor = None
        for fd in building_data["floors"]:
            if fd["floor_number"] == prop.floor_number:
                target_floor = fd
                break

        if not target_floor:
            # Auto-create floor if it doesn't exist
            target_floor = {
                "floor_number": prop.floor_number,
                "z_min": (prop.floor_number - 1) * 3.0,
                "z_max": prop.floor_number * 3.0,
                "properties": [],
            }
            building_data["floors"].append(target_floor)

        prop_data = {
            "unit_id": prop.unit_id,
            "property_type": prop.property_type,
            "area": prop.area,
            "ror_id": prop.ror_id,
            "geometry": prop.geometry_geojson,
        }
        target_floor["properties"].append(prop_data)

    # Sort floors by floor_number
    building_data["floors"].sort(key=lambda f: f["floor_number"])

    # Update num_floors
    building_data["building"]["num_floors"] = len(building_data["floors"])

    # Process using the SAME pipeline as document upload
    try:
        summary = process_building(
            db=db,
            building_data=building_data,
            data_source="manual",
        )

        return {
            "status": "complete",
            "summary": summary,
            "message": "Building created successfully via manual entry.",
        }

    except ProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual entry failed: {e}")
