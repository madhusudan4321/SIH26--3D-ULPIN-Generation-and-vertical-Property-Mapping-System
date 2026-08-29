"""
ProcessingJob ORM Model

Tracks the status and progress of building processing operations.
Each confirmed dataset triggers a processing job.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    dataset_uuid = Column(
        UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True
    )
    building_uuid = Column(
        UUID(as_uuid=True), ForeignKey("buildings.id"), nullable=True
    )

    status = Column(
        String(50), nullable=False, default="pending"
    )  # pending / validating / processing / generating / saving / complete / error
    progress = Column(Integer, default=0)  # 0-100
    error = Column(String(500), nullable=True)
    result_summary = Column(
        JSON, nullable=True
    )  # {"floors": 4, "properties": 8, "ulpins": 8, "ror_links": 6}

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    dataset = relationship("Dataset", back_populates="processing_jobs")

    def __repr__(self):
        return f"<ProcessingJob status={self.status} progress={self.progress}%>"
