/**
 * LocalLidarViewer — Full 3D Point Cloud, Building Extraction & Mesh Reconstruction Modal
 *
 * Displays the Aam Khas Bagh LiDAR point cloud, extracted building footprint,
 * and LiDAR-derived reconstructed 3D mesh in LOCAL CARTESIAN METERS coordinates.
 *
 * Features:
 *  - Real 3D Three.js WebGL rendering with actual E57 RGB colors
 *  - Visual Debugger Toggles for all layers
 *  - Reconstructed 3D Mesh with wireframe/solid/opacity controls
 *  - Mesh Statistics & Point-to-Mesh Distance Diagnostics
 *  - Connected Component reporting
 *  - Point Coverage & Mesh Support metrics
 *  - Export Local GeoJSON Action
 *  - Per-scan visibility toggling (21 scans)
 *  - Camera presets (Fit, Top, Front, Side)
 *
 * CRITICAL: LOCAL COORDINATE FRAME — NOT GEOREFERENCED
 */

import { useState, useEffect, useCallback } from "react";
import PointCloudCanvas from "./PointCloudCanvas";
import LidarErrorBoundary from "./LidarErrorBoundary";

export default function LocalLidarViewer({ onClose }) {
  const [sampleData, setSampleData] = useState(null);
  const [report, setReport] = useState(null);
  const [classifiedData, setClassifiedData] = useState(null);
  const [extractedBuilding, setExtractedBuilding] = useState(null);
  const [meshMetadata, setMeshMetadata] = useState(null);
  const [meshUrl, setMeshUrl] = useState(null);

  const [loading, setLoading] = useState(true);
  const [loadingPoints, setLoadingPoints] = useState(true);
  const [error, setError] = useState(null);

  // Controls state
  const [showAxes, setShowAxes] = useState(true);
  const [showScanners, setShowScanners] = useState(true);
  const [pointSize, setPointSize] = useState(1.5);
  const [activeTab, setActiveTab] = useState("debugger");

  // Visual Debugger Layer Toggles
  const [showRawCloud, setShowRawCloud] = useState(true);
  const [showGroundPoints, setShowGroundPoints] = useState(false);
  const [showNonGroundPoints, setShowNonGroundPoints] = useState(false);
  const [showBuildingPoints, setShowBuildingPoints] = useState(true);
  const [showFootprint, setShowFootprint] = useState(true);

  // Mesh Layer Controls
  const [showMesh, setShowMesh] = useState(true);
  const [showMeshWireframe, setShowMeshWireframe] = useState(false);
  const [meshOpacity, setMeshOpacity] = useState(0.75);

  // Per-scan visibility
  const [scanVisibility, setScanVisibility] = useState({});

  // Camera debug state & active preset
  const [activePreset, setActivePreset] = useState("fit");
  const [cameraDebugInfo, setCameraDebugInfo] = useState(null);

  const handlePresetClick = (preset) => {
    setActivePreset(preset);
    if (window.__lidarCamPreset) {
      window.__lidarCamPreset(preset);
    }
  };

  // Fetch all data on mount
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    // 1. Metadata report
    fetch("/api/lidar/aam_khas_bagh/report")
      .then((r) => (r.ok ? r.json() : null))
      .then((rpt) => {
        if (!isMounted) return;
        setReport(rpt);
        setLoading(false);
        const vis = {};
        for (let i = 0; i < (rpt?.scan_count || 21); i++) vis[i] = true;
        setScanVisibility(vis);
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message);
          setLoading(false);
        }
      });

    // 2. Point cloud sample
    fetch("/api/lidar/aam_khas_bagh/sample")
      .then((r) => (r.ok ? r.json() : null))
      .then((sample) => {
        if (!isMounted) return;
        setSampleData(sample);
        setLoadingPoints(false);
      })
      .catch(() => {
        if (isMounted) setLoadingPoints(false);
      });

    // 3. Classified cloud & extracted building
    Promise.all([
      fetch("/api/lidar/aam_khas_bagh/classified_cloud").then((r) => (r.ok ? r.json() : null)),
      fetch("/api/lidar/aam_khas_bagh/extracted_building").then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([classified, bld]) => {
        if (!isMounted) return;
        if (classified) setClassifiedData(classified);
        if (bld) setExtractedBuilding(bld);
      })
      .catch((e) => console.warn("Extraction data load:", e));

    // 4. Mesh metadata & mesh URL
    fetch("/api/lidar/aam_khas_bagh/mesh_metadata")
      .then((r) => (r.ok ? r.json() : null))
      .then((meta) => {
        if (!isMounted) return;
        if (meta && meta.status === "SUCCESS") {
          setMeshMetadata(meta);
          setMeshUrl("/api/lidar/aam_khas_bagh/mesh");
        } else if (meta) {
          setMeshMetadata(meta);
        }
      })
      .catch((e) => console.warn("Mesh metadata load:", e));

    return () => {
      isMounted = false;
    };
  }, []);

  const toggleScan = useCallback((idx) => {
    setScanVisibility((prev) => ({ ...prev, [idx]: !prev[idx] }));
  }, []);

  const showAllScans = useCallback(() => {
    setScanVisibility((prev) => {
      const next = {};
      Object.keys(prev).forEach((k) => (next[k] = true));
      return next;
    });
  }, []);

  const hideAllScans = useCallback(() => {
    setScanVisibility((prev) => {
      const next = {};
      Object.keys(prev).forEach((k) => (next[k] = false));
      return next;
    });
  }, []);

  const handleExportGeoJSON = () => {
    fetch("/api/lidar/aam_khas_bagh/export_geojson")
      .then((r) => r.json())
      .then((data) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "aam_khas_bagh_building_footprint_local.geojson";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((err) => alert("Failed to export GeoJSON: " + err.message));
  };

  const currentBld = extractedBuilding || classifiedData?.extracted_building;
  const mm = meshMetadata;

  return (
    <div className="modal-overlay" style={{ zIndex: 9999 }}>
      <div className="lidar-viewer-fullscreen">
        {/* HEADER */}
        <div className="lcv-header">
          <div className="lcv-header-left">
            <span className="lcv-icon">🛰️</span>
            <div className="lcv-titles">
              <h2>Aam Khas Bagh — LiDAR 3D Mesh Reconstruction</h2>
              <span className="lcv-frame-badge">
                🔒 LOCAL COORDINATE FRAME — NOT GEOREFERENCED
              </span>
            </div>
          </div>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* BODY */}
        <div className="lcv-body">
          {loading && !report && (
            <div className="lcv-loading">
              <div className="spinner"></div>
              <p>Loading Aam Khas Bagh E57 Metadata...</p>
            </div>
          )}

          {error && (
            <div className="lcv-error">
              <p>⚠️ {error}</p>
            </div>
          )}

          {!loading && report && (
            <div className="lcv-layout">
              {/* LEFT: 3D Canvas */}
              <div className="lcv-canvas-area">
                {loadingPoints ? (
                  <div className="lcv-loading" style={{ position: "absolute", inset: 0, background: "#0f172a", zIndex: 20 }}>
                    <div className="spinner"></div>
                    <p style={{ color: "#38bdf8", fontWeight: 600 }}>Streaming Local Point Cloud...</p>
                  </div>
                ) : sampleData ? (
                  <LidarErrorBoundary>
                    <PointCloudCanvas
                      sampleData={sampleData}
                      classifiedData={classifiedData}
                      extractedBuilding={currentBld}
                      scanVisibility={scanVisibility}
                      showAxes={showAxes}
                      showScanners={showScanners}
                      pointSize={pointSize}
                      showRawCloud={showRawCloud}
                      showGroundPoints={showGroundPoints}
                      showNonGroundPoints={showNonGroundPoints}
                      showBuildingPoints={showBuildingPoints}
                      showFootprint={showFootprint}
                      meshUrl={meshUrl}
                      showMesh={showMesh}
                      showMeshWireframe={showMeshWireframe}
                      meshOpacity={meshOpacity}
                      activePreset={activePreset}
                      onCameraInfoChange={setCameraDebugInfo}
                    />
                  </LidarErrorBoundary>
                ) : (
                  <div className="lcv-loading" style={{ position: "absolute", inset: 0, background: "#0f172a", zIndex: 20 }}>
                    <p style={{ color: "#f59e0b" }}>⚠️ Point cloud sample unavailable.</p>
                  </div>
                )}

                {/* Overlay point counter & navigation guide */}
                <div className="lcv-canvas-overlay-top">
                  <div>
                    <span className="lcv-point-counter">
                      Displayed: {(sampleData?.sampled_points || 94130).toLocaleString()} pts
                      {mm && mm.status === "SUCCESS" && ` | Mesh: ${mm.vertex_count?.toLocaleString()} verts, ${mm.triangle_count?.toLocaleString()} tris`}
                    </span>
                  </div>
                  <div>
                    <span className="lcv-nav-guide">
                      🖱️ Left-Click + Drag: Rotate 3D View &bull; Right-Click: Pan &bull; Scroll: Zoom
                    </span>
                  </div>
                </div>

                {/* Camera presets */}
                <div className="lcv-camera-bar">
                  <button className={activePreset === "fit" ? "active" : ""} onClick={() => handlePresetClick("fit")}>🎯 Fit</button>
                  <button className={activePreset === "top" ? "active" : ""} onClick={() => handlePresetClick("top")}>⬆ Top</button>
                  <button className={activePreset === "front" ? "active" : ""} onClick={() => handlePresetClick("front")}>▶ Front</button>
                  <button className={activePreset === "side" ? "active" : ""} onClick={() => handlePresetClick("side")}>◀ Side</button>
                </div>
              </div>

              {/* RIGHT: Controls Panel */}
              <div className="lcv-controls-panel">
                <div className="lcv-tabs">
                  <button className={activeTab === "debugger" ? "active" : ""} onClick={() => setActiveTab("debugger")}>
                    Layers
                  </button>
                  <button className={activeTab === "mesh" ? "active" : ""} onClick={() => setActiveTab("mesh")}>
                    Mesh
                  </button>
                  <button className={activeTab === "scans" ? "active" : ""} onClick={() => setActiveTab("scans")}>
                    Scans ({sampleData?.scan_count || 21})
                  </button>
                  <button className={activeTab === "info" ? "active" : ""} onClick={() => setActiveTab("info")}>
                    Info
                  </button>
                </div>

                {/* TAB: Layers (Visual Debugger) */}
                {activeTab === "debugger" && (
                  <div className="lcv-tab-content">
                    <div className="lcv-control-section">
                      <h4>Visual Debugger Layers</h4>

                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showRawCloud} onChange={(e) => setShowRawCloud(e.target.checked)} />
                        <span>Raw Sampled Cloud</span>
                      </label>

                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showGroundPoints} onChange={(e) => setShowGroundPoints(e.target.checked)} />
                        <span style={{ color: "#86efac" }}>Ground Points</span>
                      </label>

                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showNonGroundPoints} onChange={(e) => setShowNonGroundPoints(e.target.checked)} />
                        <span style={{ color: "#38bdf8" }}>Non-Ground Objects</span>
                      </label>

                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showBuildingPoints} onChange={(e) => setShowBuildingPoints(e.target.checked)} />
                        <span style={{ color: "#ec4899", fontWeight: 600 }}>Input Building Points</span>
                      </label>

                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showFootprint} onChange={(e) => setShowFootprint(e.target.checked)} />
                        <span style={{ color: "#fbbf24" }}>Extracted 2D Footprint</span>
                      </label>

                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showMesh} onChange={(e) => setShowMesh(e.target.checked)} />
                        <span style={{ color: "#d4a574", fontWeight: 700 }}>Reconstructed 3D Mesh</span>
                      </label>

                      <label className="lcv-toggle-row" style={{ paddingLeft: 20 }}>
                        <input type="checkbox" checked={showMeshWireframe} onChange={(e) => setShowMeshWireframe(e.target.checked)} />
                        <span style={{ color: "#38bdf8", fontSize: 11 }}>Wireframe Overlay</span>
                      </label>
                    </div>

                    <div className="lcv-control-section">
                      <h4>Mesh Opacity</h4>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <input type="range" min="0" max="1" step="0.05" value={meshOpacity}
                          onChange={(e) => setMeshOpacity(parseFloat(e.target.value))}
                          style={{ flex: 1 }} />
                        <span className="lcv-range-label">{(meshOpacity * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    <div className="lcv-control-section">
                      <h4>Display Controls</h4>
                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showAxes} onChange={(e) => setShowAxes(e.target.checked)} />
                        <span>Local Axes (X/Y/Z)</span>
                      </label>
                      <label className="lcv-toggle-row">
                        <input type="checkbox" checked={showScanners} onChange={(e) => setShowScanners(e.target.checked)} />
                        <span>Scanner Positions</span>
                      </label>
                      <div style={{ marginTop: 6 }}>
                        <span style={{ fontSize: 11 }}>Point Size: </span>
                        <input type="range" min="0.5" max="5" step="0.25" value={pointSize}
                          onChange={(e) => setPointSize(parseFloat(e.target.value))} />
                        <span className="lcv-range-label">{pointSize.toFixed(1)} px</span>
                      </div>
                    </div>

                    <div className="lcv-control-section">
                      <h4>Export</h4>
                      <button className="lcv-export-btn" onClick={handleExportGeoJSON}>
                        📥 Export Local GeoJSON
                      </button>
                      <p className="lcv-hint" style={{ marginTop: 4 }}>
                        Exports in <code>AAM_KHAS_BAGH_LOCAL</code> coordinates.
                      </p>
                    </div>
                  </div>
                )}

                {/* TAB: Mesh Statistics & Diagnostics */}
                {activeTab === "mesh" && (
                  <div className="lcv-tab-content">
                    {!mm ? (
                      <div className="lcv-control-section">
                        <p style={{ color: "#94a3b8", fontSize: 12 }}>
                          Mesh not generated yet. Run <code>reconstruct_aam_khas_bagh_mesh.py</code>.
                        </p>
                      </div>
                    ) : mm.status === "FAILED" ? (
                      <div className="lcv-control-section">
                        <h4 style={{ color: "#ef4444" }}>Reconstruction Failed</h4>
                        <p style={{ color: "#fca5a5", fontSize: 11 }}>{mm.failure_reason}</p>
                        <p style={{ color: "#94a3b8", fontSize: 11, marginTop: 4 }}>
                          No synthetic fallback generated. Reporting failure honestly.
                        </p>
                      </div>
                    ) : (
                      <>
                        <div className="lcv-control-section">
                          <h4>Mesh Statistics</h4>
                          <div className="lcv-candidate-card">
                            <div className="lcv-candidate-row">
                              <span>Terminology:</span>
                              <strong style={{ color: "#d4a574", fontSize: 10 }}>LiDAR-derived reconstructed mesh</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Method:</span>
                              <strong>{mm.reconstruction_method}</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Vertices:</span>
                              <strong>{mm.vertex_count?.toLocaleString()}</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Triangles:</span>
                              <strong>{mm.triangle_count?.toLocaleString()}</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Surface Area:</span>
                              <strong>{mm.surface_area_m2} m²</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Dimensions:</span>
                              <strong>{mm.dimensions?.width_m}×{mm.dimensions?.length_m}×{mm.dimensions?.height_m} m</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Input Points:</span>
                              <strong>{mm.input_point_count?.toLocaleString()}</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Outliers Removed:</span>
                              <strong>{mm.outliers_removed?.toLocaleString()}</strong>
                            </div>
                            <div className="lcv-candidate-row">
                              <span>Components:</span>
                              <strong>{mm.component_count}</strong>
                            </div>
                          </div>
                        </div>

                        <div className="lcv-control-section">
                          <h4>Point Spacing (NN Distance)</h4>
                          <div className="lcv-candidate-card">
                            <div className="lcv-candidate-row"><span>Mean:</span><strong>{mm.point_spacing?.mean_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>Median:</span><strong>{mm.point_spacing?.median_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>P25:</span><strong>{mm.point_spacing?.p25_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>P75:</span><strong>{mm.point_spacing?.p75_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>P95:</span><strong>{mm.point_spacing?.p95_m} m</strong></div>
                          </div>
                        </div>

                        <div className="lcv-control-section">
                          <h4>Point-to-Mesh Distance</h4>
                          <div className="lcv-candidate-card">
                            <div className="lcv-candidate-row"><span>Mean:</span><strong>{mm.point_to_mesh_distance?.mean_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>Median:</span><strong>{mm.point_to_mesh_distance?.median_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>P95:</span><strong>{mm.point_to_mesh_distance?.p95_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>P99:</span><strong>{mm.point_to_mesh_distance?.p99_m} m</strong></div>
                            <div className="lcv-candidate-row"><span>Max:</span><strong>{mm.point_to_mesh_distance?.max_m} m</strong></div>
                          </div>
                        </div>

                        <div className="lcv-control-section">
                          <h4>Point Coverage</h4>
                          <div className="lcv-candidate-card">
                            <div className="lcv-candidate-row"><span>Within 0.05m:</span><strong>{mm.point_coverage?.pct_within_005m}%</strong></div>
                            <div className="lcv-candidate-row"><span>Within 0.10m:</span><strong>{mm.point_coverage?.pct_within_010m}%</strong></div>
                            <div className="lcv-candidate-row"><span>Within 0.20m:</span><strong>{mm.point_coverage?.pct_within_020m}%</strong></div>
                            <div className="lcv-candidate-row"><span>Within 0.50m:</span><strong>{mm.point_coverage?.pct_within_050m}%</strong></div>
                          </div>
                        </div>

                        <div className="lcv-control-section">
                          <h4>Mesh Support / Coverage</h4>
                          <p className="lcv-hint" style={{ marginBottom: 4 }}>
                            Poisson may create surfaces where the scanner did NOT observe geometry.
                          </p>
                          <div className="lcv-candidate-card">
                            <div className="lcv-candidate-row"><span>Samples:</span><strong>{mm.mesh_support?.total_samples?.toLocaleString()}</strong></div>
                            <div className="lcv-candidate-row"><span>Supported ≤0.10m:</span><strong>{mm.mesh_support?.pct_supported_within_010m}%</strong></div>
                            <div className="lcv-candidate-row"><span>Supported ≤0.20m:</span><strong>{mm.mesh_support?.pct_supported_within_020m}%</strong></div>
                            <div className="lcv-candidate-row"><span>Supported ≤0.50m:</span><strong>{mm.mesh_support?.pct_supported_within_050m}%</strong></div>
                            <div className="lcv-candidate-row"><span>Supported ≤1.00m:</span><strong>{mm.mesh_support?.pct_supported_within_100m}%</strong></div>
                          </div>
                        </div>

                        {mm.components && mm.components.length > 0 && (
                          <div className="lcv-control-section">
                            <h4>Connected Components ({mm.component_count})</h4>
                            <div style={{ maxHeight: 160, overflowY: "auto" }}>
                              {mm.components.map((comp) => (
                                <div key={comp.component_id} className="lcv-candidate-card" style={{ marginBottom: 4, padding: 6 }}>
                                  <div className="lcv-candidate-row">
                                    <span>Component #{comp.component_id}</span>
                                    <strong>{comp.triangle_count?.toLocaleString()} tris</strong>
                                  </div>
                                  <div className="lcv-candidate-row">
                                    <span>Area:</span>
                                    <strong>{comp.area_m2} m²</strong>
                                  </div>
                                  <div className="lcv-candidate-row">
                                    <span>Vertices:</span>
                                    <strong>{comp.vertex_count?.toLocaleString()}</strong>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {mm.method_comparison && mm.method_comparison.length > 1 && (
                          <div className="lcv-control-section">
                            <h4>Method Comparison</h4>
                            <div style={{ maxHeight: 120, overflowY: "auto", fontSize: 10 }}>
                              {mm.method_comparison.map((m, i) => (
                                <div key={i} className="lcv-candidate-card" style={{ marginBottom: 3, padding: 4 }}>
                                  <div className="lcv-candidate-row">
                                    <span>{m.method}</span>
                                    <strong>{m.vertex_count?.toLocaleString()} V / {m.triangle_count?.toLocaleString()} T</strong>
                                  </div>
                                  <div className="lcv-candidate-row">
                                    <span>P2M Mean:</span>
                                    <strong>{m.point_to_mesh_distance?.mean_m}m</strong>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="lcv-georef-badge" style={{ marginTop: 8 }}>
                          ⚠️ {mm.disclaimer}
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* TAB: Scans */}
                {activeTab === "scans" && (
                  <div className="lcv-tab-content">
                    <div className="lcv-scan-actions">
                      <button onClick={showAllScans}>Show All</button>
                      <button onClick={hideAllScans}>Hide All</button>
                    </div>
                    <div className="lcv-scan-list">
                      {(sampleData?.scans || []).map((sc) => (
                        <label key={sc.scan_index} className={`lcv-scan-row ${scanVisibility[sc.scan_index] ? "active" : "dimmed"}`}>
                          <input type="checkbox" checked={scanVisibility[sc.scan_index] !== false} onChange={() => toggleScan(sc.scan_index)} />
                          <span className="lcv-scan-label">Scan {String(sc.scan_index).padStart(2, "0")}</span>
                          <span className="lcv-scan-pts">{(sc.point_count || 0).toLocaleString()} pts</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* TAB: Info */}
                {activeTab === "info" && (
                  <div className="lcv-tab-content">
                    <div className="lcv-control-section" style={{ marginBottom: 12 }}>
                      <h4 style={{ color: "#38bdf8", marginBottom: 6 }}>Camera & View Debug</h4>
                      <div className="lcv-candidate-card" style={{ fontSize: 11, padding: 8 }}>
                        <div className="lcv-candidate-row" style={{ marginBottom: 6 }}>
                          <span>Active View Preset:</span>
                          <strong style={{ color: "#fbbf24", fontWeight: 700, fontSize: 12 }}>
                            {cameraDebugInfo?.activeView || activePreset.toUpperCase()}
                          </strong>
                        </div>
                        <div style={{ marginTop: 4, paddingTop: 4, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                          <span style={{ color: "#94a3b8", display: "block", fontSize: 10 }}>Camera Position (Local XYZ):</span>
                          <div style={{ display: "flex", gap: 8, fontFamily: "monospace", color: "#e2e8f0", marginTop: 2 }}>
                            <span>X: <strong style={{ color: "#38bdf8" }}>{cameraDebugInfo?.cameraPosition?.x ?? "--"}</strong></span>
                            <span>Y: <strong style={{ color: "#38bdf8" }}>{cameraDebugInfo?.cameraPosition?.y ?? "--"}</strong></span>
                            <span>Z: <strong style={{ color: "#38bdf8" }}>{cameraDebugInfo?.cameraPosition?.z ?? "--"}</strong></span>
                          </div>
                        </div>
                        <div style={{ marginTop: 6, paddingTop: 4, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                          <span style={{ color: "#94a3b8", display: "block", fontSize: 10 }}>Controls Target (Local XYZ):</span>
                          <div style={{ display: "flex", gap: 8, fontFamily: "monospace", color: "#e2e8f0", marginTop: 2 }}>
                            <span>X: <strong style={{ color: "#86efac" }}>{cameraDebugInfo?.controlsTarget?.x ?? "--"}</strong></span>
                            <span>Y: <strong style={{ color: "#86efac" }}>{cameraDebugInfo?.controlsTarget?.y ?? "--"}</strong></span>
                            <span>Z: <strong style={{ color: "#86efac" }}>{cameraDebugInfo?.controlsTarget?.z ?? "--"}</strong></span>
                          </div>
                        </div>
                        <div style={{ marginTop: 6, paddingTop: 4, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                          <span style={{ color: "#94a3b8", display: "block", fontSize: 10 }}>Model Center (Local XYZ):</span>
                          <div style={{ display: "flex", gap: 8, fontFamily: "monospace", color: "#e2e8f0", marginTop: 2 }}>
                            <span>X: <strong style={{ color: "#ec4899" }}>{cameraDebugInfo?.modelCenter?.x ?? "--"}</strong></span>
                            <span>Y: <strong style={{ color: "#ec4899" }}>{cameraDebugInfo?.modelCenter?.y ?? "--"}</strong></span>
                            <span>Z: <strong style={{ color: "#ec4899" }}>{cameraDebugInfo?.modelCenter?.z ?? "--"}</strong></span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="lcv-info-grid">
                      <div className="lcv-info-item">
                        <span className="lcv-info-label">Original Points</span>
                        <span className="lcv-info-value">{(sampleData?.total_points || 219350286).toLocaleString()}</span>
                      </div>
                      <div className="lcv-info-item">
                        <span className="lcv-info-label">Displayed Points</span>
                        <span className="lcv-info-value">{(sampleData?.sampled_points || 94130).toLocaleString()}</span>
                      </div>
                      <div className="lcv-info-item">
                        <span className="lcv-info-label">Scans</span>
                        <span className="lcv-info-value">{sampleData?.scan_count || 21}</span>
                      </div>
                      <div className="lcv-info-item">
                        <span className="lcv-info-label">Coordinate Frame</span>
                        <span className="lcv-info-value highlight-local">LOCAL METERS</span>
                      </div>
                      <div className="lcv-info-item">
                        <span className="lcv-info-label">CRS</span>
                        <span className="lcv-info-value">NONE</span>
                      </div>
                      <div className="lcv-info-item">
                        <span className="lcv-info-label">Georeferenced</span>
                        <span className="lcv-info-value" style={{ color: "#ef4444" }}>FALSE</span>
                      </div>
                    </div>

                    <div className="lcv-georef-badge">
                      📌 Raw local coordinates preserved in meters relative to primary
                      scanner origin (0,0,0). No WGS84 / EPSG:4326 transformation applied.
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
