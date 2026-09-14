"""
LiDAR API Router

Provides read-only inspection reports, local point cloud sample buffers,
ground/non-ground classified streams, building candidate extraction,
reconstructed 3D mesh serving, and local GeoJSON export for the Aam Khas Bagh LiDAR dataset.

Architectural Rule:
Coordinates served are strictly in LOCAL CARTESIAN METERS (AAM_KHAS_BAGH_LOCAL).
Geospatial status: "LOCAL COORDINATE FRAME — NOT GEOREFERENCED".
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.lidar.lidar_metadata import DEFAULT_GEOREFERENCING_CONFIG

router = APIRouter(prefix="/api/lidar", tags=["lidar"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR = BASE_DIR / "tools"
ROOT_DIR = BASE_DIR.parent

DERIVED_DIR = ROOT_DIR / "data" / "aam_khas_bagh" / "derived"
if not DERIVED_DIR.exists():
    DERIVED_DIR = BASE_DIR / "data" / "aam_khas_bagh" / "derived"


@router.get("/aam_khas_bagh/report")
def get_lidar_report():
    """Return the complete E57 LiDAR metadata report."""
    report_file = TOOLS_DIR / "aam_khas_bagh_lidar_report.json"
    if not report_file.exists():
        raise HTTPException(
            status_code=404,
            detail="LiDAR inspection report not generated yet."
        )
    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/aam_khas_bagh/sample")
def get_lidar_sample():
    """Return the lightweight sampled point cloud for local coordinate visualization."""
    sample_file = TOOLS_DIR / "aam_khas_bagh_sampled_points.json"
    if not sample_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Sampled point cloud asset not generated yet."
        )
    with open(sample_file, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/aam_khas_bagh/georeferencing")
def get_lidar_georeferencing():
    """Return the current geospatial transformation status configuration."""
    return DEFAULT_GEOREFERENCING_CONFIG


@router.get("/aam_khas_bagh/extracted_building")
def get_extracted_building():
    """Return the extracted building geometry and metrics in local coordinates."""
    file_path = DERIVED_DIR / "aam_khas_bagh_extracted_building.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Extracted building data not generated yet. Run extract_aam_khas_bagh_building.py first."
        )
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/aam_khas_bagh/classified_cloud")
def get_classified_cloud():
    """Return ground/non-ground classified point streams and candidates."""
    file_path = DERIVED_DIR / "aam_khas_bagh_classified_cloud.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Classified point cloud asset not generated yet. Run extract_aam_khas_bagh_building.py first."
        )
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/aam_khas_bagh/export_geojson")
def export_local_geojson():
    """Return extracted building footprint as Local GeoJSON."""
    file_path = DERIVED_DIR / "aam_khas_bagh_building_footprint_local.geojson"
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Local GeoJSON footprint asset not generated yet."
        )
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/aam_khas_bagh/mesh_metadata")
def get_mesh_metadata():
    """Return the reconstructed 3D mesh metadata and diagnostics."""
    file_path = DERIVED_DIR / "aam_khas_bagh_mesh_metadata.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Mesh metadata not generated yet. Run reconstruct_aam_khas_bagh_mesh.py first."
        )
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/aam_khas_bagh/mesh")
def get_mesh_ply():
    """Return the reconstructed PLY mesh as a binary file download for Three.js PLYLoader."""
    file_path = DERIVED_DIR / "aam_khas_bagh_hammam_mesh.ply"
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="PLY mesh file not generated yet. Run reconstruct_aam_khas_bagh_mesh.py first."
        )
    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename="aam_khas_bagh_hammam_mesh.ply",
    )

