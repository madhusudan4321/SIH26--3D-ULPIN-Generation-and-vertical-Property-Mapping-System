/**
 * PropertyPanel Component
 *
 * Right panel showing selected property details:
 * - DEMO DATA badge
 * - 3D ULPIN
 * - Spatial identity (parcel, building, floor, unit)
 * - Elevation info with source
 * - RoR information
 * - Validation results
 *
 * Geometry and property information are linked through identifiers.
 * The 3D model itself does not contain ownership data.
 */

import { useState, useEffect } from "react";
import { useSelection } from "../hooks/useSelection";
import { getProperty, getRor, getFloor, getBuilding } from "../services/api";
import { validateProperty } from "../services/validation";
import ValidationPanel from "./ValidationPanel";

export default function PropertyPanel() {
  const { selectedPropertyId, panelOpen, clearSelection } = useSelection();
  const [property, setProperty] = useState(null);
  const [ror, setRor] = useState(null);
  const [floor, setFloor] = useState(null);
  const [building, setBuilding] = useState(null);
  const [validation, setValidation] = useState(null);
  const [showValidation, setShowValidation] = useState(false);

  useEffect(() => {
    if (!selectedPropertyId) {
      setProperty(null);
      setRor(null);
      setFloor(null);
      setBuilding(null);
      setValidation(null);
      setShowValidation(false);
      return;
    }

    const loadData = async () => {
      const prop = await getProperty(selectedPropertyId);
      setProperty(prop);

      if (prop) {
        const [rorData, floorData, buildingData] = await Promise.all([
          prop.ror_id ? getRor(prop.ror_id) : null,
          getFloor(prop.floor_id),
          getBuilding(prop.building_id),
        ]);
        setRor(rorData);
        setFloor(floorData);
        setBuilding(buildingData);

        // Run validation
        const result = validateProperty(selectedPropertyId);
        setValidation(result);
      }
    };

    loadData();
  }, [selectedPropertyId]);

  if (!panelOpen || !property) return null;

  return (
    <div className="property-panel">
      <div className="property-panel-header">
        <h2>Property Details</h2>
        <button className="panel-close-btn" onClick={clearSelection}>
          ✕
        </button>
      </div>

      {/* DEMO DATA Badge */}
      <div className="demo-data-banner">
        ⚠ DEMONSTRATION DATA
        <span className="demo-data-sub">Not a real government record</span>
      </div>

      {/* 3D ULPIN */}
      <div className="property-section">
        <h3 className="section-label">3D ULPIN (Prototype)</h3>
        <p className="ulpin-value">{property.three_d_ulpin}</p>
      </div>

      {/* Spatial Identity */}
      <div className="property-section">
        <h3 className="section-label">Spatial Identity</h3>
        <div className="property-grid">
          <div className="property-field">
            <span className="field-label">Parcel</span>
            <span className="field-value">{property.parcel_id}</span>
          </div>
          <div className="property-field">
            <span className="field-label">Building</span>
            <span className="field-value">{property.building_id}</span>
          </div>
          <div className="property-field">
            <span className="field-label">Floor</span>
            <span className="field-value">{floor?.floor_number || "—"}</span>
          </div>
          <div className="property-field">
            <span className="field-label">Unit</span>
            <span className="field-value">{property.unit_number}</span>
          </div>
        </div>
      </div>

      {/* Elevation */}
      {floor && (
        <div className="property-section">
          <h3 className="section-label">Elevation</h3>
          <div className="property-grid">
            <div className="property-field">
              <span className="field-label">Z Min</span>
              <span className="field-value">{floor.z_min} m</span>
            </div>
            <div className="property-field">
              <span className="field-label">Z Max</span>
              <span className="field-value">{floor.z_max} m</span>
            </div>
            {building && (
              <div className="property-field">
                <span className="field-label">Bldg Height</span>
                <span className="field-value">{building.height} m</span>
              </div>
            )}
            <div className="property-field">
              <span className="field-label">Source</span>
              <span className="field-value source-badge">
                {floor.elevation_source}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Record of Rights */}
      {ror && (
        <div className="property-section">
          <h3 className="section-label">Record of Rights</h3>
          <div className="property-grid">
            <div className="property-field">
              <span className="field-label">RoR ID</span>
              <span className="field-value">{ror.ror_id}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Owner</span>
              <span className="field-value">{ror.owner_name}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Land Use</span>
              <span className="field-value">{ror.land_use}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Area</span>
              <span className="field-value">{ror.area} sq m</span>
            </div>
            <div className="property-field">
              <span className="field-label">Rights</span>
              <span className="field-value">{ror.rights}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Source</span>
              <span className="field-value source-badge">{ror.source}</span>
            </div>
          </div>
        </div>
      )}

      {/* Validation */}
      <div className="property-section">
        <h3 className="section-label">
          Validation
          <button
            className="validation-toggle-btn"
            onClick={() => setShowValidation(!showValidation)}
          >
            {showValidation ? "Hide" : "View Details"}
          </button>
        </h3>
        {validation && (
          <>
            {!showValidation && (
              <div className={`validation-summary validation-${validation.overall_status.toLowerCase()}`}>
                {validation.overall_status === "PASS" ? "✅" : validation.overall_status === "WARNING" ? "⚠️" : "❌"}{" "}
                {validation.overall_status} ({validation.checks.filter(c => c.status === "PASS").length}/{validation.checks.length} checks)
              </div>
            )}
            {showValidation && <ValidationPanel validationResult={validation} />}
          </>
        )}
      </div>
    </div>
  );
}
