/**
 * DataReview Component
 *
 * Shows extracted building/property data for user review before confirming.
 * Supports duplicate building ID detection with Overwrite / Cancel choices.
 */

import { useState } from "react";
import { confirmDataset } from "../services/api";

export default function DataReview({ datasetId, extractedData, onConfirm, onBack }) {
  const [data, setData] = useState(extractedData);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);
  const [isDuplicate, setIsDuplicate] = useState(false);

  const building = data?.building || {};
  const floors = data?.floors || [];
  const metadata = data?.metadata || {};

  const handleConfirm = async (overwrite = false) => {
    setConfirming(true);
    setError(null);
    setIsDuplicate(false);
    try {
      const result = await confirmDataset(datasetId, overwrite);
      onConfirm(result);
    } catch (e) {
      const msg = e.message || "Processing failed";
      setError(msg);
      if (msg.includes("already exists")) {
        setIsDuplicate(true);
      }
    } finally {
      setConfirming(false);
    }
  };

  const totalProperties = floors.reduce(
    (sum, f) => sum + (f.properties?.length || 0), 0
  );

  return (
    <div className="modal-overlay" onClick={onBack}>
      <div className="modal-card modal-card-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <button className="modal-back-btn" onClick={onBack}>← Back</button>
          <h2>Review Extracted Data</h2>
          <button className="modal-close-btn" onClick={onBack}>✕</button>
        </div>

        {/* Summary */}
        <div className="review-summary">
          <div className="review-stat">
            <span className="review-stat-value">{building.building_id || "Auto"}</span>
            <span className="review-stat-label">Building ID</span>
          </div>
          <div className="review-stat">
            <span className="review-stat-value">{floors.length}</span>
            <span className="review-stat-label">Floors</span>
          </div>
          <div className="review-stat">
            <span className="review-stat-value">{totalProperties}</span>
            <span className="review-stat-label">Properties</span>
          </div>
          {metadata.source_type && (
            <div className="review-stat">
              <span className="review-stat-value">{metadata.source_type.toUpperCase()}</span>
              <span className="review-stat-label">Source</span>
            </div>
          )}
          {metadata.crs_detected && (
            <div className="review-stat">
              <span className="review-stat-value">{metadata.crs_detected}</span>
              <span className="review-stat-label">CRS</span>
            </div>
          )}
        </div>

        {/* Building Info */}
        <div className="review-section">
          <h3>Building</h3>
          <div className="review-grid">
            <div className="review-field">
              <label>Name</label>
              <span>{building.name || "—"}</span>
            </div>
            <div className="review-field">
              <label>Parcel</label>
              <span>{building.parcel_id || "Auto-generated"}</span>
            </div>
            <div className="review-field">
              <label>Lat/Lon</label>
              <span>
                {building.latitude != null ? `${building.latitude}, ${building.longitude}` : "—"}
              </span>
            </div>
            <div className="review-field">
              <label>Height</label>
              <span>{building.height ? `${building.height}m` : "—"}</span>
            </div>
          </div>
        </div>

        {/* Floors & Properties */}
        <div className="review-section">
          <h3>Floors & Properties</h3>
          {floors.map((floor, fi) => (
            <div key={fi} className="review-floor">
              <h4>
                Floor {floor.floor_number}
                <span className="review-floor-z">
                  ({floor.z_min}m – {floor.z_max}m)
                </span>
              </h4>
              {(floor.properties || []).length === 0 ? (
                <p className="review-empty">No properties on this floor</p>
              ) : (
                <table className="review-table">
                  <thead>
                    <tr>
                      <th>Unit</th>
                      <th>Type</th>
                      <th>Area</th>
                      <th>RoR</th>
                      <th>Geometry</th>
                    </tr>
                  </thead>
                  <tbody>
                    {floor.properties.map((prop, pi) => (
                      <tr key={pi}>
                        <td>{prop.unit_id || "—"}</td>
                        <td>{prop.property_type || "—"}</td>
                        <td>{prop.area ? `${prop.area} m²` : "—"}</td>
                        <td>{prop.ror_id || "—"}</td>
                        <td>
                          {prop.geometry ? (
                            <span className="review-geom-yes">Has polygon</span>
                          ) : (
                            <span className="review-geom-no">Synthetic subdivision</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>

        {/* Duplicate Building Options */}
        {isDuplicate && (
          <div className="upload-error" style={{ background: "rgba(245, 158, 11, 0.15)", borderColor: "rgba(245, 158, 11, 0.4)", color: "#fbbf24" }}>
            <strong>Duplicate Building ID:</strong> Building '{building.building_id}' already exists in PostgreSQL/PostGIS.
            <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
              <button
                className="connection-btn connection-btn-primary"
                style={{ background: "#ef4444", fontSize: "12px", padding: "6px 14px" }}
                onClick={() => handleConfirm(true)}
                disabled={confirming}
              >
                Overwrite Existing Building
              </button>
              <button
                className="connection-btn connection-btn-secondary"
                style={{ fontSize: "12px", padding: "6px 14px" }}
                onClick={() => setIsDuplicate(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {error && !isDuplicate && (
          <div className="upload-error"><strong>Error:</strong> {error}</div>
        )}

        {/* Actions */}
        <div className="review-actions">
          <button className="connection-btn connection-btn-secondary" onClick={onBack}>
            Cancel
          </button>
          <button
            className="connection-btn connection-btn-primary"
            onClick={() => handleConfirm(false)}
            disabled={confirming}
          >
            {confirming ? "Processing..." : "Confirm & Process"}
          </button>
        </div>
      </div>
    </div>
  );
}
