"""
3D ULPIN System — Backend Application

FastAPI application with CORS, routers, and database initialization.
Extends the existing M1 stub with full API functionality.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Import routers
from app.routers import health, buildings, properties, upload, manual_entry, lidar, photogrammetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown lifecycle.

    On startup: create tables if they don't exist (safe, no drops).
    """
    # Create tables on startup (CREATE TABLE IF NOT EXISTS)
    Base.metadata.create_all(bind=engine)
    print("Database tables verified.")
    yield
    # Shutdown: nothing to clean up for now


app = FastAPI(
    title="3D ULPIN System API",
    description="3D ULPIN Generation and Vertical Property Mapping System",
    version="0.2.0",
    lifespan=lifespan,
)

from fastapi.middleware.gzip import GZipMiddleware

# CORS — allow frontend dev server and docker container origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://localhost:80",
        "http://localhost",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for fast JSON transmission of 3D point cloud assets
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Register routers
app.include_router(health.router)
app.include_router(buildings.router)
app.include_router(properties.router)
app.include_router(upload.router)
app.include_router(manual_entry.router)
app.include_router(lidar.router)
app.include_router(photogrammetry.router)

