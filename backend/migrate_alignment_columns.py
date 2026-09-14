"""
Database Migration Script — Add Geographic Alignment & Elevation Columns

Executes DDL statements on PostgreSQL to add alignment and elevation tracking
columns to the buildings table.
"""

from sqlalchemy import text
from app.database import engine

def migrate():
    statements = [
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS reference_elevation FLOAT DEFAULT 0.0;",
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS elevation_source VARCHAR(50) DEFAULT 'manual';",
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS heading FLOAT DEFAULT 0.0;",
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS model_anchor_lat FLOAT;",
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS model_anchor_lon FLOAT;",
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS alignment_status VARCHAR(50) DEFAULT 'UNVERIFIED';",
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS alignment_error_m FLOAT DEFAULT 0.0;",
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS reference_footprint geometry(Polygon,4326);",
    ]

    with engine.begin() as conn:
        for stmt in statements:
            print(f"Executing DDL: {stmt}")
            conn.execute(text(stmt))
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
