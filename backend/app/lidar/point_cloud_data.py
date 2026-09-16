"""
PointCloudData — Standardized Internal Point Cloud Representation

Normalized internal representation for LiDAR point clouds supporting:
- XYZ Cartesian coordinates (float64 meters)
- RGB colors (uint8 0-255)
- Intensity (float32)
- Classification labels (int32: 0=UNKNOWN, 1=GROUND, 2=VEGETATION, 3=BUILDING, 4=OUTLIER)
- Classification confidence scores (float32 0.0 to 1.0)
- Source scan IDs (int32)

Uses zero-copy slicing and vectorized NumPy arrays to optimize memory usage.
"""

import json
from typing import Dict, Any, Optional, List, Tuple
import numpy as np


CLASS_UNKNOWN = 0
CLASS_GROUND = 1
CLASS_VEGETATION = 2
CLASS_BUILDING = 3
CLASS_OUTLIER = 4

CLASS_NAMES = {
    CLASS_UNKNOWN: "UNKNOWN",
    CLASS_GROUND: "GROUND",
    CLASS_VEGETATION: "VEGETATION",
    CLASS_BUILDING: "BUILDING",
    CLASS_OUTLIER: "OUTLIER",
}


class PointCloudData:
    def __init__(self, count: int):
        self.count = count
        self.x = np.zeros(count, dtype=np.float64)
        self.y = np.zeros(count, dtype=np.float64)
        self.z = np.zeros(count, dtype=np.float64)

        self.r = np.zeros(count, dtype=np.uint8)
        self.g = np.zeros(count, dtype=np.uint8)
        self.b = np.zeros(count, dtype=np.uint8)

        self.intensity = np.zeros(count, dtype=np.float32)
        self.classification = np.zeros(count, dtype=np.int32)
        self.confidence = np.ones(count, dtype=np.float32)
        self.source_scan_id = np.zeros(count, dtype=np.int32)
        self.classification_reason: List[str] = [""] * count

    @classmethod
    def from_arrays(
        cls,
        pts: np.ndarray,
        colors: Optional[np.ndarray] = None,
        intensity: Optional[np.ndarray] = None,
        scans: Optional[np.ndarray] = None,
        classification: Optional[np.ndarray] = None,
        confidence: Optional[np.ndarray] = None,
    ) -> "PointCloudData":
        """Construct PointCloudData from NumPy array components."""
        count = len(pts)
        pcd = cls(count)
        pcd.x = np.asarray(pts[:, 0], dtype=np.float64)
        pcd.y = np.asarray(pts[:, 1], dtype=np.float64)
        pcd.z = np.asarray(pts[:, 2], dtype=np.float64)

        if colors is not None and len(colors) == count:
            pcd.r = np.asarray(colors[:, 0], dtype=np.uint8)
            pcd.g = np.asarray(colors[:, 1], dtype=np.uint8)
            pcd.b = np.asarray(colors[:, 2], dtype=np.uint8)

        if intensity is not None and len(intensity) == count:
            pcd.intensity = np.asarray(intensity, dtype=np.float32)

        if scans is not None and len(scans) == count:
            pcd.source_scan_id = np.asarray(scans, dtype=np.int32)

        if classification is not None and len(classification) == count:
            pcd.classification = np.asarray(classification, dtype=np.int32)

        if confidence is not None and len(confidence) == count:
            pcd.confidence = np.asarray(confidence, dtype=np.float32)

        return pcd

    def get_xyz(self) -> np.ndarray:
        """Return [N, 3] float64 Cartesian coordinates array."""
        return np.column_stack((self.x, self.y, self.z))

    def get_rgb(self) -> np.ndarray:
        """Return [N, 3] uint8 color array."""
        return np.column_stack((self.r, self.g, self.b))

    def get_bounds(self) -> Dict[str, float]:
        """Compute Cartesian bounding box statistics."""
        if self.count == 0:
            return {
                "x_min": 0.0, "x_max": 0.0, "x_range": 0.0,
                "y_min": 0.0, "y_max": 0.0, "y_range": 0.0,
                "z_min": 0.0, "z_max": 0.0, "z_range": 0.0,
            }
        x_min, x_max = float(np.min(self.x)), float(np.max(self.x))
        y_min, y_max = float(np.min(self.y)), float(np.max(self.y))
        z_min, z_max = float(np.min(self.z)), float(np.max(self.z))
        return {
            "x_min": round(x_min, 4), "x_max": round(x_max, 4), "x_range": round(x_max - x_min, 4),
            "y_min": round(y_min, 4), "y_max": round(y_max, 4), "y_range": round(y_max - y_min, 4),
            "z_min": round(z_min, 4), "z_max": round(z_max, 4), "z_range": round(z_max - z_min, 4),
        }

    def filter_by_class(self, class_id: int) -> "PointCloudData":
        """Return a new PointCloudData containing only points matching class_id."""
        mask = self.classification == class_id
        return self.select_by_mask(mask)

    def select_by_mask(self, mask: np.ndarray) -> "PointCloudData":
        """Return a new PointCloudData filtered by boolean mask."""
        indices = np.where(mask)[0]
        count = len(indices)
        filtered = PointCloudData(count)
        filtered.x = self.x[indices]
        filtered.y = self.y[indices]
        filtered.z = self.z[indices]
        filtered.r = self.r[indices]
        filtered.g = self.g[indices]
        filtered.b = self.b[indices]
        filtered.intensity = self.intensity[indices]
        filtered.classification = self.classification[indices]
        filtered.confidence = self.confidence[indices]
        filtered.source_scan_id = self.source_scan_id[indices]
        filtered.classification_reason = [self.classification_reason[i] for i in indices]
        return filtered

    def get_class_counts(self) -> Dict[str, int]:
        """Compute class distribution breakdown."""
        counts = {}
        for code, name in CLASS_NAMES.items():
            counts[name] = int(np.sum(self.classification == code))
        return counts

    def to_dict_flat(self) -> Dict[str, Any]:
        """Export as flattened array dict for web JSON responses."""
        flat_pts = []
        for i in range(self.count):
            flat_pts.extend([
                round(float(self.x[i]), 4),
                round(float(self.y[i]), 4),
                round(float(self.z[i]), 4),
                int(self.r[i]),
                int(self.g[i]),
                int(self.b[i]),
                int(self.classification[i]),
                round(float(self.confidence[i]), 3),
            ])
        return {
            "point_count": self.count,
            "format": "x_y_z_r_g_b_class_score",
            "points": flat_pts,
        }
