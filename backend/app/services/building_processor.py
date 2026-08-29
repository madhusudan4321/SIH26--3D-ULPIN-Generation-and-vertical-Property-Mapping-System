"""
Building Processor Service

Converts normalized building data into database records.
This is the CONVERGENCE POINT — both document upload and
manual entry use this same processor.

TRANSACTION SAFETY (Correction #3):
Uses a proper SQLAlchemy outer transaction for the complete
building-processing operation. All records commit together,
or all records roll back. No partial buildings in the database.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from shapely.geometry import shape, mapping
from sqlalchemy.orm import Session

from app.models import Building, Floor, ModelAsset, Parcel, ProcessingJob, Property3D, RoR
from app.services.ulpin_generator import generate_ulpin


class ProcessingError(Exception):
    """Raised when building processing fails."""
    pass


def process_building(db: Session, building_data: dict, data_source: str = "uploaded_document") -> dict:
    """
    Process normalized building data into database records.

    This is the single processing pipeline used by BOTH document
    upload and manual entry workflows.

    ATOMIC: Uses an outer transaction. All records commit together
    or all records roll back. No partial buildings in the database.

    Args:
        db: SQLAlchemy session (caller must NOT have an active transaction)
        building_data: Normalized data from document_parser or manual entry
        data_source: How the data was created (uploaded_document / manual / DEMO_DATA)

    Returns:
        Summary dict with created record counts

    Raises:
        ProcessingError: If any step fails (transaction is rolled back)
    """
    try:
        # Begin outer transaction
        bld_info = building_data.get("building", {})
        floors_data = building_data.get("floors", [])
        ror_data = building_data.get("ror_records", [])

        # ── 1. Create or get Parcel ──
        parcel_id = bld_info.get("parcel_id")
        if not parcel_id:
            parcel_id = f"P-{uuid.uuid4().hex[:8].upper()}"

        parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
        if not parcel:
            parcel = Parcel(
                parcel_id=parcel_id,
                source=data_source,
            )
            db.add(parcel)
            db.flush()

        # ── 2. Create Building ──
        building_id = bld_info.get("building_id")
        if not building_id:
            building_id = f"B-{uuid.uuid4().hex[:8].upper()}"

        # Check if building already exists
        existing = db.query(Building).filter(Building.building_id == building_id).first()
        if existing:
            raise ProcessingError(
                f"Building '{building_id}' already exists. "
                f"Delete it first or use a different building_id."
            )

        building = Building(
            building_id=building_id,
            name=bld_info.get("name"),
            parcel_uuid=parcel.id,
            latitude=bld_info.get("latitude"),
            longitude=bld_info.get("longitude"),
            height=bld_info.get("height"),
            num_floors=bld_info.get("num_floors") or len(floors_data),
            ground_elevation=bld_info.get("ground_elevation", 0.0),
            source=data_source,
        )
        db.add(building)
        db.flush()

        # ── 3. Create RoR Records ──
        ror_count = 0
        for rd in ror_data:
            ror_id = rd.get("ror_id")
            if not ror_id:
                continue
            # Skip if RoR already exists
            existing_ror = db.query(RoR).filter(RoR.ror_id == ror_id).first()
            if not existing_ror:
                ror = RoR(
                    ror_id=ror_id,
                    parcel_uuid=parcel.id,
                    owner_name=rd.get("owner"),
                    area=rd.get("area"),
                    land_use=rd.get("land_use"),
                    rights=rd.get("rights"),
                    source=data_source,
                )
                db.add(ror)
                ror_count += 1

        # ── 4. Create Floors and Properties ──
        floor_count = 0
        prop_count = 0
        ulpin_count = 0
        ror_link_count = 0

        for floor_data in floors_data:
            floor_number = floor_data.get("floor_number", floor_count + 1)
            floor_id = f"{building_id}-F{floor_number:02d}"

            floor = Floor(
                floor_id=floor_id,
                building_uuid=building.id,
                floor_number=floor_number,
                z_min=floor_data.get("z_min", (floor_number - 1) * 3.0),
                z_max=floor_data.get("z_max", floor_number * 3.0),
                elevation_source=data_source,
            )
            db.add(floor)
            db.flush()
            floor_count += 1

            # Create properties for this floor
            for prop_data in floor_data.get("properties", []):
                unit_id = prop_data.get("unit_id") or f"{floor_number}0{prop_count + 1}"
                prop_id = f"{building_id}-{unit_id}"

                # Generate ULPIN
                ulpin = generate_ulpin(
                    parcel_id=parcel_id,
                    building_id=building_id,
                    floor_number=floor_number,
                    unit_id=unit_id,
                    property_type=prop_data.get("property_type"),
                )

                # Handle geometry (Correction #1):
                # If unit geometry provided → use it (geometry_source = uploaded_geojson/manual)
                # If no geometry → leave NULL (geometry_source = None)
                geometry_wkt = None
                geometry_source = None

                unit_geom = prop_data.get("geometry")
                if unit_geom and isinstance(unit_geom, dict) and unit_geom.get("type"):
                    try:
                        geom = shape(unit_geom)
                        if geom.is_valid:
                            geometry_wkt = f"SRID=4326;{geom.wkt}"
                            geometry_source = "uploaded_geojson" if data_source != "manual" else "manual"
                    except Exception:
                        pass  # Invalid geometry — leave as NULL

                prop = Property3D(
                    property_id=prop_id,
                    ulpin=ulpin,
                    building_uuid=building.id,
                    floor_uuid=floor.id,
                    unit_id=unit_id,
                    property_type=prop_data.get("property_type"),
                    area=prop_data.get("area"),
                    geometry=geometry_wkt,
                    z_min=floor.z_min,
                    z_max=floor.z_max,
                    ror_id=prop_data.get("ror_id"),
                    data_source=data_source,
                    geometry_source=geometry_source,
                    verification_status="unverified",
                )
                db.add(prop)
                prop_count += 1
                ulpin_count += 1

                if prop_data.get("ror_id"):
                    ror_link_count += 1

                # Also create RoR from property data if not already in ror_data
                if prop_data.get("ror_id") and prop_data.get("owner"):
                    ror_id = prop_data["ror_id"]
                    existing_ror = db.query(RoR).filter(RoR.ror_id == ror_id).first()
                    if not existing_ror:
                        ror = RoR(
                            ror_id=ror_id,
                            parcel_uuid=parcel.id,
                            owner_name=prop_data.get("owner"),
                            area=prop_data.get("area"),
                            land_use=prop_data.get("land_use"),
                            rights=prop_data.get("rights"),
                            source=data_source,
                        )
                        db.add(ror)
                        ror_count += 1

        # ── 5. Create Model Asset Reference ──
        from app.services.model_asset_service import create_model_asset
        create_model_asset(db, building)

        # ── COMMIT — all or nothing ──
        db.commit()

        summary = {
            "building_id": building_id,
            "parcel_id": parcel_id,
            "floors": floor_count,
            "properties": prop_count,
            "ulpins": ulpin_count,
            "ror_records": ror_count,
            "ror_links": ror_link_count,
        }
        return summary

    except ProcessingError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise ProcessingError(f"Building processing failed: {e}")
