"""
Building-related Pydantic schemas.

Request and response schemas for building, floor, and related endpoints.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Floor Schemas ──────────────────────────────────────────

class FloorBase(BaseModel):
    floor_number: int
    z_min: float = 0.0
    z_max: float = 3.0

class FloorCreate(FloorBase):
    floor_id: Optional[str] = None  # Auto-generated if not provided

class FloorOut(FloorBase):
    id: UUID
    floor_id: str
    elevation_source: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Property Schemas ───────────────────────────────────────

class PropertyBase(BaseModel):
    unit_id: Optional[str] = None
    property_type: Optional[str] = None  # commercial / residential / mixed
    area: Optional[float] = None
    z_min: Optional[float] = None
    z_max: Optional[float] = None
    ror_id: Optional[str] = None

class PropertyCreate(PropertyBase):
    property_id: Optional[str] = None  # Auto-generated if not provided
    floor_number: int  # Used to link to the correct floor
    geometry_geojson: Optional[dict] = None  # Optional GeoJSON polygon

class PropertyOut(PropertyBase):
    id: UUID
    property_id: str
    ulpin: str
    building_id: str = Field(default="", description="Human-readable building_id")
    floor_id: str = Field(default="", description="Human-readable floor_id")
    floor_number: Optional[int] = None
    data_source: str
    geometry_source: Optional[str] = None
    geometry_available: bool = False
    verification_status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── RoR Schema ─────────────────────────────────────────────

class RoROut(BaseModel):
    ror_id: str
    owner_name: Optional[str] = None
    area: Optional[float] = None
    land_use: Optional[str] = None
    rights: Optional[str] = None
    source: str

    model_config = {"from_attributes": True}


# ─── Building Schemas ───────────────────────────────────────

class BuildingBase(BaseModel):
    building_id: Optional[str] = None
    name: Optional[str] = None
    parcel_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    height: Optional[float] = None
    num_floors: Optional[int] = None

class BuildingCreate(BuildingBase):
    """Used for manual building creation."""
    floors: List[FloorCreate] = []
    properties: List[PropertyCreate] = []
    ror_records: Optional[List[dict]] = None  # Optional RoR data

class BuildingSummary(BaseModel):
    """Lightweight building info for list endpoints."""
    id: UUID
    building_id: str
    name: Optional[str] = None
    parcel_id: str
    num_floors: Optional[int] = None
    property_count: int = 0
    source: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class BuildingDetail(BaseModel):
    """Full building details with floors and properties."""
    id: UUID
    building_id: str
    name: Optional[str] = None
    parcel_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    height: Optional[float] = None
    num_floors: Optional[int] = None
    ground_elevation: float = 0.0
    source: str
    created_at: Optional[datetime] = None
    floors: List[FloorOut] = []
    properties: List[PropertyOut] = []

    model_config = {"from_attributes": True}


# ─── Property Detail (with RoR) ────────────────────────────

class PropertyDetail(PropertyOut):
    """Property with linked RoR information."""
    ror: Optional[RoROut] = None
    building_name: Optional[str] = None
    parcel_id: Optional[str] = None
