/**
 * ManualEntryForm Component
 *
 * Form for manual building + floors + properties entry.
 * Calls the SAME processing pipeline as document upload via POST /api/manual-entry.
 */

import { useState } from "react";
import { submitManualEntry } from "../services/api";

export default function ManualEntryForm({ onComplete, onBack }) {
  const [building, setBuilding] = useState({
    building_id: "",
    name: "",
    parcel_id: "",
    latitude: "",
    longitude: "",
    height: "",
    num_floors: 1,
  });
  const [floors, setFloors] = useState([
    { floor_number: 1, z_min: 0, z_max: 3 },
  ]);
  const [properties, setProperties] = useState([
    { floor_number: 1, unit_id: "", property_type: "residential", area: "", ror_id: "" },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const updateBuilding = (field, value) => {
    setBuilding((prev) => ({ ...prev, [field]: value }));
  };

  const addFloor = () => {
    const nextNum = floors.length + 1;
    setFloors([...floors, {
      floor_number: nextNum,
      z_min: (nextNum - 1) * 3,
      z_max: nextNum * 3,
    }]);
  };

  const removeFloor = (idx) => {
    if (floors.length <= 1) return;
    const removed = floors[idx];
    setFloors(floors.filter((_, i) => i !== idx));
    setProperties(properties.filter((p) => p.floor_number !== removed.floor_number));
  };

  const addProperty = () => {
    setProperties([...properties, {
      floor_number: 1,
      unit_id: "",
      property_type: "residential",
      area: "",
      ror_id: "",
    }]);
  };

  const removeProperty = (idx) => {
    if (properties.length <= 1) return;
    setProperties(properties.filter((_, i) => i !== idx));
  };

  const updateProperty = (idx, field, value) => {
    setProperties(properties.map((p, i) =>
      i === idx ? { ...p, [field]: value } : p
    ));
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);

    try {
      const payload = {
        building_id: building.building_id || undefined,
        name: building.name || undefined,
        parcel_id: building.parcel_id || "AUTO",
        latitude: building.latitude ? parseFloat(building.latitude) : null,
        longitude: building.longitude ? parseFloat(building.longitude) : null,
        height: building.height ? parseFloat(building.height) : null,
        num_floors: floors.length,
        floors: floors.map((f) => ({
          floor_number: f.floor_number,
          z_min: f.z_min,
          z_max: f.z_max,
        })),
        properties: properties.map((p) => ({
          floor_number: p.floor_number,
          unit_id: p.unit_id || undefined,
          property_type: p.property_type || undefined,
          area: p.area ? parseFloat(p.area) : null,
          ror_id: p.ror_id || undefined,
        })),
      };

      const result = await submitManualEntry(payload);
      onComplete(result);
    } catch (e) {
      setError(e.message || "Manual entry failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onBack}>
      <div className="modal-card modal-card-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <button className="modal-back-btn" onClick={onBack}>← Back</button>
          <h2>Manual Building Entry</h2>
          <button className="modal-close-btn" onClick={onBack}>✕</button>
        </div>

        {/* Building Info */}
        <div className="form-section">
          <h3>Building Information</h3>
          <div className="form-grid">
            <div className="form-field">
              <label>Building ID</label>
              <input
                type="text"
                placeholder="e.g. B-TEST-01 (auto if blank)"
                value={building.building_id}
                onChange={(e) => updateBuilding("building_id", e.target.value)}
              />
            </div>
            <div className="form-field">
              <label>Building Name</label>
              <input
                type="text"
                placeholder="e.g. Sunrise Apartments"
                value={building.name}
                onChange={(e) => updateBuilding("name", e.target.value)}
              />
            </div>
            <div className="form-field">
              <label>Parcel ID</label>
              <input
                type="text"
                placeholder="e.g. P001 (auto if blank)"
                value={building.parcel_id}
                onChange={(e) => updateBuilding("parcel_id", e.target.value)}
              />
            </div>
            <div className="form-field">
              <label>Latitude</label>
              <input
                type="number" step="any"
                placeholder="28.6139"
                value={building.latitude}
                onChange={(e) => updateBuilding("latitude", e.target.value)}
              />
            </div>
            <div className="form-field">
              <label>Longitude</label>
              <input
                type="number" step="any"
                placeholder="77.2090"
                value={building.longitude}
                onChange={(e) => updateBuilding("longitude", e.target.value)}
              />
            </div>
            <div className="form-field">
              <label>Height (m)</label>
              <input
                type="number" step="any"
                placeholder="12"
                value={building.height}
                onChange={(e) => updateBuilding("height", e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Floors */}
        <div className="form-section">
          <h3>
            Floors
            <button className="form-add-btn" onClick={addFloor}>+ Add Floor</button>
          </h3>
          {floors.map((floor, fi) => (
            <div key={fi} className="form-inline-row">
              <span className="form-inline-label">Floor {floor.floor_number}</span>
              <div className="form-inline-field">
                <label>Z Min</label>
                <input
                  type="number" step="any"
                  value={floor.z_min}
                  onChange={(e) => {
                    const updated = [...floors];
                    updated[fi] = { ...updated[fi], z_min: parseFloat(e.target.value) || 0 };
                    setFloors(updated);
                  }}
                />
              </div>
              <div className="form-inline-field">
                <label>Z Max</label>
                <input
                  type="number" step="any"
                  value={floor.z_max}
                  onChange={(e) => {
                    const updated = [...floors];
                    updated[fi] = { ...updated[fi], z_max: parseFloat(e.target.value) || 0 };
                    setFloors(updated);
                  }}
                />
              </div>
              {floors.length > 1 && (
                <button className="form-remove-btn" onClick={() => removeFloor(fi)}>✕</button>
              )}
            </div>
          ))}
        </div>

        {/* Properties */}
        <div className="form-section">
          <h3>
            Properties
            <button className="form-add-btn" onClick={addProperty}>+ Add Property</button>
          </h3>
          {properties.map((prop, pi) => (
            <div key={pi} className="form-property-row">
              <div className="form-field">
                <label>Floor</label>
                <select
                  value={prop.floor_number}
                  onChange={(e) => updateProperty(pi, "floor_number", parseInt(e.target.value))}
                >
                  {floors.map((f) => (
                    <option key={f.floor_number} value={f.floor_number}>
                      Floor {f.floor_number}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label>Unit ID</label>
                <input
                  type="text"
                  placeholder="e.g. S101"
                  value={prop.unit_id}
                  onChange={(e) => updateProperty(pi, "unit_id", e.target.value)}
                />
              </div>
              <div className="form-field">
                <label>Type</label>
                <select
                  value={prop.property_type}
                  onChange={(e) => updateProperty(pi, "property_type", e.target.value)}
                >
                  <option value="residential">Residential</option>
                  <option value="commercial">Commercial</option>
                  <option value="mixed">Mixed</option>
                </select>
              </div>
              <div className="form-field">
                <label>Area (m²)</label>
                <input
                  type="number" step="any"
                  placeholder="80"
                  value={prop.area}
                  onChange={(e) => updateProperty(pi, "area", e.target.value)}
                />
              </div>
              <div className="form-field">
                <label>RoR ID</label>
                <input
                  type="text"
                  placeholder="Optional"
                  value={prop.ror_id}
                  onChange={(e) => updateProperty(pi, "ror_id", e.target.value)}
                />
              </div>
              {properties.length > 1 && (
                <button className="form-remove-btn" onClick={() => removeProperty(pi)}>✕</button>
              )}
            </div>
          ))}
        </div>

        {error && <div className="upload-error"><strong>Error:</strong> {error}</div>}

        <div className="review-actions">
          <button className="connection-btn connection-btn-secondary" onClick={onBack}>
            Cancel
          </button>
          <button
            className="connection-btn connection-btn-primary"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create Building"}
          </button>
        </div>
      </div>
    </div>
  );
}
