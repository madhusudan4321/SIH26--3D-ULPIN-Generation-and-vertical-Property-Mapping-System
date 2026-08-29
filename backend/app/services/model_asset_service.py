"""
Model Asset Service

Manages model asset file storage and database references.

Architecture:
- PostgreSQL stores metadata + file path reference (MODEL_ASSET table)
- Actual model files stored in backend/storage/models/
- Files are NOT stored inside PostgreSQL rows

When a building is requested:
  DB → find model asset → load file from storage → send to frontend/Cesium
"""

import json
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Building, ModelAsset


def create_model_asset(db: Session, building: Building) -> ModelAsset:
    """
    Create a model asset reference for a processed building.

    Stores building metadata as a JSON file in local storage
    and creates a MODEL_ASSET record pointing to it.
    """
    # Create storage directory for this building
    building_dir = os.path.join(settings.MODEL_DIR, building.building_id)
    os.makedirs(building_dir, exist_ok=True)

    # Determine version
    existing_assets = (
        db.query(ModelAsset)
        .filter(ModelAsset.building_uuid == building.id)
        .all()
    )
    version = len(existing_assets) + 1

    # Create versioned directory
    version_dir = os.path.join(building_dir, f"v{version}")
    os.makedirs(version_dir, exist_ok=True)

    # Save metadata JSON
    metadata = {
        "building_id": building.building_id,
        "name": building.name,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "latitude": building.latitude,
        "longitude": building.longitude,
        "height": building.height,
        "num_floors": building.num_floors,
        "ground_elevation": building.ground_elevation,
    }

    metadata_path = os.path.join(version_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Relative path for DB reference
    rel_path = os.path.join(building.building_id, f"v{version}", "metadata.json")

    # Create DB record
    asset = ModelAsset(
        building_uuid=building.id,
        asset_type="metadata_json",
        file_path=rel_path,
        format="json",
        version=version,
    )
    db.add(asset)

    return asset


def get_latest_model_asset(db: Session, building_id: str) -> dict | None:
    """
    Get the latest model asset for a building.

    Returns metadata dict or None if no asset exists.
    """
    from app.models import Building

    building = db.query(Building).filter(Building.building_id == building_id).first()
    if not building:
        return None

    asset = (
        db.query(ModelAsset)
        .filter(ModelAsset.building_uuid == building.id)
        .order_by(ModelAsset.version.desc())
        .first()
    )

    if not asset:
        return None

    # Load the metadata file
    full_path = os.path.join(settings.MODEL_DIR, asset.file_path)
    if os.path.exists(full_path):
        with open(full_path, "r") as f:
            return json.load(f)

    return {
        "building_id": building.building_id,
        "asset_type": asset.asset_type,
        "file_path": asset.file_path,
        "version": asset.version,
    }
