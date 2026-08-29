"""
Parcel ORM Model

Represents a cadastral parcel (land plot).
Uses PostGIS Geometry for 2D parcel boundary.
"""

import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Parcel(Base):
    __tablename__ = "parcels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_id = Column(String(50), unique=True, nullable=False, index=True)
    survey_number = Column(String(100), nullable=True)
    geometry_2d = Column(
        Geometry("POLYGON", srid=4326, spatial_index=True), nullable=True
    )
    area = Column(Float, nullable=True)
    crs_source = Column(String(50), nullable=True, default="EPSG:4326")
    source = Column(String(50), nullable=False, default="manual")

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
    buildings = relationship("Building", back_populates="parcel")
    ror_records = relationship("RoR", back_populates="parcel")

    def __repr__(self):
        return f"<Parcel {self.parcel_id}>"
