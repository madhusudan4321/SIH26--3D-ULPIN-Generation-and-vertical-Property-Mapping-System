"""
ModelAsset ORM Model

Stores metadata/reference to 3D model asset files.
Actual model files are stored in backend/storage/models/.
PostgreSQL stores the file path reference, NOT the binary data.

When a building is requested:
  Database → find model asset → load file from storage → send to Cesium
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ModelAsset(Base):
    __tablename__ = "model_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    building_uuid = Column(
        UUID(as_uuid=True), ForeignKey("buildings.id"), nullable=False
    )

    asset_type = Column(
        String(50), nullable=False
    )  # cesium_tileset / glb / metadata_json
    file_path = Column(
        String(500), nullable=False
    )  # Relative path in backend/storage/models/
    format = Column(String(50), nullable=False)  # 3dtiles / glb / json
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    building = relationship("Building", back_populates="model_assets")

    def __repr__(self):
        return f"<ModelAsset building={self.building_uuid} type={self.asset_type} v{self.version}>"
