/**
 * AddBuildingModal Component
 *
 * Choice modal: Import Document or Manual Entry.
 * Opens the appropriate workflow.
 */

export default function AddBuildingModal({ onClose, onChooseUpload, onChooseManual }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Building</h2>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>
        <p className="modal-subtitle">
          Choose how to add building data to the system.
        </p>
        <div className="modal-choices">
          <button className="modal-choice-card" onClick={onChooseUpload}>
            <span className="modal-choice-icon">📄</span>
            <h3>Import Document</h3>
            <p>Upload a PDF, CSV, JSON, or GeoJSON file containing building and property data.</p>
          </button>
          <button className="modal-choice-card" onClick={onChooseManual}>
            <span className="modal-choice-icon">✏️</span>
            <h3>Manual Entry</h3>
            <p>Enter building, floor, and property information manually using a form.</p>
          </button>
        </div>
      </div>
    </div>
  );
}
