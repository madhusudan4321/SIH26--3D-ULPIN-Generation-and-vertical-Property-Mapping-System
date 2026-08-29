"""
RoR (Record of Rights) ORM Model

Represents legal ownership/rights information for a property.
Linked to properties via property3d.ror_id → ror.ror_id.
Uses UUID FK to Parcel.id for type-safe parcel relationship.

Legal/ownership metadata is kept SEPARATE from geometry.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RoR(Base):
    __tablename__ = "ror"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ror_id = Column(String(50), unique=True, nullable=False, index=True)

    # UUID FK to Parcel — type-safe relationship (correction #2)
    parcel_uuid = Column(
        UUID(as_uuid=True), ForeignKey("parcels.id"), nullable=True
    )

    owner_name = Column(String(200), nullable=True)
    area = Column(Float, nullable=True)
    land_use = Column(String(100), nullable=True)
    rights = Column(String(100), nullable=True)
    source = Column(String(50), nullable=False, default="synthetic_demo")

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
    parcel = relationship("Parcel", back_populates="ror_records")

    def __repr__(self):
        return f"<RoR {self.ror_id} owner={self.owner_name}>"
