"""
COLMAP CLI Execution Wrapper Module

Executes COLMAP SfM and MVS pipeline stages:
1. feature_extractor (configurable camera_model & single_camera)
2. matcher (exhaustive / sequential / spatial)
3. mapper (SfM sparse reconstruction)
4. image_undistorter (pre-MVS dense workspace setup)
5. patch_match_stereo (MVS depth estimation — CUDA required)
6. stereo_fusion (dense PLY point cloud generation)

Handles hardware checks (CUDA detection), dry-run mode, and missing COLMAP binary cleanly.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from .config import PhotogrammetryConfig

logger = logging.getLogger(__name__)


def run_command(cmd: List[str], cwd: Optional[Path] = None, log_file: Optional[Path] = None) -> Tuple[int, str, str]:
    """Execute a CLI command and capture output."""
    logger.info(f"Running command: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        stdout, stderr = proc.communicate()

        if log_file:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"=== Command: {' '.join(cmd)} ===\n")
                f.write(f"Return code: {proc.returncode}\n")
                f.write("--- STDOUT ---\n" + stdout + "\n")
                f.write("--- STDERR ---\n" + stderr + "\n\n")

        return proc.returncode, stdout, stderr
    except Exception as e:
        logger.error(f"Failed to execute command {' '.join(cmd)}: {e}")
        return -1, "", str(e)


def run_colmap_pipeline(
    config: PhotogrammetryConfig,
    images_dir: Path,
    image_list_path: Optional[Path] = None,
    single_camera: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Run full COLMAP SfM + MVS pipeline.

    Returns:
        dict: Detailed log of execution status per stage.
    """
    results: Dict[str, Any] = {
        "colmap_installed": config.colmap_installed,
        "colmap_version": config.colmap_version,
        "cuda_available": config.cuda_available,
        "dry_run": config.dry_run,
        "stages": {},
        "status": "NOT_RUN",
    }

    if config.dry_run:
        logger.info("Dry-run mode enabled: skipping COLMAP execution.")
        results["status"] = "DRY_RUN"
        return results

    if not config.colmap_installed or not config.colmap_bin:
        logger.warning("COLMAP binary not found on system PATH or configured location.")
        results["status"] = "COLMAP_NOT_INSTALLED"
        return results

    # Ensure directories exist
    config.workspace_dir.mkdir(parents=True, exist_ok=True)
    config.sparse_dir.mkdir(parents=True, exist_ok=True)
    config.dense_dir.mkdir(parents=True, exist_ok=True)
    config.reports_dir.mkdir(parents=True, exist_ok=True)

    log_file = config.reports_dir / "colmap_execution.log"
    database_path = config.workspace_dir / "database.db"

    # Single camera logic
    is_single = single_camera if single_camera is not None else config.single_camera

    # -------------------------------------------------------------------------
    # Stage 1: Feature Extractor
    # -------------------------------------------------------------------------
    feat_cmd = [
        config.colmap_bin,
        "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(images_dir),
        "--ImageReader.camera_model", config.camera_model,
        "--ImageReader.single_camera", "1" if is_single else "0",
        "--FeatureExtraction.max_image_size", str(config.max_image_size),
    ]
    if image_list_path and image_list_path.exists():
        feat_cmd.extend(["--image_list_path", str(image_list_path)])

    code, out, err = run_command(feat_cmd, log_file=log_file)
    results["stages"]["feature_extractor"] = {
        "return_code": code,
        "success": code == 0,
    }
    if code != 0:
        results["status"] = "FAILED_FEATURE_EXTRACTION"
        return results

    # -------------------------------------------------------------------------
    # Stage 2: Matcher
    # -------------------------------------------------------------------------
    matcher_type = config.matcher.lower()
    if matcher_type == "auto":
        matcher_cmd_name = "exhaustive_matcher"
    elif matcher_type == "sequential":
        matcher_cmd_name = "sequential_matcher"
    elif matcher_type == "spatial":
        matcher_cmd_name = "spatial_matcher"
    else:
        matcher_cmd_name = "exhaustive_matcher"

    match_cmd = [
        config.colmap_bin,
        matcher_cmd_name,
        "--database_path", str(database_path),
    ]

    code, out, err = run_command(match_cmd, log_file=log_file)
    results["stages"]["matcher"] = {
        "type": matcher_cmd_name,
        "return_code": code,
        "success": code == 0,
    }
    if code != 0:
        results["status"] = "FAILED_MATCHING"
        return results

    # -------------------------------------------------------------------------
    # Stage 3: Mapper (SfM Sparse Reconstruction)
    # -------------------------------------------------------------------------
    map_cmd = [
        config.colmap_bin,
        "mapper",
        "--database_path", str(database_path),
        "--image_path", str(images_dir),
        "--output_path", str(config.sparse_dir),
    ]

    code, out, err = run_command(map_cmd, log_file=log_file)
    results["stages"]["mapper"] = {
        "return_code": code,
        "success": code == 0,
    }
    if code != 0:
        results["status"] = "FAILED_MAPPING"
        return results

    # Check if sparse model 0 was produced
    sparse_model_dir = config.sparse_dir / "0"
    if not sparse_model_dir.exists():
        results["status"] = "SPARSE_MODEL_EMPTY"
        logger.warning("COLMAP mapper did not produce a valid sparse model in sparse/0.")
        return results

    # Convert model to TXT format for cross-version COLMAP parsing compatibility
    conv_cmd = [
        config.colmap_bin,
        "model_converter",
        "--input_path", str(sparse_model_dir),
        "--output_path", str(sparse_model_dir),
        "--output_type", "TXT",
    ]
    run_command(conv_cmd, log_file=log_file)

    results["status"] = "SFM_COMPLETE"

    # -------------------------------------------------------------------------
    # Stage 4: Image Undistorter (Pre-MVS setup)
    # -------------------------------------------------------------------------
    undistort_cmd = [
        config.colmap_bin,
        "image_undistorter",
        "--image_path", str(images_dir),
        "--input_path", str(sparse_model_dir),
        "--output_path", str(config.dense_dir),
        "--output_type", "COLMAP",
        "--max_image_size", "2000",
    ]

    code, out, err = run_command(undistort_cmd, log_file=log_file)
    results["stages"]["image_undistorter"] = {
        "return_code": code,
        "success": code == 0,
    }
    if code != 0:
        logger.warning("Image undistortion failed; skipping MVS stage.")
        results["mvs_status"] = "FAILED_UNDISTORT"
        return results

    # -------------------------------------------------------------------------
    # Stage 5 & 6: Patch Match Stereo & Stereo Fusion (CUDA Required)
    # -------------------------------------------------------------------------
    if not config.cuda_available:
        logger.info("CUDA not available; skipping patch_match_stereo & stereo_fusion (Sparse-only mode).")
        results["mvs_status"] = "SKIPPED_NO_CUDA"
        return results

    # Stage 5: Patch Match Stereo
    pms_cmd = [
        config.colmap_bin,
        "patch_match_stereo",
        "--workspace_path", str(config.dense_dir),
        "--workspace_format", "COLMAP",
        "--PatchMatchStereo.geom_consistency", "true",
    ]

    code, out, err = run_command(pms_cmd, log_file=log_file)
    results["stages"]["patch_match_stereo"] = {
        "return_code": code,
        "success": code == 0,
    }
    if code != 0:
        logger.warning("Patch match stereo failed; skipping stereo fusion.")
        results["mvs_status"] = "FAILED_PATCH_MATCH"
        return results

    # Stage 6: Stereo Fusion
    fused_ply_path = config.dense_dir / "fused.ply"
    fusion_cmd = [
        config.colmap_bin,
        "stereo_fusion",
        "--workspace_path", str(config.dense_dir),
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--output_path", str(fused_ply_path),
    ]

    code, out, err = run_command(fusion_cmd, log_file=log_file)
    results["stages"]["stereo_fusion"] = {
        "return_code": code,
        "success": code == 0 and fused_ply_path.exists(),
        "fused_ply_path": str(fused_ply_path) if fused_ply_path.exists() else None,
    }

    if code == 0 and fused_ply_path.exists():
        results["mvs_status"] = "COMPLETE"
        results["status"] = "COMPLETE"
    else:
        results["mvs_status"] = "FAILED_FUSION"

    return results
