"""
Database Initialization

Creates all tables using CREATE TABLE IF NOT EXISTS.
Does NOT drop existing tables or delete existing data.
Safe to run multiple times.

For the prototype, this replaces Alembic. When the schema
stabilizes, migrate to Alembic for proper versioned migrations.
"""

import os
import sys

# Add parent to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import inspect, text

from app.database import engine, Base

# Import all models so Base.metadata knows about them
from app.models import (  # noqa: F401
    Parcel,
    Building,
    Floor,
    Property3D,
    RoR,
    Dataset,
    ProcessingJob,
    ModelAsset,
)


def init_db():
    """Create all tables that don't already exist."""
    print("Connecting to database...")

    with engine.connect() as conn:
        db_name = conn.execute(text("SELECT current_database()")).scalar()
        print(f"Database: {db_name}")

        postgis = conn.execute(text("SELECT PostGIS_Version()")).scalar()
        print(f"PostGIS: {postgis}")

    print("\nCreating tables (IF NOT EXISTS)...")
    Base.metadata.create_all(bind=engine)

    # Column migrations for existing tables
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE buildings ADD COLUMN IF NOT EXISTS footprint GEOMETRY(POLYGON, 4326);"))
        conn.commit()

    # Verify
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = [
        "parcels",
        "buildings",
        "floors",
        "properties_3d",
        "ror",
        "datasets",
        "processing_jobs",
        "model_assets",
    ]

    print("\nTable verification:")
    all_ok = True
    for table in expected:
        exists = table in tables
        status = "[OK]" if exists else "[MISSING]"
        print(f"  {status}  {table}")
        if not exists:
            all_ok = False

    if all_ok:
        print(f"\nAll {len(expected)} tables created successfully.")
    else:
        print("\nWARNING: Some tables are missing!")
        sys.exit(1)


if __name__ == "__main__":
    init_db()
