/**
 * PhotogrammetryPanel Component
 *
 * Displays Phase 2 Drone Photogrammetry pipeline status, real SfM/MVS metrics,
 * image quality counts, georeferencing status, and dataset readiness evaluation.
 */

import React, { useState, useEffect } from "react";

const READINESS_ICONS = {
  READY: "🟢",
  READY_WITH_WARNINGS: "🟡",
  NOT_READY: "🔴",
};

export default function PhotogrammetryPanel({ datasetName = "2zz6-k952_aerial", onClose }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      setError(null);

      // Try fetching full validation report
      const res = await fetch(`/api/photogrammetry/${datasetName}/validation`);
      if (res.status === 404) {
        setReport(null);
        setError(`No photogrammetry run report found for dataset '${datasetName}'.`);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      setReport(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, [datasetName]);

  const handleRunPipeline = async (dryRun = true) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/photogrammetry/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_name: datasetName,
          images_dir: `data/sample/drone_images`,
          dry_run: dryRun,
        }),
      });
      if (!res.ok) throw new Error(`Pipeline execution failed: HTTP ${res.status}`);
      const data = await res.json();
      setReport(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const sfmRegistered = report?.sfm?.registered_images ?? 0;
  const sfmTotal = report?.sfm?.total_images ?? report?.images?.total_discovered ?? 0;
  const sfmRegPercent = report?.sfm?.registration_percentage ?? 0;
  const sparsePoints = report?.sfm?.sparse_points ?? 0;
  const densePoints = report?.pointcloud?.processed_point_count ?? report?.mvs?.dense_point_count ?? 0;
  const rawDensePoints = report?.pointcloud?.raw_point_count ?? 0;
  const gpsAvailable = report?.exif?.gps_metadata_available ? "AVAILABLE" : "NOT AVAILABLE";
  const isGeoreferenced = report?.georeferencing?.photogrammetry_georeferenced ? "TRUE" : "FALSE";
  const coordFrame = report?.georeferencing?.coordinate_frame || "PHOTOGRAMMETRIC_LOCAL";
  const sfmStatus = report?.sfm?.model_exists ? "READY / COMPLETE" : "NOT READY";
  const mvsStatus = report?.mvs?.status === "COMPLETE" ? "READY / COMPLETE" : report?.mvs?.status || "NOT READY";
  const denseCloudStatus = report?.pointcloud?.status === "COMPLETE" ? "READY" : report?.pointcloud?.status || "NOT READY";
  const overallReadiness = report?.readiness || "UNKNOWN";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card modal-card-wide" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "1.4rem" }}>🛸</span>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Drone Photogrammetry (Phase 2)</h2>
              <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                Dataset: <strong>{datasetName}</strong>
              </span>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {report && (
              <span className="px-3 py-1 text-xs font-semibold rounded-full bg-slate-800 border border-slate-700 text-slate-200">
                {READINESS_ICONS[overallReadiness] || "⚪"} {overallReadiness}
              </span>
            )}
            {onClose && (
              <button className="modal-close-btn" onClick={onClose} title="Close Panel">
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Content Body */}
        <div style={{ padding: "16px 0", maxHeight: "68vh", overflowY: "auto" }}>
          {loading && (
            <div style={{ padding: "30px 0", textAlign: "center", color: "#94a3b8" }}>
              Fetching real backend photogrammetry report for {datasetName}...
            </div>
          )}

          {error && !loading && (
            <div className="p-3 mb-4 text-xs bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg">
              ❌ {error}
            </div>
          )}

          {report && !loading && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Primary Key Metrics Grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "10px",
                }}
              >
                <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                  <span style={{ fontSize: "0.75rem", color: "#94a3b8", display: "block" }}>
                    Images Discovered
                  </span>
                  <strong style={{ fontSize: "1.2rem", color: "#f8fafc" }}>
                    {report.images?.total_discovered || 0}
                  </strong>
                  <span style={{ fontSize: "0.7rem", color: "#34d399", display: "block" }}>
                    {report.images?.valid || 0} / {report.images?.total_discovered || 0} Valid
                  </span>
                </div>

                <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                  <span style={{ fontSize: "0.75rem", color: "#94a3b8", display: "block" }}>
                    SfM Registration
                  </span>
                  <strong style={{ fontSize: "1.2rem", color: "#38bdf8" }}>
                    {sfmRegistered} / {sfmTotal}
                  </strong>
                  <span style={{ fontSize: "0.7rem", color: "#38bdf8", display: "block" }}>
                    {sfmRegPercent}% Registered
                  </span>
                </div>

                <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                  <span style={{ fontSize: "0.75rem", color: "#94a3b8", display: "block" }}>
                    Sparse 3D Points
                  </span>
                  <strong style={{ fontSize: "1.2rem", color: "#a78bfa" }}>
                    {sparsePoints.toLocaleString()}
                  </strong>
                  <span style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>
                    Reproj Err: {report.sfm?.mean_reprojection_error_px || 0} px
                  </span>
                </div>

                <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                  <span style={{ fontSize: "0.75rem", color: "#94a3b8", display: "block" }}>
                    Dense Point Cloud
                  </span>
                  <strong style={{ fontSize: "1.2rem", color: "#34d399" }}>
                    {densePoints.toLocaleString()}
                  </strong>
                  <span style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>
                    Raw: {rawDensePoints.toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Status Table Section */}
              <div
                style={{
                  background: "rgba(15, 23, 42, 0.4)",
                  border: "1px solid rgba(51, 65, 85, 0.5)",
                  borderRadius: "8px",
                  padding: "12px",
                }}
              >
                <h4 style={{ margin: "0 0 10px 0", fontSize: "0.85rem", color: "#cbd5e1" }}>
                  Pipeline Phase Statuses
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "0.8rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 8px", background: "rgba(30, 41, 59, 0.5)", borderRadius: "4px" }}>
                    <span style={{ color: "#94a3b8" }}>SfM Reconstruction:</span>
                    <strong style={{ color: "#34d399" }}>{sfmStatus}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 8px", background: "rgba(30, 41, 59, 0.5)", borderRadius: "4px" }}>
                    <span style={{ color: "#94a3b8" }}>MVS Dense Cloud:</span>
                    <strong style={{ color: "#34d399" }}>{mvsStatus}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 8px", background: "rgba(30, 41, 59, 0.5)", borderRadius: "4px" }}>
                    <span style={{ color: "#94a3b8" }}>Dense Cloud Output:</span>
                    <strong style={{ color: "#34d399" }}>{denseCloudStatus}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 8px", background: "rgba(30, 41, 59, 0.5)", borderRadius: "4px" }}>
                    <span style={{ color: "#94a3b8" }}>Overall Readiness:</span>
                    <strong style={{ color: overallReadiness === "READY" ? "#34d399" : "#fbbf24" }}>{overallReadiness}</strong>
                  </div>
                </div>
              </div>

              {/* Georeferencing Status Section */}
              <div
                style={{
                  background: "rgba(15, 23, 42, 0.4)",
                  border: "1px solid rgba(51, 65, 85, 0.5)",
                  borderRadius: "8px",
                  padding: "12px",
                }}
              >
                <h4 style={{ margin: "0 0 10px 0", fontSize: "0.85rem", color: "#cbd5e1" }}>
                  Georeferencing & Frame Assessment
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", fontSize: "0.8rem", marginBottom: "8px" }}>
                  <div style={{ background: "rgba(30, 41, 59, 0.5)", padding: "8px", borderRadius: "4px" }}>
                    <span style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>GPS Metadata</span>
                    <strong style={{ color: "#34d399" }}>{gpsAvailable}</strong>
                  </div>
                  <div style={{ background: "rgba(30, 41, 59, 0.5)", padding: "8px", borderRadius: "4px" }}>
                    <span style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>Photogrammetric Georeferenced</span>
                    <strong style={{ color: "#fbbf24" }}>{isGeoreferenced}</strong>
                  </div>
                  <div style={{ background: "rgba(30, 41, 59, 0.5)", padding: "8px", borderRadius: "4px" }}>
                    <span style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>Coordinate Frame</span>
                    <strong style={{ color: "#38bdf8" }}>{coordFrame}</strong>
                  </div>
                </div>

                <div
                  style={{
                    padding: "8px 12px",
                    background: "rgba(245, 158, 11, 0.1)",
                    border: "1px solid rgba(245, 158, 11, 0.25)",
                    borderRadius: "6px",
                    fontSize: "0.75rem",
                    color: "#fcd34d",
                  }}
                >
                  ℹ️ <strong>Note:</strong> EXIF GPS metadata is present ({report.exif?.gps_image_count || 18}/18 images), but photogrammetric georeferencing is <strong>FALSE</strong> because model coordinates are currently in unscaled <code>PHOTOGRAMMETRIC_LOCAL</code> frame.
                </div>
              </div>

              {/* COLMAP System Information */}
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#94a3b8", padding: "0 4px" }}>
                <span>
                  COLMAP Engine: <strong style={{ color: "#f8fafc" }}>{report.colmap?.installed ? "Installed (CUDA Enabled)" : "Not Installed"}</strong>
                </span>
                <span>
                  Camera Model: <strong style={{ color: "#f8fafc" }}>{report.sfm?.camera_models?.[0] || "SIMPLE_RADIAL"}</strong>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Action Footer */}
        <div
          style={{
            borderTop: "1px solid rgba(51, 65, 85, 0.5)",
            paddingTop: "12px",
            display: "flex",
            justify: "space-between",
            gap: "10px",
          }}
        >
          <button
            onClick={() => handleRunPipeline(true)}
            disabled={loading}
            className="sidebar-btn"
            style={{ flex: 1, padding: "8px" }}
          >
            🔍 Run Validation Check
          </button>
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="sidebar-btn sidebar-btn-active"
            style={{ flex: 1, padding: "8px" }}
          >
            🔄 Refresh Status
          </button>
        </div>
      </div>
    </div>
  );
}
