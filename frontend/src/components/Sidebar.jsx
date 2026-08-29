/**
 * Sidebar Component
 *
 * Left sidebar containing layer controls and processing actions.
 * Processing buttons are disabled in M1 (frontend-only milestone).
 */

import LayerControl from "./LayerControl";

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <LayerControl />

      <div className="sidebar-section">
        <h3 className="sidebar-section-title">Processing</h3>
        <p className="sidebar-hint">Available in Milestone 2+</p>
        <div className="sidebar-actions">
          <button className="sidebar-btn" disabled title="Milestone 2+">
            📷 Upload Drone Data
          </button>
          <button className="sidebar-btn" disabled title="Milestone 4+">
            🏗️ Extract Buildings
          </button>
          <button className="sidebar-btn" disabled title="Milestone 4+">
            📡 Process LiDAR
          </button>
          <button className="sidebar-btn" disabled title="Milestone 2+">
            🧊 Generate 3D Properties
          </button>
        </div>
      </div>

      <div className="sidebar-section sidebar-footer">
        <div className="sidebar-context-info">
          <p className="context-label">Geographic Context</p>
          <p className="context-value">New Delhi, India</p>
        </div>
        <div className="sidebar-context-info">
          <p className="context-label">Cadastral Data</p>
          <p className="context-value">Synthetic Demo Data</p>
        </div>
      </div>
    </aside>
  );
}
