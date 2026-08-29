"""
Upload Router

Endpoints:
  POST /api/upload                       — Upload document (PDF/CSV/JSON/GeoJSON)
  GET  /api/upload/{dataset_id}/review   — Get extracted data for review
  PUT  /api/upload/{dataset_id}/review   — Edit extracted data before confirm
  POST /api/upload/{dataset_id}/confirm  — Confirm → transactional 3D generation → persist
"""

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Dataset, ProcessingJob
from app.services.building_processor import ProcessingError, process_building
from app.services.document_parser import parse_document

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a building document for extraction.

    Supported formats: PDF, CSV, JSON, GeoJSON.
    Returns extracted data for user review before confirmation.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Save uploaded file
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    dataset_id = f"DS-{uuid.uuid4().hex[:8].upper()}"
    safe_name = file.filename.replace(" ", "_")
    file_path = os.path.join(settings.UPLOAD_DIR, f"{dataset_id}_{safe_name}")

    with open(file_path, "wb") as f:
        f.write(content)

    # Parse document
    try:
        extracted = parse_document(content, file.filename, file.content_type or "")
    except ValueError as e:
        # Clean up saved file on parse error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=422, detail=str(e))

    # Create Dataset record
    dataset = Dataset(
        dataset_id=dataset_id,
        source_type=extracted.get("metadata", {}).get("source_type", "unknown"),
        uploaded_files=[{"name": file.filename, "path": file_path}],
        crs_detected=extracted.get("metadata", {}).get("crs_detected"),
        processing_status="review",
        extracted_data=extracted,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": dataset_id,
        "status": "review",
        "source_type": dataset.source_type,
        "crs_detected": dataset.crs_detected,
        "extracted_data": extracted,
        "message": "Document parsed successfully. Review the extracted data and confirm.",
    }


@router.get("/{dataset_id}/review")
async def get_review_data(dataset_id: str, db: Session = Depends(get_db)):
    """Get extracted data for review/editing."""
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    return {
        "dataset_id": dataset.dataset_id,
        "status": dataset.processing_status,
        "source_type": dataset.source_type,
        "crs_detected": dataset.crs_detected,
        "extracted_data": dataset.extracted_data,
    }


@router.put("/{dataset_id}/review")
async def update_review_data(
    dataset_id: str,
    updated_data: dict,
    db: Session = Depends(get_db),
):
    """
    Update extracted data after user review/editing.

    The user can:
    - Edit property details
    - Add new properties
    - Remove properties
    - Correct building info
    - Add/remove RoR records
    """
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    if dataset.processing_status not in ("review", "uploaded"):
        raise HTTPException(
            status_code=400,
            detail=f"Dataset is in '{dataset.processing_status}' state. Can only edit during 'review'.",
        )

    dataset.extracted_data = updated_data
    db.commit()

    return {"dataset_id": dataset_id, "status": "review", "message": "Data updated successfully."}


@router.post("/{dataset_id}/confirm")
async def confirm_and_process(dataset_id: str, db: Session = Depends(get_db)):
    """
    Confirm extracted data and trigger processing.

    This is a TRANSACTIONAL operation:
    - Creates building, floors, properties, ULPINs, RoR links
    - All commit together or all roll back
    - No partial buildings in the database
    """
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    if dataset.processing_status not in ("review", "uploaded"):
        raise HTTPException(
            status_code=400,
            detail=f"Dataset already in '{dataset.processing_status}' state.",
        )

    extracted = dataset.extracted_data
    if not extracted:
        raise HTTPException(status_code=400, detail="No extracted data to process.")

    # Create processing job
    job = ProcessingJob(
        dataset_uuid=dataset.id,
        status="processing",
        progress=10,
    )
    db.add(job)
    dataset.processing_status = "processing"
    db.commit()

    # Process building (this uses its own transaction)
    try:
        summary = process_building(
            db=db,
            building_data=extracted,
            data_source="uploaded_document",
        )

        # Update job and dataset status
        from app.models import Building as BuildingModel
        job.status = "complete"
        job.progress = 100
        job.result_summary = summary
        bld = db.query(BuildingModel).filter_by(building_id=summary["building_id"]).first()
        if bld:
            job.building_uuid = bld.id
            dataset.building_uuid = bld.id
        db.commit()

        return {
            "status": "complete",
            "dataset_id": dataset_id,
            "summary": summary,
            "message": "Building processed and saved successfully.",
        }

    except ProcessingError as e:
        job.status = "error"
        job.error = str(e)
        dataset.processing_status = "error"
        db.commit()

        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        job.status = "error"
        job.error = str(e)
        dataset.processing_status = "error"
        db.commit()

        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
