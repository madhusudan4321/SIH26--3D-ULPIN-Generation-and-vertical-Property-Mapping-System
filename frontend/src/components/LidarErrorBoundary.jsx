import React from "react";

export default class LidarErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("3D VIEWER ERROR BOUNDARY CATCAH:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="lcv-canvas-error-fallback"
          style={{
            position: "absolute",
            inset: 0,
            background: "#0f172a",
            color: "#f87171",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px",
            zIndex: 100,
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "48px", marginBottom: "16px" }}>⚠️</div>
          <h3 style={{ fontSize: "20px", fontWeight: "700", marginBottom: "8px", color: "#f87171" }}>
            3D VIEWER ERROR
          </h3>
          <p style={{ fontSize: "14px", color: "#cbd5e1", maxWidth: "500px", marginBottom: "20px", fontFamily: "monospace" }}>
            {this.state.error?.message || "An unexpected rendering exception occurred."}
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: "8px 20px",
              background: "#38bdf8",
              color: "#0f172a",
              fontWeight: "600",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              fontSize: "14px",
            }}
          >
            Retry Viewer
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
