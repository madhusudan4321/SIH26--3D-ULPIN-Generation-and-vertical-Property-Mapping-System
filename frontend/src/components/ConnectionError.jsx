/**
 * ConnectionError Component
 *
 * Displayed when the backend/database is unavailable.
 * Provides [Retry] and [Load Demo Data] buttons.
 * Demo data is NEVER loaded silently — user must explicitly choose.
 */

import { useState } from "react";

export default function ConnectionError({ onRetry, onLoadDemo, error }) {
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="connection-error-overlay">
      <div className="connection-error-card">
        <div className="connection-error-icon">⚠</div>
        <h2 className="connection-error-title">Backend / Database Unavailable</h2>
        <p className="connection-error-message">
          Unable to connect to the 3D ULPIN System API.
          {error && <span className="connection-error-detail">{error}</span>}
        </p>
        <p className="connection-error-hint">
          Make sure the FastAPI backend is running on port 8000 and PostgreSQL is accessible.
        </p>
        <div className="connection-error-actions">
          <button
            className="connection-btn connection-btn-primary"
            onClick={handleRetry}
            disabled={retrying}
          >
            {retrying ? "Retrying..." : "Retry Connection"}
          </button>
          <button
            className="connection-btn connection-btn-secondary"
            onClick={onLoadDemo}
          >
            Load Demo Data
          </button>
        </div>
        <p className="connection-error-footnote">
          Demo data is local sample data for testing only. When the backend is running,
          PostgreSQL/PostGIS is the single source of truth.
        </p>
      </div>
    </div>
  );
}
