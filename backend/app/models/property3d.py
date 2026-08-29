"""
Property3D ORM Model

Represents an individual 3D property unit (shop, apartment, etc.)
within a floor of a building.

Key design decisions (per user corrections):
- geometry is NULLABLE — unit geometry may not be available
- geometry_source tracks provenance (real vs synthetic vs unavailable)
- data_source tracks how the property data was created
- ror_id is NULLABLE — some properties may lack RoR records
- ulpin has a UNIQUE constraint (prototype ULPIN)
"""

import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Property3D(Base):
    __tablename__ = "properties_3d"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(String(50), unique=True, nullable=False, index=True)
    ulpin = Column(String(100), unique=True, nullable=False, index=True)

    # UUID FKs to Building and Floor
    building_uuid = Column(
        UUID(as_uuid=True), ForeignKey("buildings.id"), nullable=False
    )
    floor_uuid = Column(
        UUID(as_uuid=True), ForeignKey("floors.id"), nullable=False
    )

    unit_id = Column(String(50), nullable=True)
    property_type = Column(String(50), nullable=True)  # commercial/residential/mixed
    area = Column(Float, nullable=True)

    # Geometry is NULLABLE — may not be available for every unit.
    # When NULL, the UI must indicate "geometry unavailable".
    # Never silently substitute building footprint as real unit boundary.
    geometry = Column(
        Geometry("POLYGON", srid=4326, spatial_index=True), nullable=True
    )

    z_min = Column(Float, nullable=True)
    z_max = Column(Float, nullable=True)

    # RoR relationship — nullable (some properties may lack RoR)
    ror_id = Column(String(50), nullable=True, index=True)

    # Provenance tracking
    data_source = Column(
        String(50), nullable=False, default="manual"
    )  # uploaded_document / manual / synthetic_demo / geojson
    geometry_source = Column(
        String(50), nullable=True
    )  # uploaded_geojson / floor_plan / manual / synthetic_subdivision / building_footprint / NULL
    verification_status = Column(
        String(50), nullable=False, default="unverified"
    )  # unverified / user_verified / survey_verified

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
    building = relationship("Building", back_populates="properties")
    floor = relationship("Floor", back_populates="properties")

    def __repr__(self):
        return f"<Property3D {self.property_id} ulpin={self.ulpin}>"
