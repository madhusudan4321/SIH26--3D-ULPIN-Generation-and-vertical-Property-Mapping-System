/**
 * AlignmentOverlay Component — Geographic Footprint & Elevation Alignment Diagnostics
 *
 * Displays data-driven geographic alignment diagnostics for the selected building.
 * Auditable visual evidence:
 * - Alignment Status (PASS / APPROXIMATE / UNVERIFIED / WARN / FAIL)
 * - IoU (Intersection over Union), Containment Ratio, Horizontal Displacement
 * - Base & Reference Elevation, Elevation Diff
 * - Local ENU Footprint Centroid Anchor
 * - Data & Elevation Provenance Source
 */

import { useState, useEffect } from "react";
import { useSelection } from "../hooks/useSelection";
import { getBuildingAlignment } from "../services/api";

export default function AlignmentOverlay() {
  const { selectedBuildingId, selectedPropertyId } = useSelection();
  const [alignmentData, setAlignmentData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [minimized, setMinimized] = useState(false);

  const activeBuildingId = selectedBuildingId || (selectedPropertyId ? selectedPropertyId.split("-F")[0] : null);

  useEffect(() => {
    if (!activeBuildingId) {
      setAlignmentData(null);
      return;
    }

    let isMounted = true;
    setLoading(true);

    getBuildingAlignment(activeBuildingId)
      .then((data) => {
        if (isMounted) {
          setAlignmentData(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setAlignmentData(null);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [activeBuildingId]);

  if (!activeBuildingId || (!alignmentData && !loading)) {
    return null;
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case "PASS":
        return { text: "PASS", color: "#22c55e", bg: "rgba(34, 197, 94, 0.15)", border: "#22c55e" };
      case "APPROXIMATE":
        return { text: "APPROXIMATE", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.15)", border: "#f59e0b" };
      case "UNVERIFIED":
        return { text: "UNVERIFIED", color: "#38bdf8", bg: "rgba(56, 189, 248, 0.15)", border: "#38bdf8" };
      case "WARN":
        return { text: "WARN", color: "#f97316", bg: "rgba(249, 115, 22, 0.15)", border: "#f97316" };
      case "FAIL":
        return { text: "FAIL", color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)", border: "#ef4444" };
      default:
        return { text: status || "UNKNOWN", color: "#9ca3af", bg: "rgba(156, 163, 175, 0.15)", border: "#9ca3af" };
    }
  };

  const badge = getStatusBadge(alignmentData?.alignment_status);

  return (
    <div className="alignment-overlay-card">
      <div className="alignment-header" onClick={() => setMinimized(!minimized)}>
        <div className="alignment-title-group">
          <span className="alignment-icon">🎯</span>
          <span className="alignment-title">Geographic Alignment</span>
        </div>
        {alignmentData && (
          <span
            className="alignment-badge"
            style={{
              color: badge.color,
              backgroundColor: badge.bg,
              borderColor: badge.border,
            }}
          >
            {badge.text}
          </span>
        )}
        <button className="alignment-toggle-btn">
          {minimized ? "▲" : "▼"}
        </button>
      </div>

      {!minimized && alignmentData && (
        <div className="alignment-body">
          <div className="alignment-message">
            {alignmentData.diagnostic_message}
          </div>

          <div className="alignment-grid">
            <div className="alignment-metric">
              <span className="metric-label">Horizontal Offset</span>
              <span className="metric-value">{alignmentData.horizontal_offset_m} m</span>
            </div>

            <div className="alignment-metric">
              <span className="metric-label">IoU (Overlap)</span>
              <span className="metric-value">
                {alignmentData.iou != null ? `${(alignmentData.iou * 100).toFixed(1)}%` : "N/A"}
              </span>
            </div>

            <div className="alignment-metric">
              <span className="metric-label">Containment</span>
              <span className="metric-value">{alignmentData.containment_ratio_percent}%</span>
            </div>

            <div className="alignment-metric">
              <span className="metric-label">Base Elevation</span>
              <span className="metric-value">{alignmentData.base_elevation_m} m</span>
            </div>

            <div className="alignment-metric">
              <span className="metric-label">Ref Elevation</span>
              <span className="metric-value">{alignmentData.reference_elevation_m} m</span>
            </div>

            <div className="alignment-metric">
              <span className="metric-label">Elev Difference</span>
              <span className="metric-value">{alignmentData.elevation_difference_m} m</span>
            </div>
          </div>

          <div className="alignment-meta">
            <div>
              <strong>Centroid Anchor:</strong> {alignmentData.model_anchor_lat}°, {alignmentData.model_anchor_lon}°
            </div>
            <div>
              <strong>Geometry Source:</strong> <span className="source-tag">{alignmentData.geometry_source}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
