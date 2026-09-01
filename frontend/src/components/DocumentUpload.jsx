/**
 * DocumentUpload Component
 *
 * File upload interface for PDF/CSV/JSON/GeoJSON.
 * Shows upload progress, then transitions to DataReview on success.
 */

import { useState, useRef } from "react";
import { uploadDocument } from "../services/api";

const ACCEPTED_TYPES = ".pdf,.csv,.json,.geojson";

export default function DocumentUpload({ onUploadComplete, onBack }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setError(null);

    try {
      const result = await uploadDocument(file);
      onUploadComplete(result);
    } catch (e) {
      setError(e.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="modal-overlay" onClick={onBack}>
      <div className="modal-card modal-card-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <button className="modal-back-btn" onClick={onBack}>← Back</button>
          <h2>Import Document</h2>
          <button className="modal-close-btn" onClick={onBack}>✕</button>
        </div>

        <div
          className={`upload-dropzone ${dragOver ? "upload-dropzone-active" : ""} ${uploading ? "upload-dropzone-disabled" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
        >
          {uploading ? (
            <div className="upload-progress">
              <div className="upload-spinner" />
              <p>Parsing document...</p>
            </div>
          ) : (
            <>
              <span className="upload-icon">📁</span>
              <p className="upload-text">
                Drag & drop a file here, or <span className="upload-link">browse</span>
              </p>
              <p className="upload-hint">Supported: PDF, CSV, JSON, GeoJSON</p>
            </>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            style={{ display: "none" }}
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>

        {error && (
          <div className="upload-error">
            <strong>Error:</strong> {error}
          </div>
        )}
      </div>
    </div>
  );
}
