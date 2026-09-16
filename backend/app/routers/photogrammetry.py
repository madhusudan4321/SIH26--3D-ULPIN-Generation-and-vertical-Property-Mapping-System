"""
Photogrammetry REST API Router

Endpoints:
- GET  /api/photogrammetry/{dataset}/metadata    — Returns metadata JSON
- GET  /api/photogrammetry/{dataset}/images      — Returns image report JSON
- GET  /api/photogrammetry/{dataset}/sfm         — Returns SfM sparse reconstruction section
- GET  /api/photogrammetry/{dataset}/dense       — Returns pointcloud section
- GET  /api/photogrammetry/{dataset}/validation  — Returns full validation report JSON
- POST /api/photogrammetry/run                   — Executes photogrammetry pipeline
"""

import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings

# Base data directory for photogrammetry outputs (resolves to project root /data)
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

from app.photogrammetry.pipeline import run_photogrammetry_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/photogrammetry", tags=["photogrammetry"])


class PhotogrammetryRunRequest(BaseModel):
    dataset_name: str
    images_dir: str
    matcher: Optional[str] = "exhaustive"
    camera_model: Optional[str] = "SIMPLE_RADIAL"
    single_camera: Optional[bool] = None
    dry_run: Optional[bool] = False


def _get_dataset_reports_dir(dataset_name: str) -> Path:
    return Path(DATA_DIR) / "photogrammetry" / dataset_name / "reports"


def _load_json_report(dataset_name: str, report_filename: str) -> dict:
    reports_dir = _get_dataset_reports_dir(dataset_name)
    report_file = reports_dir / report_filename

    if not report_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report '{report_filename}' for dataset '{dataset_name}' not found. Run photogrammetry pipeline first.",
        )

    try:
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read report '{report_filename}': {str(e)}",
        )


@router.get("/{dataset_name}/metadata")
async def get_photogrammetry_metadata(dataset_name: str):
    """Retrieve EXIF & camera metadata summary."""
    return _load_json_report(dataset_name, "photogrammetry_metadata.json")


@router.get("/{dataset_name}/images")
async def get_image_report(dataset_name: str):
    """Retrieve image quality, blur, exposure, and duplicate report."""
    return _load_json_report(dataset_name, "photogrammetry_image_report.json")


@router.get("/{dataset_name}/validation")
async def get_validation_report(dataset_name: str):
    """Retrieve full unified validation report and readiness assessment."""
    return _load_json_report(dataset_name, "photogrammetry_validation_report.json")


@router.get("/{dataset_name}/sfm")
async def get_sfm_section(dataset_name: str):
    """Retrieve SfM sparse reconstruction statistics."""
    report = _load_json_report(dataset_name, "photogrammetry_validation_report.json")
    return report.get("sfm", {})


@router.get("/{dataset_name}/dense")
async def get_dense_section(dataset_name: str):
    """Retrieve MVS and Open3D point cloud processing statistics."""
    report = _load_json_report(dataset_name, "photogrammetry_validation_report.json")
    return {
        "mvs": report.get("mvs", {}),
        "pointcloud": report.get("pointcloud", {}),
    }


@router.post("/run")
async def trigger_photogrammetry_run(req: PhotogrammetryRunRequest):
    """Trigger photogrammetry pipeline execution."""
    images_path = Path(req.images_dir)
    if not images_path.is_absolute():
        images_path = Path(DATA_DIR) / req.images_dir

    try:
        report = run_photogrammetry_pipeline(
            dataset_name=req.dataset_name,
            images_dir=images_path,
            matcher=req.matcher or "exhaustive",
            camera_model=req.camera_model or "SIMPLE_RADIAL",
            single_camera=req.single_camera,
            dry_run=req.dry_run or False,
        )
        return report
    except Exception as e:
        logger.error(f"Error running photogrammetry pipeline: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Photogrammetry execution failed: {str(e)}",
        )
