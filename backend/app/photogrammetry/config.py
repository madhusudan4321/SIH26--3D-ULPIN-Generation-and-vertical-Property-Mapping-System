"""
Photogrammetry Configuration Module

Manages:
- Dataset directory structure (raw/, workspace/, sparse/, dense/, derived/, reports/)
- COLMAP binary detection (PATH, COLMAP_PATH env, standard locations)
- COLMAP version extraction
- CUDA/GPU availability detection
- Configurable camera model, matcher type, and quality parameters
"""

import os
import shutil
import subprocess
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


# Supported image extensions for Phase 2
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# COLMAP camera models
CAMERA_MODELS = ["SIMPLE_RADIAL", "RADIAL", "PINHOLE", "OPENCV", "FULL_OPENCV"]

# Matcher types
MATCHER_TYPES = ["exhaustive", "sequential", "spatial"]


@dataclass
class PhotogrammetryConfig:
    """Configuration for a photogrammetry pipeline run."""

    # Dataset identification
    dataset_name: str = "unnamed_dataset"

    # Paths
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)
    base_data_dir: Optional[Path] = None
    images_dir: Optional[Path] = None  # Raw image source directory

    # COLMAP settings
    colmap_path: Optional[str] = None  # Explicit COLMAP binary path
    colmap_bin_path: Optional[Path] = None
    camera_model: str = "SIMPLE_RADIAL"
    single_camera: Optional[bool] = None  # None = auto-detect from EXIF
    matcher_type: str = "exhaustive"  # exhaustive | sequential | spatial
    matcher: Optional[str] = None

    # Quality settings
    feature_type: str = "SIFT"  # COLMAP default
    max_image_size: int = 3200  # Max dimension for feature extraction
    patch_match_max_image_size: int = 2000  # Max dimension for MVS

    # Pipeline control
    dry_run: bool = False

    def __post_init__(self):
        if self.matcher and not self.matcher_type:
            self.matcher_type = self.matcher
        elif self.matcher:
            self.matcher_type = self.matcher

        if self.colmap_bin_path and not self.colmap_path:
            self.colmap_path = str(self.colmap_bin_path)

        if self.camera_model not in CAMERA_MODELS:
            raise ValueError(f"Unsupported camera model: {self.camera_model}. Must be one of: {CAMERA_MODELS}")
        if self.matcher_type not in MATCHER_TYPES and self.matcher_type != "auto":
            raise ValueError(f"Unsupported matcher type: {self.matcher_type}. Must be one of: {MATCHER_TYPES}")

    # --- Directory Structure ---

    @property
    def dataset_dir(self) -> Path:
        if self.base_data_dir:
            return self.base_data_dir / "photogrammetry" / self.dataset_name
        return self.project_root / "data" / "photogrammetry" / self.dataset_name

    @property
    def raw_dir(self) -> Path:
        return self.dataset_dir / "raw"

    @property
    def workspace_dir(self) -> Path:
        return self.dataset_dir / "workspace"

    @property
    def sparse_dir(self) -> Path:
        return self.dataset_dir / "sparse"

    @property
    def dense_dir(self) -> Path:
        return self.dataset_dir / "dense"

    @property
    def derived_dir(self) -> Path:
        return self.dataset_dir / "derived"

    @property
    def reports_dir(self) -> Path:
        return self.dataset_dir / "reports"

    @property
    def database_path(self) -> Path:
        return self.workspace_dir / "database.db"

    def ensure_directories(self):
        """Create all dataset subdirectories (except raw, which must pre-exist or be symlinked)."""
        for d in [self.workspace_dir, self.sparse_dir, self.dense_dir, self.derived_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def get_effective_images_dir(self) -> Path:
        """Return the images directory: explicit --images path, or raw/ subdirectory."""
        if self.images_dir and self.images_dir.exists():
            return self.images_dir
        if self.raw_dir.exists():
            return self.raw_dir
        return self.raw_dir  # Will be checked for existence by caller

    # --- Hardware & Software Detection Helpers ---

    @property
    def colmap_info(self) -> dict:
        return detect_colmap(self.colmap_path)

    @property
    def colmap_installed(self) -> bool:
        return self.colmap_info["installed"]

    @property
    def colmap_bin(self) -> Optional[str]:
        return self.colmap_info["path"]

    @property
    def colmap_version(self) -> Optional[str]:
        return self.colmap_info["version"]

    @property
    def cuda_available(self) -> bool:
        return detect_cuda()["available"]


def detect_colmap(explicit_path: Optional[str] = None) -> dict:
    """
    Detect COLMAP binary and version.

    Search order:
    1. Explicit path parameter
    2. COLMAP_PATH environment variable
    3. Installed D:\\colmap-x64-windows-cuda\\bin\\colmap.exe
    4. System PATH (shutil.which)
    5. Standard installation directories (Windows/Linux)

    Returns dict with: installed, path, version
    """
    result = {"installed": False, "path": None, "version": None}

    candidates = []
    if explicit_path:
        candidates.append(explicit_path)

    env_path = os.environ.get("COLMAP_PATH")
    if env_path:
        candidates.append(env_path)

    # Standard Windows CUDA build path
    if platform.system() == "Windows":
        candidates.extend([
            r"D:\colmap-x64-windows-cuda\bin\colmap.exe",
            r"C:\colmap-x64-windows-cuda\bin\colmap.exe",
        ])

    which_result = shutil.which("colmap.exe") or shutil.which("colmap")
    if which_result:
        candidates.append(which_result)

    if platform.system() == "Windows":
        candidates.extend([
            r"C:\Program Files\COLMAP\bin\colmap.exe",
            r"C:\COLMAP\colmap.exe",
            r"D:\COLMAP\colmap.exe",
        ])
    else:
        candidates.extend([
            "/usr/local/bin/colmap",
            "/usr/bin/colmap",
            "/opt/colmap/bin/colmap",
        ])

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            result["installed"] = True
            result["path"] = str(candidate)
            # Try to get version using -v first
            try:
                proc = subprocess.run(
                    [str(candidate), "-v"],
                    capture_output=True, text=True, timeout=10
                )
                output = (proc.stdout + proc.stderr).strip()
                if output and "COLMAP" in output:
                    result["version"] = output.splitlines()[0]
                else:
                    proc_help = subprocess.run(
                        [str(candidate), "--help"],
                        capture_output=True, text=True, timeout=10
                    )
                    out_help = proc_help.stdout + proc_help.stderr
                    for line in out_help.splitlines():
                        line_lower = line.lower().strip()
                        if "colmap" in line_lower and any(c.isdigit() for c in line_lower):
                            result["version"] = line.strip()
                            break
                if not result["version"]:
                    result["version"] = "detected (version unknown)"
            except Exception:
                result["version"] = "detected (version query failed)"
            break

    return result


def detect_cuda() -> dict:
    """
    Detect CUDA/GPU availability for COLMAP patch_match_stereo.

    Checks:
    1. nvidia-smi command availability
    2. CUDA_HOME / CUDA_PATH environment variables
    """
    result = {"available": False, "method": None, "detail": None}

    # Check nvidia-smi
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0 and proc.stdout.strip():
            result["available"] = True
            result["method"] = "nvidia-smi"
            result["detail"] = proc.stdout.strip().splitlines()[0]
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check CUDA environment variables
    cuda_home = os.environ.get("CUDA_HOME") or os.environ.get("CUDA_PATH")
    if cuda_home and Path(cuda_home).exists():
        result["available"] = True
        result["method"] = "CUDA_HOME"
        result["detail"] = cuda_home
        return result

    result["method"] = "not_detected"
    result["detail"] = "No NVIDIA GPU or CUDA toolkit detected. MVS (patch_match_stereo) requires CUDA."
    return result
