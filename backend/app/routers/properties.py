"""
Properties Router

Endpoints:
  GET  /api/properties/{ulpin}      — Get property by ULPIN / Sub-ULPIN
  GET  /api/properties/{ulpin}/ror  — Get linked RoR record
  GET  /api/search                  — Search by ULPIN, Sub-ULPIN, building_id, property_id, unit_id, ror_id
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Building, Floor, Parcel, Property3D, RoR
from app.schemas.building import PropertyDetail, PropertyOut, RoROut

router = APIRouter(prefix="/api", tags=["properties"])


@router.get("/properties/{ulpin}", response_model=PropertyDetail)
async def get_property_by_ulpin(ulpin: str, db: Session = Depends(get_db)):
    """Get a property by its ULPIN or Sub-ULPIN, including linked RoR."""
    prop = (
        db.query(Property3D)
        .options(
            joinedload(Property3D.building).joinedload(Building.parcel),
            joinedload(Property3D.floor),
        )
        .filter(
            or_(
                Property3D.ulpin == ulpin,
                Property3D.sub_ulpin == ulpin,
                Property3D.property_id == ulpin,
            )
        )
        .first()
    )

    if not prop:
        raise HTTPException(status_code=404, detail=f"Property with ULPIN/Sub-ULPIN '{ulpin}' not found")

    building = prop.building
    floor = prop.floor

    # Look up RoR if available
    ror_out = None
    if prop.ror_id:
        ror = db.query(RoR).filter(RoR.ror_id == prop.ror_id).first()
        if ror:
            ror_out = RoROut(
                ror_id=ror.ror_id,
                owner_name=ror.owner_name,
                area=ror.area,
                land_use=ror.land_use,
                rights=ror.rights,
                source=ror.source,
            )

    # Convert PostGIS geometry to GeoJSON dict if present
    geom_geojson = None
    if prop.geometry is not None:
        try:
            from geoalchemy2.shape import to_shape
            from shapely.geometry import mapping
            geom_geojson = mapping(to_shape(prop.geometry))
        except Exception:
            pass

    default_sub_ulpin = f"SUB-ULPIN-{building.building_id if building else 'BLD'}-{prop.unit_id if prop.unit_id else 'UNIT'}"

    return PropertyDetail(
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
        ror=ror_out,
        building_name=building.name if building else None,
        parcel_id=building.parcel.parcel_id if building and building.parcel else None,
    )


@router.get("/properties/{ulpin}/ror", response_model=Optional[RoROut])
async def get_property_ror(ulpin: str, db: Session = Depends(get_db)):
    """Get the RoR record linked to a property."""
    prop = (
        db.query(Property3D)
        .filter(
            or_(
                Property3D.ulpin == ulpin,
                Property3D.sub_ulpin == ulpin,
                Property3D.property_id == ulpin,
            )
        )
        .first()
    )

    if not prop:
        raise HTTPException(status_code=404, detail=f"Property with ULPIN '{ulpin}' not found")

    if not prop.ror_id:
        return None

    ror = db.query(RoR).filter(RoR.ror_id == prop.ror_id).first()
    if not ror:
        return None

    return RoROut(
        ror_id=ror.ror_id,
        owner_name=ror.owner_name,
        area=ror.area,
        land_use=ror.land_use,
        rights=ror.rights,
        source=ror.source,
    )


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    db: Session = Depends(get_db),
):
    """
    Search across buildings, properties, ULPINs, Sub-ULPINs, Unit IDs, and RoR IDs.
    """
    query_str = f"%{q}%"
    results = []

    # Search properties by ULPIN, sub_ulpin, property_id, unit_id, or ror_id
    props = (
        db.query(Property3D)
        .options(
            joinedload(Property3D.building),
            joinedload(Property3D.floor),
        )
        .filter(
            or_(
                Property3D.ulpin.ilike(query_str),
                Property3D.sub_ulpin.ilike(query_str),
                Property3D.property_id.ilike(query_str),
                Property3D.unit_id.ilike(query_str),
                Property3D.ror_id.ilike(query_str),
            )
        )
        .limit(20)
        .all()
    )

    for p in props:
        sub = p.sub_ulpin or f"SUB-ULPIN-{p.building.building_id if p.building else 'BLD'}-{p.unit_id}"
        results.append({
            "type": "property",
            "id": p.ulpin,
            "ulpin": p.ulpin,
            "sub_ulpin": sub,
            "property_id": p.property_id,
            "unit_id": p.unit_id,
            "ror_id": p.ror_id,
            "building_id": p.building.building_id if p.building else None,
            "building_name": p.building.name if p.building else None,
            "floor_number": p.floor.floor_number if p.floor else None,
            "property_type": p.property_type,
            "label": f"{p.unit_id} — {sub} ({p.building.name if p.building and p.building.name else p.building_id})",
            "latitude": p.building.latitude if p.building else None,
            "longitude": p.building.longitude if p.building else None,
        })

    # Search buildings by building_id, ulpin, or name
    buildings = (
        db.query(Building)
        .options(joinedload(Building.parcel))
        .filter(
            or_(
                Building.building_id.ilike(query_str),
                Building.ulpin.ilike(query_str),
                Building.name.ilike(query_str),
            )
        )
        .limit(10)
        .all()
    )

    for b in buildings:
        # Skip if already found via property search
        if not any(r.get("building_id") == b.building_id for r in results if r.get("type") == "building"):
            results.append({
                "type": "building",
                "id": b.building_id,
                "building_id": b.building_id,
                "ulpin": b.ulpin,
                "building_name": b.name,
                "label": f"{b.name or b.building_id} ({b.building_id})",
                "parcel_id": b.parcel.parcel_id if b.parcel else None,
                "num_floors": b.num_floors,
                "latitude": b.latitude,
                "longitude": b.longitude,
                "height": b.height,
            })

    # Search parcels by parcel_id
    parcels = (
        db.query(Parcel)
        .filter(Parcel.parcel_id.ilike(query_str))
        .limit(5)
        .all()
    )

    for p in parcels:
        results.append({
            "type": "parcel",
            "parcel_id": p.parcel_id,
        })

    return {"results": results, "count": len(results)}
