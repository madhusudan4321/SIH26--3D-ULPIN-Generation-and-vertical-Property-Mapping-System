/**
 * GeometryBadge Component
 *
 * Displays geometry provenance indicator.
 * Green badge for real source geometry, amber warning for synthetic/approximate.
 */

const GEOMETRY_LABELS = {
  geojson: { label: "SOURCE GEOMETRY — GeoJSON Polygon", type: "real", icon: "✅" },
  uploaded_geojson: { label: "SOURCE GEOMETRY — GeoJSON Polygon", type: "real", icon: "✅" },
  floorplan: { label: "SOURCE GEOMETRY — Floor Plan Derived", type: "real", icon: "✅" },
  floor_plan: { label: "SOURCE GEOMETRY — Floor Plan Derived", type: "real", icon: "✅" },
  cad: { label: "SOURCE GEOMETRY — CAD Drawing", type: "real", icon: "✅" },
  bim: { label: "SOURCE GEOMETRY — BIM Model", type: "real", icon: "✅" },
  photogrammetry: { label: "SOURCE GEOMETRY — 3D Photogrammetry", type: "real", icon: "✅" },
  lidar: { label: "SOURCE GEOMETRY — LiDAR Scan", type: "real", icon: "✅" },
  manual: { label: "SOURCE GEOMETRY — Surveyed Boundary", type: "real", icon: "✅" },
  building_footprint: { label: "APPROXIMATE GEOMETRY — Building Envelope", type: "approximate", icon: "⚠" },
  synthetic_subdivision: { label: "APPROXIMATE GEOMETRY — Synthetic Subdivision", type: "approximate", icon: "⚠" },
};

export default function GeometryBadge({ geometrySource, geometryAvailable }) {
  if (!geometryAvailable && !geometrySource) {
    return (
      <span className="geometry-badge geometry-badge-unavailable">
        ○ Geometry Unavailable
      </span>
    );
  }

  const key = (geometrySource || "").toLowerCase();
  const info = GEOMETRY_LABELS[key] || {
    label: geometrySource ? `SOURCE GEOMETRY — ${geometrySource}` : "Unknown Geometry",
    type: key.includes("synthetic") || key.includes("approx") ? "approximate" : "real",
    icon: key.includes("synthetic") || key.includes("approx") ? "⚠" : "✅",
  };

  const className =
    info.type === "real"
      ? "geometry-badge geometry-badge-real"
      : info.type === "approximate"
      ? "geometry-badge geometry-badge-approximate"
      : "geometry-badge geometry-badge-unknown";

  return (
    <span className={className}>
      {info.icon} {info.label}
    </span>
  );
}
