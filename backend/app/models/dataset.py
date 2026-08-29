"""
Dataset ORM Model

Tracks uploaded datasets (documents, GeoJSON, etc.) and their
extraction/processing status. Stores extracted structured data
for user review before confirmation.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(String(50), unique=True, nullable=False, index=True)

    # Building linkage — nullable until the dataset is confirmed/processed
    building_uuid = Column(
        UUID(as_uuid=True), ForeignKey("buildings.id"), nullable=True
    )

    source_type = Column(String(50), nullable=False)  # pdf / csv / json / geojson
    uploaded_files = Column(JSON, nullable=True)  # [{"name": "...", "path": "..."}]
    crs_detected = Column(String(50), nullable=True)  # Detected CRS of spatial data
    processing_status = Column(
        String(50), nullable=False, default="uploaded"
    )  # uploaded / extracting / review / confirmed / processing / complete / error
    extracted_data = Column(JSON, nullable=True)  # Parsed structured data for review

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    building = relationship("Building", back_populates="datasets")
    processing_jobs = relationship(
        "ProcessingJob", back_populates="dataset", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Dataset {self.dataset_id} status={self.processing_status}>"
