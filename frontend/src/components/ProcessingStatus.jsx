/**
 * ProcessingStatus Component
 *
 * Displays processing result after successful confirm/manual entry.
 * Shows summary of created records.
 */

export default function ProcessingStatus({ result, onClose }) {
  const summary = result?.summary || {};

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Processing Complete</h2>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="processing-success-icon">✓</div>

        <div className="processing-summary">
          <h3>Building Created Successfully</h3>
          <div className="review-summary">
            <div className="review-stat">
              <span className="review-stat-value">{summary.building_id || "—"}</span>
              <span className="review-stat-label">Building ID</span>
            </div>
            <div className="review-stat">
              <span className="review-stat-value">{summary.parcel_id || "—"}</span>
              <span className="review-stat-label">Parcel ID</span>
            </div>
            <div className="review-stat">
              <span className="review-stat-value">{summary.floors || 0}</span>
              <span className="review-stat-label">Floors</span>
            </div>
            <div className="review-stat">
              <span className="review-stat-value">{summary.properties || 0}</span>
              <span className="review-stat-label">Properties</span>
            </div>
            <div className="review-stat">
              <span className="review-stat-value">{summary.ulpins || 0}</span>
              <span className="review-stat-label">ULPINs</span>
            </div>
            <div className="review-stat">
              <span className="review-stat-value">{summary.ror_links || 0}</span>
              <span className="review-stat-label">RoR Links</span>
            </div>
          </div>
          <p className="processing-note">
            The building is now stored in PostgreSQL/PostGIS and can be viewed on the map.
          </p>
        </div>

        <div className="review-actions">
          <button className="connection-btn connection-btn-primary" onClick={onClose}>
            Close & Refresh Map
          </button>
        </div>
      </div>
    </div>
  );
}
