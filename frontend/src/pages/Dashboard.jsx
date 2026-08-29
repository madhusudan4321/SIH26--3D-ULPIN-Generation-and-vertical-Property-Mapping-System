/**
 * Dashboard Page — Main Application Layout
 *
 * Layout: Navbar (top) + Sidebar (left) + CesiumViewer (center) + PropertyPanel (right)
 */

import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import CesiumViewer from "../cesium/CesiumViewer";
import PropertyPanel from "../components/PropertyPanel";

export default function Dashboard() {
  return (
    <div className="dashboard">
      <Navbar />
      <div className="dashboard-body">
        <Sidebar />
        <main className="dashboard-main">
          <CesiumViewer />
        </main>
        <PropertyPanel />
      </div>
    </div>
  );
}
