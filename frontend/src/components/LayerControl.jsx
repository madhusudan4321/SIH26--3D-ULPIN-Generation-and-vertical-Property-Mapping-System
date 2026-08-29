/**
 * LayerControl Component
 *
 * Checkbox toggles that show/hide Cesium entity groups.
 * Each toggle directly controls layer visibility via selection context.
 */

import { useSelection } from "../hooks/useSelection";

const LAYERS = [
  { key: "parcels", label: "Parcels", icon: "📐", color: "#f59e0b" },
  { key: "buildings", label: "Buildings", icon: "🏢", color: "#94a3b8" },
  { key: "properties", label: "3D Properties", icon: "🏠", color: "#06b6d4" },
  { key: "underground", label: "Underground", icon: "⚡", color: "#ef4444" },
];

export default function LayerControl() {
  const { layerVisibility, toggleLayer } = useSelection();

  return (
    <div className="layer-control">
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
  );
}
