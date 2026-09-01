/**
 * PropertyPanel Component
 *
 * Right panel showing selected property or building details:
 * - Supports Building Selection (building_id, lat/lon, height, floors, units list)
 * - Supports Property Unit Selection (unit_id, elevation z_min/z_max, area, linked RoR)
 * - Geometry provenance badge (GeometryBadge)
 * - Building Delete capability with confirmation
 */

import { useState, useEffect } from "react";
import { useSelection } from "../hooks/useSelection";
import { getProperty, getBuilding, deleteBuilding } from "../services/api";
import { validateProperty } from "../services/validation";
import ValidationPanel from "./ValidationPanel";
import GeometryBadge from "./GeometryBadge";

export default function PropertyPanel({ onDeleteBuildingSuccess }) {
  const {
    selectedPropertyId,
    selectedBuildingId,
    selectionType,
    panelOpen,
    clearSelection,
    selectProperty,
    flyTo,
  } = useSelection();

  // Data states
  const [property, setProperty] = useState(null);
  const [buildingData, setBuildingData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validation, setValidation] = useState(null);
  const [showValidation, setShowValidation] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Load property or building data whenever selection changes
  useEffect(() => {
    if (!panelOpen) return;

    let isMounted = true;

    async function loadSelectionData() {
      setLoading(true);
      setError(null);

      try {
        if (selectionType === "building" || (!selectedPropertyId && selectedBuildingId)) {
          // Load full building details
          const bld = await getBuilding(selectedBuildingId);
          if (isMounted) {
            setBuildingData(bld);
            setProperty(null);
          }
        } else if (selectedPropertyId) {
          // Load property details
          const prop = await getProperty(selectedPropertyId);
          if (isMounted) {
            setProperty(prop);
            setBuildingData(null);
            const valResult = validateProperty(selectedPropertyId);
            setValidation(valResult);
          }
        }
      } catch (e) {
        if (isMounted) {
          setError(e.message || "Failed to load selection data");
          setProperty(null);
          setBuildingData(null);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadSelectionData();

    return () => {
      isMounted = false;
    };
  }, [selectedPropertyId, selectedBuildingId, selectionType, panelOpen]);

  const handleDeleteBuilding = async (bldId) => {
    const targetId = bldId || property?.building_id || buildingData?.building_id;
    if (!targetId) return;
    setDeleting(true);
    try {
      await deleteBuilding(targetId);
      setShowDeleteConfirm(false);
      clearSelection();
      if (onDeleteBuildingSuccess) {
        onDeleteBuildingSuccess(targetId);
      }
    } catch (e) {
      alert(`Delete failed: ${e.message}`);
    } finally {
      setDeleting(false);
    }
  };

  if (!panelOpen) return null;

  if (loading) {
    return (
      <div className="property-panel">
        <div className="property-panel-header">
          <h2>{selectionType === "building" ? "Building Details" : "Property Details"}</h2>
          <button className="panel-close-btn" onClick={clearSelection}>✕</button>
        </div>
        <div className="panel-loading">Loading details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="property-panel">
        <div className="property-panel-header">
          <h2>{selectionType === "building" ? "Building Details" : "Property Details"}</h2>
          <button className="panel-close-btn" onClick={clearSelection}>✕</button>
        </div>
        <div className="panel-error">{error}</div>
      </div>
    );
  }

  // ─── Render Building View ──────────────────────────────────
  if (buildingData && !property) {
    const hasCoords = buildingData.latitude != null && buildingData.longitude != null;
    return (
      <div className="property-panel">
        <div className="property-panel-header">
          <h2>🏢 Building Details</h2>
          <button className="panel-close-btn" onClick={clearSelection}>✕</button>
        </div>

        <div className="demo-data-banner demo-data-banner-real">
          Source: {buildingData.source || "PostgreSQL/PostGIS"}
          <span className="demo-data-sub">Georeferenced Registered Building</span>
        </div>

        <div className="property-section">
          <h3 className="section-label">Building Identity</h3>
          <p className="ulpin-value">{buildingData.name || buildingData.building_id}</p>
          <span className="property-subtext">ID: {buildingData.building_id} • Parcel: {buildingData.parcel_id}</span>
        </div>

        {/* Geographic Coordinates Section */}
        <div className="property-section">
          <h3 className="section-label">Geographic Georeferencing</h3>
          <div className="property-grid">
            <div className="property-field">
              <span className="field-label">Latitude</span>
              <span className="field-value">{hasCoords ? `${buildingData.latitude.toFixed(6)}° N` : "—"}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Longitude</span>
              <span className="field-value">{hasCoords ? `${buildingData.longitude.toFixed(6)}° E` : "—"}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Height</span>
              <span className="field-value">{buildingData.height ? `${buildingData.height} m` : "Derived"}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Ground Elevation</span>
              <span className="field-value">{buildingData.ground_elevation} m</span>
            </div>
          </div>
        </div>

        {/* Footprint & Spatial Extent */}
        <div className="property-section">
          <h3 className="section-label">Spatial & Floor Structure</h3>
          <div className="property-grid">
            <div className="property-field">
              <span className="field-label">Floors</span>
              <span className="field-value">{buildingData.num_floors || buildingData.floors?.length || "—"}</span>
            </div>
            <div className="property-field">
              <span className="field-label">Units</span>
              <span className="field-value">{buildingData.properties?.length || 0} Units</span>
            </div>
          </div>
        </div>

        {/* Units List */}
        {buildingData.properties && buildingData.properties.length > 0 && (
          <div className="property-section">
            <h3 className="section-label">Property Units</h3>
            <div className="panel-units-scroll">
              {buildingData.properties.map((p) => (
                <button
                  key={p.ulpin || p.id}
                  className="panel-unit-item"
                  onClick={() => {
                    flyTo(p.ulpin);
                    selectProperty(p.ulpin);
                  }}
                >
                  <span className="unit-name">🏠 {p.unit_id}</span>
                  <span className="unit-type">Floor {p.floor_number} • {p.property_type || "Unit"} ({p.area} m²)</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Delete Action */}
        <div className="property-section panel-danger-zone">
          {!showDeleteConfirm ? (
            <button className="delete-building-btn" onClick={() => setShowDeleteConfirm(true)}>
              🗑 Delete Building
            </button>
          ) : (
            <div className="delete-confirm-box">
              <p>Permanently delete <strong>{buildingData.building_id}</strong> and all child floors/properties?</p>
              <div className="delete-confirm-actions">
                <button className="confirm-delete-btn" onClick={() => handleDeleteBuilding(buildingData.building_id)} disabled={deleting}>
                  {deleting ? "Deleting..." : "Yes, Delete Building"}
                </button>
                <button className="cancel-delete-btn" onClick={() => setShowDeleteConfirm(false)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ─── Render Property Unit View ─────────────────────────────
  if (!property) return null;

  const ror = property.ror;
  const isDemoData = property.data_source === "DEMO_DATA" || property.data_source === "synthetic_demo";

  return (
    <div className="property-panel">
      <div className="property-panel-header">
        <h2>Property Unit Details</h2>
        <button className="panel-close-btn" onClick={clearSelection}>✕</button>
      </div>

      {/* Data Source Badge */}
      <div className={`demo-data-banner ${isDemoData ? "" : "demo-data-banner-real"}`}>
        {isDemoData ? "⚠ DEMONSTRATION DATA" : `Source: ${property.data_source}`}
        <span className="demo-data-sub">
          {isDemoData ? "Not a real government record" : `Verified: ${property.verification_status}`}
        </span>
      </div>

      {/* Geometry Provenance */}
      <div className="property-section">
        <GeometryBadge
          geometrySource={property.geometry_source}
          geometryAvailable={property.geometry_available}
        />
      </div>

      {/* 3D ULPIN */}
      <div className="property-section">
        <h3 className="section-label">3D ULPIN (Prototype)</h3>
        <p className="ulpin-value">{property.ulpin}</p>
      </div>

      {/* Spatial Identity */}
      <div className="property-section">
        <h3 className="section-label">Spatial Identity</h3>
        <div className="property-grid">
          <div className="property-field">
            <span className="field-label">Parcel</span>
            <span className="field-value">{property.parcel_id || "—"}</span>
          </div>
          <div className="property-field">
            <span className="field-label">Building</span>
            <span className="field-value">{property.building_name || property.building_id}</span>
          </div>
          <div className="property-field">
            <span className="field-label">Floor</span>
            <span className="field-value">{property.floor_number ?? "—"}</span>
          </div>
          <div className="property-field">
            <span className="field-label">Unit ID</span>
            <span className="field-value">{property.unit_id || "—"}</span>
          </div>
        </div>
      </div>

      {/* Attributes */}
      <div className="property-section">
        <h3 className="section-label">Property Attributes</h3>
        <div className="property-grid">
          <div className="property-field">
            <span className="field-label">Type</span>
            <span className="field-value capitalize">{property.property_type || "—"}</span>
          </div>
          <div className="property-field">
            <span className="field-label">Recorded Area</span>
            <span className="field-value">{property.area ? `${property.area} m²` : "—"}</span>
          </div>
        </div>
      </div>

      {/* Elevation */}
      <div className="property-section">
        <h3 className="section-label">Elevation (3D Boundary)</h3>
        <div className="property-grid">
          <div className="property-field">
            <span className="field-label">Z Min (Base)</span>
            <span className="field-value">{property.z_min ?? "0"} m</span>
          </div>
          <div className="property-field">
            <span className="field-label">Z Max (Ceiling)</span>
            <span className="field-value">{property.z_max ?? "3"} m</span>
          </div>
        </div>
      </div>

      {/* Linked RoR */}
      <div className="property-section">
        <h3 className="section-label">Record of Rights (RoR)</h3>
        {ror ? (
          <div className="ror-box">
            <div className="ror-field">
              <span className="field-label">RoR ID</span>
              <span className="field-value">{ror.ror_id}</span>
            </div>
            <div className="ror-field">
              <span className="field-label">Owner</span>
              <span className="field-value">{ror.owner_name}</span>
            </div>
            <div className="ror-field">
              <span className="field-label">Land Use</span>
              <span className="field-value">{ror.land_use}</span>
            </div>
            <div className="ror-field">
              <span className="field-label">Rights</span>
              <span className="field-value">{ror.rights}</span>
            </div>
          </div>
        ) : (
          <p className="no-data">No RoR record linked (RoR ID: {property.ror_id || "None"})</p>
        )}
      </div>

      {/* Validation */}
      {validation && (
        <div className="property-section">
          <button
            className="validation-toggle-btn"
            onClick={() => setShowValidation(!showValidation)}
          >
            {showValidation ? "Hide Validation Details ▲" : "Show Validation Details ▼"}
          </button>
          {showValidation && <ValidationPanel result={validation} />}
        </div>
      )}

      {/* Delete Action */}
      <div className="property-section panel-danger-zone">
        {!showDeleteConfirm ? (
          <button className="delete-building-btn" onClick={() => setShowDeleteConfirm(true)}>
            🗑 Delete Building ({property.building_id})
          </button>
        ) : (
          <div className="delete-confirm-box">
            <p>Permanently delete building <strong>{property.building_id}</strong>?</p>
            <div className="delete-confirm-actions">
              <button className="confirm-delete-btn" onClick={() => handleDeleteBuilding()} disabled={deleting}>
                {deleting ? "Deleting..." : "Yes, Delete Building"}
              </button>
              <button className="cancel-delete-btn" onClick={() => setShowDeleteConfirm(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
