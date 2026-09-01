"""
Building ORM Model

Represents a physical building on a parcel.
Uses UUID foreign key to Parcel.id for type-safe relationship.
"""

import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Building(Base):
    __tablename__ = "buildings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    building_id = Column(String(50), unique=True, nullable=False, index=True)
    ulpin = Column(String(100), nullable=True, index=True)
    name = Column(String(200), nullable=True)

    # UUID FK to Parcel — type-safe relationship
    parcel_uuid = Column(
        UUID(as_uuid=True), ForeignKey("parcels.id"), nullable=False
    )

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    num_floors = Column(Integer, nullable=True)
    ground_elevation = Column(Float, default=0.0)
    source = Column(String(50), nullable=False, default="manual")
    geometry_source = Column(String(50), nullable=True, default="synthetic_subdivision")

    # Building footprint polygon stored in PostGIS
    footprint = Column(
        Geometry("POLYGON", srid=4326, spatial_index=True), nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    parcel = relationship("Parcel", back_populates="buildings")
    floors = relationship(
        "Floor", back_populates="building", cascade="all, delete-orphan"
    )
    properties = relationship(
        "Property3D", back_populates="building", cascade="all, delete-orphan"
    )
    datasets = relationship("Dataset", back_populates="building")
    model_assets = relationship(
        "ModelAsset", back_populates="building", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Building {self.building_id} ({self.name})>"
