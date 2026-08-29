"""
Health Check Router

Endpoints:
  GET /api/health     — Basic application health
  GET /api/health/db  — PostgreSQL + PostGIS verification

Does NOT expose:
  - DATABASE_URL
  - database password
  - credentials
  - environment variables
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health():
    """Basic application health check."""
    return {"status": "ok", "service": "3D ULPIN System API"}


@router.get("/db")
async def health_db(db: Session = Depends(get_db)):
    """
    Verify PostgreSQL connectivity, database name, and PostGIS availability.

    Response example:
    {
        "database": "connected",
        "database_name": "ulpin_db",
        "postgis": "3.6.2"
    }
    """
    try:
        db_name = db.execute(text("SELECT current_database()")).scalar()
        postgis_version = db.execute(text("SELECT PostGIS_Version()")).scalar()

        return {
            "database": "connected",
            "database_name": db_name,
            "postgis": postgis_version,
        }
    except Exception as e:
        return {
            "database": "error",
            "database_name": None,
            "postgis": None,
            "error": str(e),
        }
