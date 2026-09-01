"""
Building Processor Service

Converts normalized building data into database records.
This is the CONVERGENCE POINT — both document upload and
manual entry use this same processor.

TRANSACTION SAFETY:
Uses a proper SQLAlchemy outer transaction for the complete
building-processing operation. Overwrites execute inside the same
transaction. All records commit together or all roll back.
"""

import uuid
from typing import Optional

from shapely.geometry import mapping, shape
from sqlalchemy.orm import Session

from app.models import Building, Floor, ModelAsset, Parcel, ProcessingJob, Property3D, RoR
from app.services.geometry_engine import (
    generate_building_footprint,
    subdivide_footprint_by_area,
)
from app.services.ulpin_generator import generate_ulpin


class ProcessingError(Exception):
    """Raised when building processing fails."""
    pass


def process_building(
    db: Session,
    building_data: dict,
    data_source: str = "uploaded_document",
    overwrite: bool = False,
) -> dict:
    """
    Process normalized building data into database records.

    ATOMIC & IDEMPOTENT: Uses a single transaction. Overwrites delete
    existing records inside the same transaction.

    Args:
        db: SQLAlchemy session
        building_data: Normalized data from document_parser or manual entry
        data_source: Data creation source (uploaded_document / manual / DEMO_DATA)
        overwrite: If True, replace building if building_id already exists

    Returns:
        Summary dict with created record counts

    Raises:
        ProcessingError: If any step fails (transaction is rolled back)
    """
    try:
        bld_info = building_data.get("building", {})
        floors_data = building_data.get("floors", [])
        ror_data = building_data.get("ror_records", [])

        building_id = bld_info.get("building_id")
        if not building_id:
            building_id = f"B-{uuid.uuid4().hex[:8].upper()}"

        building_ulpin = bld_info.get("ulpin") or f"ULPIN-{building_id}"

        # ── Handle Duplicate / Overwrite ──
        existing_building = db.query(Building).filter(Building.building_id == building_id).first()
        if existing_building:
            if not overwrite:
                raise ProcessingError(
                    f"Building '{building_id}' already exists. "
                    f"Choose overwrite to replace it or use a different building_id."
                )
            # Atomic overwrite: delete existing building (cascades to floors, properties, assets)
            _delete_building_internal(db, existing_building)
            db.flush()

        # ── 1. Create or get Parcel ──
        parcel_id = bld_info.get("parcel_id") or "P001"
        parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
        if not parcel:
            parcel = Parcel(
                parcel_id=parcel_id,
                source=data_source,
            )
            db.add(parcel)
            db.flush()

        # ── 2. Derive Height & Footprint ──
        lat = bld_info.get("latitude") or 28.6134
        lon = bld_info.get("longitude") or 77.2300

        # Calculate building height: preserve uploaded height if present, else derive max(z_max)
        calc_height = bld_info.get("height")
        if not calc_height or float(calc_height) <= 0:
            max_z = 0.0
            for f in floors_data:
                z = f.get("z_max", 0.0)
                if z > max_z:
                    max_z = z
            calc_height = max_z if max_z > 0 else (len(floors_data) * 3.0 or 12.0)

        # Footprint geometry
        footprint_geojson = bld_info.get("footprint")
        if not footprint_geojson:
            footprint_geojson = generate_building_footprint(lon=lon, lat=lat)

        footprint_shape = shape(footprint_geojson)
        footprint_wkt = f"SRID=4326;{footprint_shape.wkt}"

        b_geom_source = bld_info.get("geometry_source", "synthetic_subdivision")

        # Create Building record
        building = Building(
            building_id=building_id,
            ulpin=building_ulpin,
            name=bld_info.get("name") or f"Building {building_id}",
            parcel_uuid=parcel.id,
            latitude=lat,
            longitude=lon,
            height=calc_height,
            num_floors=bld_info.get("num_floors") or len(floors_data),
            ground_elevation=bld_info.get("ground_elevation", 0.0),
            footprint=footprint_wkt,
            source=data_source,
            geometry_source=b_geom_source,
        )
        db.add(building)
        db.flush()

        # ── 3. Create RoR Records ──
        ror_count = 0
        for rd in ror_data:
            ror_id = rd.get("ror_id")
            if not ror_id:
                continue
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

        # ── 4. Create Floors and 3D Property Geometries ──
        floor_count = 0
        prop_count = 0
        ulpin_count = 0
        ror_link_count = 0

        for floor_data in floors_data:
            floor_number = floor_data.get("floor_number", floor_count + 1)
            floor_id = f"{building_id}-F{floor_number:02d}"

            f_geom_source = floor_data.get("geometry_source") or b_geom_source

            floor = Floor(
                floor_id=floor_id,
                building_uuid=building.id,
                floor_number=floor_number,
                z_min=floor_data.get("z_min", (floor_number - 1) * 3.0),
                z_max=floor_data.get("z_max", floor_number * 3.0),
                elevation_source=data_source,
                geometry_source=f_geom_source,
            )
            db.add(floor)
            db.flush()
            floor_count += 1

            floor_properties = floor_data.get("properties", [])
            if not floor_properties:
                continue

            # Check if explicit unit geometries exist (geometry / geometry_geojson)
            has_explicit_geoms = any(
                (p.get("geometry") and isinstance(p["geometry"], dict) and p["geometry"].get("type")) or
                (p.get("geometry_geojson") and isinstance(p["geometry_geojson"], dict) and p["geometry_geojson"].get("type"))
                for p in floor_properties
            )

            if has_explicit_geoms:
                unit_geoms = [
                    p.get("geometry") or p.get("geometry_geojson")
                    for p in floor_properties
                ]
                default_geom_source = "geojson"
            else:
                # Subdivide footprint deterministically for all units on this floor
                unit_geoms = subdivide_footprint_by_area(footprint_geojson, floor_properties)
                default_geom_source = "synthetic_subdivision"

            # Create individual 3D properties with geometries
            for idx, prop_data in enumerate(floor_properties):
                unit_id = prop_data.get("unit_id") or f"U{floor_number}0{idx + 1}"
                prop_id = prop_data.get("property_id") or f"{building_id}-{unit_id}"

                # Prototype ULPIN & Sub-ULPIN
                ulpin = prop_data.get("ulpin") or generate_ulpin(
                    parcel_id=parcel_id,
                    building_id=building_id,
                    floor_number=floor_number,
                    unit_id=unit_id,
                    property_type=prop_data.get("property_type"),
                )

                sub_ulpin = prop_data.get("sub_ulpin") or f"SUB-ULPIN-{building_id}-{unit_id}"

                # Format unit PostGIS geometry
                geometry_wkt = None
                geom_source = prop_data.get("geometry_source") or default_geom_source

                u_geom = unit_geoms[idx] if idx < len(unit_geoms) else None
                if u_geom:
                    try:
                        g_shape = shape(u_geom)
                        if g_shape.is_valid and not g_shape.is_empty:
                            geometry_wkt = f"SRID=4326;{g_shape.wkt}"
                    except Exception:
                        pass

                prop = Property3D(
                    property_id=prop_id,
                    ulpin=ulpin,
                    sub_ulpin=sub_ulpin,
                    building_uuid=building.id,
                    floor_uuid=floor.id,
                    unit_id=unit_id,
                    property_type=prop_data.get("property_type"),
                    area=prop_data.get("area"),
                    geometry=geometry_wkt,
                    z_min=prop_data.get("z_min") if prop_data.get("z_min") is not None else floor.z_min,
                    z_max=prop_data.get("z_max") if prop_data.get("z_max") is not None else floor.z_max,
                    ror_id=prop_data.get("ror_id"),
                    data_source=data_source,
                    geometry_source=geom_source,
                    verification_status="unverified",
                )
                db.add(prop)
                prop_count += 1
                ulpin_count += 1

                if prop_data.get("ror_id"):
                    ror_link_count += 1

                # Create RoR record if needed
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

        # ── COMMIT — Atomic transaction ──
        db.commit()

        return {
            "building_id": building_id,
            "parcel_id": parcel_id,
            "floors": floor_count,
            "properties": prop_count,
            "ulpins": ulpin_count,
            "ror_records": ror_count,
            "ror_links": ror_link_count,
        }

    except ProcessingError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise ProcessingError(f"Building processing failed: {e}")


def _delete_building_internal(db: Session, building: Building):
    """
    Internal helper to delete a building and associated records within a session.
    """
    # Delete model assets
    db.query(ModelAsset).filter(ModelAsset.building_uuid == building.id).delete()

    # Unlink datasets
    db.query(ProcessingJob).filter(ProcessingJob.building_uuid == building.id).delete()

    # Delete properties and floors
    db.query(Property3D).filter(Property3D.building_uuid == building.id).delete()
    db.query(Floor).filter(Floor.building_uuid == building.id).delete()

    # Delete building
    db.delete(building)
