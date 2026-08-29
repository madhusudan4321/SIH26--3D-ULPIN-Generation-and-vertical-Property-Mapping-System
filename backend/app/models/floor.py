"""
Floor ORM Model

Represents a single floor/storey within a building.
z_min / z_max define the vertical extent relative to ground.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Floor(Base):
    __tablename__ = "floors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    floor_id = Column(String(50), unique=True, nullable=False, index=True)

    # UUID FK to Building
    building_uuid = Column(
        UUID(as_uuid=True), ForeignKey("buildings.id"), nullable=False
    )

    floor_number = Column(Integer, nullable=False)
    z_min = Column(Float, nullable=False, default=0.0)
    z_max = Column(Float, nullable=False, default=3.0)
    elevation_source = Column(String(50), nullable=True, default="manual")

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
    building = relationship("Building", back_populates="floors")
    properties = relationship(
        "Property3D", back_populates="floor", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Floor {self.floor_id} (#{self.floor_number})>"
