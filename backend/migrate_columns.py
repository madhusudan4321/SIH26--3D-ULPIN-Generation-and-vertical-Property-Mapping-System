"""
Migration script to add missing columns to existing PostgreSQL tables.
"""

from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE buildings ADD COLUMN IF NOT EXISTS ulpin VARCHAR(100);"))
        conn.execute(text("ALTER TABLE buildings ADD COLUMN IF NOT EXISTS geometry_source VARCHAR(50);"))
        conn.execute(text("ALTER TABLE floors ADD COLUMN IF NOT EXISTS geometry_source VARCHAR(50);"))
        conn.execute(text("ALTER TABLE floors ADD COLUMN IF NOT EXISTS floor_geometry geometry(Polygon, 4326);"))
        conn.execute(text("ALTER TABLE properties_3d ADD COLUMN IF NOT EXISTS sub_ulpin VARCHAR(100);"))
        conn.commit()
        print("DB Columns migrated successfully!")

if __name__ == "__main__":
    migrate()
