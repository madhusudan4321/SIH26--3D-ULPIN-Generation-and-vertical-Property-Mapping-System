"""
Buildings Router

Endpoints:
  GET     /api/buildings                          — List all buildings
  GET     /api/buildings/{building_id}            — Get building with floors + properties
  GET     /api/buildings/{building_id}/properties — Properties for a building
  DELETE  /api/buildings/{building_id}            — Delete building and associated records
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Building, Floor, ModelAsset, Parcel, ProcessingJob, Property3D, RoR
from app.schemas.building import (
    BuildingDetail,
    BuildingSummary,
    FloorOut,
    PropertyOut,
)

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


def _property_to_out(prop: Property3D, building: Building, floor: Floor) -> PropertyOut:
    """Convert a Property3D ORM object to a PropertyOut schema."""
    geom_geojson = None
    if prop.geometry is not None:
        try:
            sh_geom = to_shape(prop.geometry)
            geom_geojson = mapping(sh_geom)
        except Exception:
            pass

    default_sub_ulpin = f"SUB-ULPIN-{building.building_id if building else 'BLD'}-{prop.unit_id if prop.unit_id else 'UNIT'}"

    return PropertyOut(
        id=prop.id,
        property_id=prop.property_id,
        ulpin=prop.ulpin,
        sub_ulpin=prop.sub_ulpin or default_sub_ulpin,
        building_id=building.building_id if building else "",
        floor_id=floor.floor_id if floor else "",
        floor_number=floor.floor_number if floor else None,
        unit_id=prop.unit_id,
        property_type=prop.property_type,
        area=prop.area,
        z_min=prop.z_min,
        z_max=prop.z_max,
        ror_id=prop.ror_id,
        data_source=prop.data_source,
        geometry_source=prop.geometry_source or "synthetic_subdivision",
        geometry_available=prop.geometry is not None,
        geometry_geojson=geom_geojson,
        verification_status=prop.verification_status,
        created_at=prop.created_at,
    )


@router.get("", response_model=list[BuildingSummary])
async def list_buildings(db: Session = Depends(get_db)):
    """List all buildings with summary info."""
    buildings = (
        db.query(Building)
        .options(joinedload(Building.parcel), joinedload(Building.properties))
        .all()
    )

    result = []
    for b in buildings:
        result.append(
            BuildingSummary(
                id=b.id,
                building_id=b.building_id,
                ulpin=b.ulpin,
                name=b.name,
                parcel_id=b.parcel.parcel_id if b.parcel else "",
                latitude=b.latitude,
                longitude=b.longitude,
                height=b.height,
                num_floors=b.num_floors,
                property_count=len(b.properties),
                source=b.source,
                geometry_source=b.geometry_source,
                created_at=b.created_at,
            )
        )
    return result


@router.get("/{building_id}", response_model=BuildingDetail)
async def get_building(building_id: str, db: Session = Depends(get_db)):
    """Get full building details with floors and properties."""
    building = (
        db.query(Building)
        .options(
            joinedload(Building.parcel),
            joinedload(Building.floors),
            joinedload(Building.properties).joinedload(Property3D.floor),
        )
        .filter(Building.building_id == building_id)
        .first()
    )

    if not building:
        raise HTTPException(status_code=404, detail=f"Building '{building_id}' not found")

    floors_out = [
        FloorOut(
            id=f.id,
            floor_id=f.floor_id,
            floor_number=f.floor_number,
            z_min=f.z_min,
            z_max=f.z_max,
            elevation_source=f.elevation_source,
            geometry_source=f.geometry_source,
            created_at=f.created_at,
        )
        for f in sorted(building.floors, key=lambda f: f.floor_number)
    ]

    props_out = [
        _property_to_out(p, building, p.floor)
        for p in building.properties
    ]

    footprint_geojson = None
    if building.footprint is not None:
        try:
            footprint_geojson = mapping(to_shape(building.footprint))
        except Exception:
            pass

    return BuildingDetail(
        id=building.id,
        building_id=building.building_id,
        ulpin=building.ulpin,
        name=building.name,
        parcel_id=building.parcel.parcel_id if building.parcel else "",
        latitude=building.latitude,
        longitude=building.longitude,
        height=building.height,
        num_floors=building.num_floors,
        ground_elevation=building.ground_elevation,
        footprint_geojson=footprint_geojson,
        source=building.source,
        geometry_source=building.geometry_source,
        created_at=building.created_at,
        floors=floors_out,
        properties=props_out,
    )


@router.get("/{building_id}/properties", response_model=list[PropertyOut])
async def get_building_properties(building_id: str, db: Session = Depends(get_db)):
    """Get all properties for a building."""
    building = (
        db.query(Building)
        .options(
            joinedload(Building.properties).joinedload(Property3D.floor),
        )
        .filter(Building.building_id == building_id)
        .first()
    )

    if not building:
        raise HTTPException(status_code=404, detail=f"Building '{building_id}' not found")

    return [
        _property_to_out(p, building, p.floor)
        for p in building.properties
    ]


@router.delete("/{building_id}")
async def delete_building(building_id: str, db: Session = Depends(get_db)):
    """
    Delete a building and all associated records atomically.

    Cascades deletion to:
    - Floors
    - Property 3D geometries & records
    - Model assets
    - Processing jobs / datasets
    """
    building = db.query(Building).filter(Building.building_id == building_id).first()
    if not building:
        raise HTTPException(status_code=404, detail=f"Building '{building_id}' not found")

    try:
        # Delete related model assets
        db.query(ModelAsset).filter(ModelAsset.building_uuid == building.id).delete()

        # Delete processing jobs
        db.query(ProcessingJob).filter(ProcessingJob.building_uuid == building.id).delete()

        # Delete properties & floors
        db.query(Property3D).filter(Property3D.building_uuid == building.id).delete()
        db.query(Floor).filter(Floor.building_uuid == building.id).delete()

        # Delete building
        db.delete(building)
        db.commit()

        return {
            "status": "deleted",
            "building_id": building_id,
            "message": f"Building '{building_id}' and all associated records deleted successfully.",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete building '{building_id}': {e}")
