"""
Photogrammetry Module Unit Tests (unittest format)

Tests:
1. Image discovery & manifest generation
2. Image quality validation (sharpness, exposure, duplicate detection)
3. EXIF metadata extraction & coordinate frame separation
4. Dry-run pipeline execution (verifies zero fake reconstruction files created)
5. Router handler execution
"""

import asyncio
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

# Ensure backend directory is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.photogrammetry.image_ingestion import discover_images
from app.photogrammetry.image_validation import validate_images
from app.photogrammetry.exif import process_dataset_exif
from app.photogrammetry.pipeline import run_photogrammetry_pipeline
from app.routers.photogrammetry import trigger_photogrammetry_run, PhotogrammetryRunRequest, get_validation_report


class TestPhotogrammetryPipeline(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.mock_images_dir = self.tmp_dir / "drone_images"
        self.mock_images_dir.mkdir()

        # Valid image 1
        im1 = Image.new("RGB", (800, 600), color=(100, 150, 200))
        im1.save(self.mock_images_dir / "drone_001.jpg")

        # Valid image 2
        im2 = Image.new("RGB", (800, 600), color=(120, 140, 180))
        im2.save(self.mock_images_dir / "drone_002.jpg")

        # Corrupted / invalid image 3
        corrupt_file = self.mock_images_dir / "drone_corrupt.jpg"
        with open(corrupt_file, "wb") as f:
            f.write(b"not an image file data")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_image_discovery(self):
        reports_dir = self.tmp_dir / "reports"
        manifest = discover_images(self.mock_images_dir, "test_dataset", reports_dir)

        self.assertEqual(manifest["total_discovered"], 3)
        self.assertTrue((reports_dir / "photogrammetry_image_manifest.json").exists())

    def test_image_validation(self):
        reports_dir = self.tmp_dir / "reports"
        workspace_dir = self.tmp_dir / "workspace"

        manifest = discover_images(self.mock_images_dir, "test_dataset", reports_dir)
        report = validate_images(manifest, reports_dir, workspace_dir)

        self.assertEqual(report["total_discovered"], 3)
        self.assertEqual(report["invalid"], 1)  # drone_corrupt.jpg
        self.assertTrue((workspace_dir / "image_list.txt").exists())

    def test_exif_extraction(self):
        reports_dir = self.tmp_dir / "reports"
        manifest = discover_images(self.mock_images_dir, "test_dataset", reports_dir)
        exif_summary = process_dataset_exif(manifest, reports_dir)

        self.assertEqual(exif_summary["total_images"], 3)
        self.assertEqual(exif_summary["georeferencing"]["coordinate_frame"], "PHOTOGRAMMETRIC_LOCAL")
        self.assertFalse(exif_summary["georeferencing"]["photogrammetry_georeferenced"])

    def test_dry_run_pipeline(self):
        base_data = self.tmp_dir / "data"
        report = run_photogrammetry_pipeline(
            dataset_name="test_dry_run",
            images_dir=self.mock_images_dir,
            base_data_dir=base_data,
            dry_run=True,
        )

        self.assertEqual(report["dataset"]["pipeline_status"], "DRY_RUN")
        self.assertEqual(report["readiness"], "NOT_READY")
        self.assertTrue(any("Pipeline executed in dry-run mode" in w for w in report["warnings"]))

        # Verify ZERO reconstruction artifacts created
        dense_ply = base_data / "photogrammetry" / "test_dry_run" / "derived" / "photogrammetry_dense_processed.ply"
        self.assertFalse(dense_ply.exists())

    def test_router_handler(self):
        req = PhotogrammetryRunRequest(
            dataset_name="router_test",
            images_dir=str(self.mock_images_dir),
            dry_run=True,
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(trigger_photogrammetry_run(req))

        self.assertEqual(res["dataset"]["pipeline_status"], "DRY_RUN")
    def test_colmap_command_construction(self):
        from unittest.mock import patch
        from app.photogrammetry.config import PhotogrammetryConfig
        from app.photogrammetry.colmap_runner import run_colmap_pipeline

        config = PhotogrammetryConfig(
            dataset_name="test_cmd",
            base_data_dir=self.tmp_dir / "data",
            camera_model="SIMPLE_RADIAL",
            single_camera=True,
            matcher="exhaustive",
            dry_run=False,
        )

        image_list = self.tmp_dir / "image_list.txt"
        image_list.write_text("drone_001.jpg\ndrone_002.jpg\n", encoding="utf-8")

        executed_cmds = []

        def mock_run_command(cmd, cwd=None, log_file=None):
            executed_cmds.append(cmd)
            return (0, "", "") if "feature_extractor" in cmd else (1, "", "")

        with patch("app.photogrammetry.colmap_runner.run_command", side_effect=mock_run_command), \
             patch.object(PhotogrammetryConfig, "colmap_installed", True), \
             patch.object(PhotogrammetryConfig, "colmap_bin", r"D:\colmap-x64-windows-cuda\bin\colmap.exe"):

            run_colmap_pipeline(
                config=config,
                images_dir=self.mock_images_dir,
                image_list_path=image_list,
                single_camera=True,
            )

        self.assertGreater(len(executed_cmds), 0)
        feat_cmd = executed_cmds[0]

        # Verify command arguments
        self.assertEqual(feat_cmd[0], r"D:\colmap-x64-windows-cuda\bin\colmap.exe")
        self.assertEqual(feat_cmd[1], "feature_extractor")
        self.assertIn("--database_path", feat_cmd)
        self.assertIn("--image_path", feat_cmd)
        self.assertIn("--ImageReader.camera_model", feat_cmd)
        self.assertIn("--ImageReader.single_camera", feat_cmd)
        self.assertIn("--FeatureExtraction.max_image_size", feat_cmd)

        # Verify correct top-level flag for COLMAP 4.2.0
        self.assertIn("--image_list_path", feat_cmd)
        self.assertNotIn("--ImageReader.image_list_path", feat_cmd)


if __name__ == "__main__":
    unittest.main()
