/**
 * Navbar Component
 *
 * Top bar with project branding and search.
 */

import SearchBar from "./SearchBar";

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="navbar-logo">
          <svg viewBox="0 0 32 32" fill="none" width="28" height="28">
            <rect x="2" y="18" width="10" height="12" rx="1" fill="#10b981" opacity="0.8" />
            <rect x="11" y="12" width="10" height="18" rx="1" fill="#06b6d4" opacity="0.8" />
            <rect x="20" y="6" width="10" height="24" rx="1" fill="#3b82f6" opacity="0.8" />
            <rect x="2" y="28" width="28" height="2" rx="1" fill="#f59e0b" />
          </svg>
        </div>
        <div className="navbar-title">
          <h1>3D ULPIN System</h1>
          <span className="navbar-subtitle">Vertical Property Mapping</span>
        </div>
      </div>

      <SearchBar />

      <div className="navbar-info">
        <span className="navbar-badge demo-badge">⚠ DEMO</span>
      </div>
    </nav>
  );
}
