/**
 * LayerControl Component
 *
 * Provides:
 * 1. Google Maps Basemap Mode toggle (Roadmap vs Satellite)
 * 2. 3D Camera Navigation Controls (Top View, 3D View, Reset View, Compass N/S/E/W)
 * 3. Building Shell Visualization Mode (Transparent / Opaque / Hidden)
 * 4. Floor Visibility & Exploded Floor View Controls
 * 5. Checkbox toggles that show/hide Cesium entity groups
 */

import { useSelection } from "../hooks/useSelection";

const LAYERS = [
  { key: "parcels", label: "Parcels", icon: "📐", color: "#f59e0b" },
  { key: "buildings", label: "Buildings", icon: "🏢", color: "#94a3b8" },
  { key: "properties", label: "3D Properties", icon: "🏠", color: "#06b6d4" },
  { key: "underground", label: "Underground", icon: "⚡", color: "#ef4444" },
];

const DISPLAY_FLOORS = [1, 2, 3, 4, 5, 6, 7, 8];

export default function LayerControl() {
  const {
    layerVisibility,
    toggleLayer,
    basemapMode,
    setBasemapMode,
    triggerCameraView,
    shellMode,
    setShellMode,
    visibleFloors,
    isolatedFloorNumber,
    explodedView,
    setExplodedView,
    explodeOffset,
    setExplodeOffset,
    toggleFloorVisibility,
    isolateFloor,
    showAllFloors,
  } = useSelection();

  return (
    <div className="layer-control">
      {/* Google Maps Basemap Toggle */}
      <div className="basemap-section">
        <h3 className="sidebar-section-title">Google Basemap</h3>
        <div className="basemap-toggle-group">
          <button
            type="button"
            className={`basemap-toggle-btn ${basemapMode === "roadmap" ? "active" : ""}`}
            onClick={() => setBasemapMode("roadmap")}
          >
            🗺️ Roadmap
          </button>
          <button
            type="button"
            className={`basemap-toggle-btn ${basemapMode === "satellite" ? "active" : ""}`}
            onClick={() => setBasemapMode("satellite")}
          >
            🛰️ Satellite
          </button>
        </div>
      </div>

      {/* 3D Camera Controls */}
      <div className="camera-control-section">
        <h3 className="sidebar-section-title">Camera & 3D Navigation</h3>
        <div className="camera-presets-group">
          <button
            type="button"
            className="camera-btn"
            onClick={() => triggerCameraView("top")}
            title="Inspect Building Footprint & Units from Top (Pitch -90°)"
          >
            📌 TOP
          </button>
          <button
            type="button"
            className="camera-btn"
            onClick={() => triggerCameraView("3d")}
            title="Oblique 3D Perspective View"
          >
            🏠 3D
          </button>
          <button
            type="button"
            className="camera-btn"
            onClick={() => triggerCameraView("reset")}
            title="Reset Camera View to Selected Target"
          >
            🔄 RESET
          </button>
        </div>

        {/* Compass Direction Control Pad */}
        <div className="compass-pad">
          <div className="compass-row">
            <button
              type="button"
              className="compass-btn north"
              onClick={() => triggerCameraView("N")}
              title="Look North"
            >
              N
            </button>
          </div>
          <div className="compass-row middle">
            <button
              type="button"
              className="compass-btn west"
              onClick={() => triggerCameraView("W")}
              title="Look West"
            >
              W
            </button>
            <div className="compass-center">🧭</div>
            <button
              type="button"
              className="compass-btn east"
              onClick={() => triggerCameraView("E")}
              title="Look East"
            >
              E
            </button>
          </div>
          <div className="compass-row">
            <button
              type="button"
              className="compass-btn south"
              onClick={() => triggerCameraView("S")}
              title="Look South"
            >
              S
            </button>
          </div>
        </div>
      </div>

      {/* Building Shell Visualization Mode */}
      <div className="shell-section">
        <h3 className="sidebar-section-title">Building Shell Envelope</h3>
        <div className="basemap-toggle-group">
          <button
            type="button"
            className={`basemap-toggle-btn ${shellMode === "transparent" ? "active" : ""}`}
            onClick={() => setShellMode("transparent")}
            title="Transparent Envelope (Internal 3D property units visible)"
          >
            🔍 Glass
          </button>
          <button
            type="button"
            className={`basemap-toggle-btn ${shellMode === "opaque" ? "active" : ""}`}
            onClick={() => setShellMode("opaque")}
            title="Opaque Solid Building Envelope"
          >
            🏢 Solid
          </button>
          <button
            type="button"
            className={`basemap-toggle-btn ${shellMode === "hidden" ? "active" : ""}`}
            onClick={() => setShellMode("hidden")}
            title="Hide Building Envelope (Units only)"
          >
            🙈 Hidden
          </button>
        </div>
      </div>

      {/* Floor & Exploded View Controls */}
      <div className="floors-control-section">
        <h3 className="sidebar-section-title">Floor & Vertical Structure</h3>

        {/* Exploded View Toggle & Slider */}
        <div className="exploded-control-box">
          <label className="exploded-toggle-label">
            <input
              type="checkbox"
              checked={explodedView}
              onChange={(e) => setExplodedView(e.target.checked)}
              className="layer-checkbox"
            />
            <span className="exploded-title">💥 Exploded Floor View</span>
          </label>
          {explodedView && (
            <div className="exploded-slider-box">
              <span className="slider-label">Spacing: {explodeOffset}m</span>
              <input
                type="range"
                min="2.0"
                max="15.0"
                step="1.0"
                value={explodeOffset}
                onChange={(e) => setExplodeOffset(parseFloat(e.target.value))}
                className="exploded-slider"
              />
            </div>
          )}
        </div>

        {/* Floor Selection & Isolation List */}
        <div className="floor-buttons-header">
          <button
            type="button"
            className="show-all-floors-btn"
            onClick={showAllFloors}
          >
            Show All Floors
          </button>
          {isolatedFloorNumber != null && (
            <span className="isolated-badge">
              Isolating Floor {isolatedFloorNumber}
            </span>
          )}
        </div>

        <div className="floor-checkbox-grid">
          {DISPLAY_FLOORS.map((fNum) => {
            const isChecked = isolatedFloorNumber != null ? isolatedFloorNumber === fNum : visibleFloors.includes(fNum);
            return (
              <div key={fNum} className="floor-check-item">
                <label className="floor-label">
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleFloorVisibility(fNum)}
                    className="layer-checkbox"
                  />
                  <span>F{fNum}</span>
                </label>
                <button
                  type="button"
                  className={`isolate-btn ${isolatedFloorNumber === fNum ? "active" : ""}`}
                  onClick={() => isolateFloor(fNum)}
                  title={`Isolate Floor ${fNum} (hide all other floors)`}
                >
                  🎯
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Layer Group Visibility Controls */}
      <div className="layers-section">
        <h3 className="sidebar-section-title">Layers</h3>
        <div className="layer-list">
          {LAYERS.map((layer) => (
            <label key={layer.key} className="layer-item">
              <input
                type="checkbox"
                checked={layerVisibility[layer.key]}
                onChange={() => toggleLayer(layer.key)}
                className="layer-checkbox"
              />
              <span
                className="layer-color-dot"
                style={{ backgroundColor: layer.color }}
              />
              <span className="layer-icon">{layer.icon}</span>
              <span className="layer-label">{layer.label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
