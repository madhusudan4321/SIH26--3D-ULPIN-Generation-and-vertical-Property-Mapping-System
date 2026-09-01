/**
 * Sidebar Component
 *
 * Left sidebar with layer controls, registered PostgreSQL buildings list, and processing actions.
 * Dynamic registered building list fetched directly from PostgreSQL/PostGIS backend.
 */

import { useState, useEffect } from "react";
import LayerControl from "./LayerControl";
import { getBuildings } from "../services/api";
import { useSelection } from "../hooks/useSelection";

export default function Sidebar({ onAddBuilding, onImportDocument, backendStatus, refreshKey }) {
  const [buildings, setBuildings] = useState([]);
  const [loadingBuildings, setLoadingBuildings] = useState(false);
  const { selectedBuildingId, flyToBuilding, selectBuilding } = useSelection();

  useEffect(() => {
    let isMounted = true;
    async function loadRegisteredBuildings() {
      if (backendStatus !== "connected") return;
      try {
        setLoadingBuildings(true);
        const data = await getBuildings();
        if (isMounted && Array.isArray(data)) {
          setBuildings(data);
        }
      } catch (e) {
        console.warn("Failed to load registered buildings:", e);
      } finally {
        if (isMounted) setLoadingBuildings(false);
      }
    }

    loadRegisteredBuildings();
    return () => {
      isMounted = false;
    };
  }, [backendStatus, refreshKey]);

  const handleBuildingClick = (building) => {
    flyToBuilding(building.building_id, {
      latitude: building.latitude,
      longitude: building.longitude,
      height: building.height,
    });
    selectBuilding(building.building_id);
  };

  return (
    <aside className="sidebar">
      <LayerControl />

      {/* Registered Buildings List Section */}
      <div className="sidebar-section">
        <div className="sidebar-section-header">
          <h3 className="sidebar-section-title">Registered Buildings</h3>
          <span className="sidebar-count-badge">{buildings.length}</span>
        </div>

        <div className="registered-buildings-list">
          {loadingBuildings && buildings.length === 0 ? (
            <div className="sidebar-loading">Loading PostGIS buildings...</div>
          ) : buildings.length === 0 ? (
            <div className="sidebar-empty">No buildings registered yet.</div>
          ) : (
            buildings.map((b) => {
              const isSelected = selectedBuildingId === b.building_id;
              const hasCoords = b.latitude != null && b.longitude != null;
              return (
                <button
                  key={b.building_id}
                  className={`building-card-item ${isSelected ? "selected" : ""}`}
                  onClick={() => handleBuildingClick(b)}
                >
                  <div className="building-card-header">
                    <span className="building-card-icon">🏢</span>
                    <div className="building-card-titles">
                      <span className="building-card-name">{b.name || b.building_id}</span>
                      <span className="building-card-id">{b.building_id}</span>
                    </div>
                  </div>

                  <div className="building-card-details">
                    {hasCoords && (
                      <span className="building-card-coords">
                        📍 {b.latitude?.toFixed(4)}°, {b.longitude?.toFixed(4)}°
                      </span>
                    )}
                    <span className="building-card-meta">
                      {b.num_floors ? `${b.num_floors} Floors` : ""}
                      {b.property_count ? ` • ${b.property_count} Units` : ""}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="sidebar-section">
        <h3 className="sidebar-section-title">Actions</h3>
        <div className="sidebar-actions">
          <button
            className="sidebar-btn sidebar-btn-active"
            onClick={onAddBuilding}
            title="Add a new building via import or manual entry"
          >
            🏗️ Add Building
          </button>
          <button
            className="sidebar-btn sidebar-btn-active"
            onClick={onImportDocument}
            title="Upload a document (PDF/CSV/JSON/GeoJSON)"
          >
            📄 Import Document
          </button>
          <button className="sidebar-btn" disabled title="Planned for future phase">
            📡 Process LiDAR
          </button>
          <button className="sidebar-btn" disabled title="Planned for future phase">
            📷 Drone Photogrammetry
          </button>
        </div>
      </div>

      <div className="sidebar-section sidebar-footer">
        <div className="sidebar-context-info">
          <p className="context-label">Data Source</p>
          <p className="context-value">
            {backendStatus === "connected" ? "PostgreSQL/PostGIS" : "Local Demo Data"}
          </p>
        </div>
        <div className="sidebar-context-info">
          <p className="context-label">Status</p>
          <p className={`context-value ${backendStatus === "connected" ? "status-connected" : "status-disconnected"}`}>
            {backendStatus === "connected" ? "Backend Connected" : "Backend Offline"}
          </p>
        </div>
      </div>
    </aside>
  );
}
