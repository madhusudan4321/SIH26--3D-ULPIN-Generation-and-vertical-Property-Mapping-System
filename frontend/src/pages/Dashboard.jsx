/**
 * Dashboard Page — Main Application Layout
 *
 * Layout: Navbar (top) + Sidebar (left) + CesiumViewer (center) + PropertyPanel (right)
 *
 * Manages:
 * - Backend health check on mount
 * - ConnectionError display when backend unavailable
 * - Modal flow for Add Building / Import Document
 * - Processing status display
 */

import { useState, useEffect, useCallback } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import CesiumViewer from "../cesium/CesiumViewer";
import PropertyPanel from "../components/PropertyPanel";
import ConnectionError from "../components/ConnectionError";
import AddBuildingModal from "../components/AddBuildingModal";
import DocumentUpload from "../components/DocumentUpload";
import DataReview from "../components/DataReview";
import ManualEntryForm from "../components/ManualEntryForm";
import ProcessingStatus from "../components/ProcessingStatus";
import { checkHealth, loadDemoData } from "../services/api";

export default function Dashboard() {
  const [backendStatus, setBackendStatus] = useState("checking"); // checking | connected | error
  const [backendError, setBackendError] = useState(null);
  const [useDemoData, setUseDemoData] = useState(false);

  // Modal state
  const [activeModal, setActiveModal] = useState(null); // null | addBuilding | upload | review | manual | status
  const [uploadResult, setUploadResult] = useState(null);
  const [processingResult, setProcessingResult] = useState(null);

  // Check backend health on mount
  const checkBackend = useCallback(async () => {
    setBackendStatus("checking");
    const result = await checkHealth();
    if (result.ok) {
      setBackendStatus("connected");
      setBackendError(null);
      setUseDemoData(false);
    } else {
      setBackendStatus("error");
      setBackendError(result.error);
    }
  }, []);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  const handleLoadDemo = () => {
    setUseDemoData(true);
    setBackendStatus("demo");
    setBackendError(null);
  };

  // Modal handlers
  const handleAddBuilding = () => setActiveModal("addBuilding");
  const handleImportDocument = () => setActiveModal("upload");

  const handleUploadComplete = (result) => {
    setUploadResult(result);
    setActiveModal("review");
  };

  const handleConfirmComplete = (result) => {
    setProcessingResult(result);
    setActiveModal("status");
  };

  const handleProcessingClose = () => {
    setActiveModal(null);
    setProcessingResult(null);
    setUploadResult(null);
    // Force CesiumViewer to reload (increment key)
    setRefreshKey((k) => k + 1);
  };

  const [refreshKey, setRefreshKey] = useState(0);

  // Show connection error if backend is unavailable and user hasn't chosen demo
  if (backendStatus === "error" && !useDemoData) {
    return (
      <div className="dashboard">
        <Navbar />
        <ConnectionError
          onRetry={checkBackend}
          onLoadDemo={handleLoadDemo}
          error={backendError}
        />
      </div>
    );
  }

  return (
    <div className="dashboard">
      <Navbar />
      <div className="dashboard-body">
        <Sidebar
          onAddBuilding={handleAddBuilding}
          onImportDocument={handleImportDocument}
          backendStatus={backendStatus === "connected" ? "connected" : "disconnected"}
          refreshKey={refreshKey}
        />
        <main className="dashboard-main">
          <CesiumViewer key={refreshKey} useDemoData={useDemoData} />
        </main>
        <PropertyPanel onDeleteBuildingSuccess={() => setRefreshKey((k) => k + 1)} />
      </div>

      {/* Modals */}
      {activeModal === "addBuilding" && (
        <AddBuildingModal
          onClose={() => setActiveModal(null)}
          onChooseUpload={() => setActiveModal("upload")}
          onChooseManual={() => setActiveModal("manual")}
        />
      )}

      {activeModal === "upload" && (
        <DocumentUpload
          onUploadComplete={handleUploadComplete}
          onBack={() => setActiveModal(null)}
        />
      )}

      {activeModal === "review" && uploadResult && (
        <DataReview
          datasetId={uploadResult.dataset_id}
          extractedData={uploadResult.extracted_data}
          onConfirm={handleConfirmComplete}
          onBack={() => setActiveModal("upload")}
        />
      )}

      {activeModal === "manual" && (
        <ManualEntryForm
          onComplete={handleConfirmComplete}
          onBack={() => setActiveModal(null)}
        />
      )}

      {activeModal === "status" && processingResult && (
        <ProcessingStatus
          result={processingResult}
          onClose={handleProcessingClose}
        />
      )}
    </div>
  );
}
