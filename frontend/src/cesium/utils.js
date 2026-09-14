/**
 * Cesium Utilities — Colors, CRS Config, Helpers
 *
 * CRS Configuration:
 * All spatial data uses EPSG:4326 (WGS84 lon/lat).
 * GeoJSON coordinate order: [longitude, latitude]
 */

import * as Cesium from "cesium";

// ─── CRS ────────────────────────────────────────────────────

export const SAMPLE_DATA_CRS = "EPSG:4326";

// ─── Camera Target ──────────────────────────────────────────

export const SAMPLE_CENTER = {
  lon: -123.2509,
  lat: 49.2632,
};

// ─── Color Palette ──────────────────────────────────────────

export const FLOOR_COLORS = [
  Cesium.Color.fromCssColorString("#10b981"), // Floor 1 — Emerald
  Cesium.Color.fromCssColorString("#06b6d4"), // Floor 2 — Cyan
  Cesium.Color.fromCssColorString("#3b82f6"), // Floor 3 — Blue
  Cesium.Color.fromCssColorString("#8b5cf6"), // Floor 4 — Violet
  Cesium.Color.fromCssColorString("#ec4899"), // Floor 5 — Pink
  Cesium.Color.fromCssColorString("#f59e0b"), // Floor 6 — Amber
];

export const PARCEL_COLOR = Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.25);
export const PARCEL_OUTLINE_COLOR = Cesium.Color.fromCssColorString("#f59e0b");
export const BUILDING_COLOR = Cesium.Color.fromCssColorString("#94a3b8").withAlpha(0.15);
export const BUILDING_OUTLINE_COLOR = Cesium.Color.fromCssColorString("#cbd5e1").withAlpha(0.6);
export const SELECTION_COLOR = Cesium.Color.fromCssColorString("#facc15").withAlpha(0.85);
export const UNDERGROUND_COLORS = {
  water_pipeline: Cesium.Color.fromCssColorString("#3b82f6"),
  sewer: Cesium.Color.fromCssColorString("#a855f7"),
  electricity_cable: Cesium.Color.fromCssColorString("#ef4444"),
};

// ─── Helpers ────────────────────────────────────────────────

export function getFloorColor(floorNumber, alpha = 0.7) {
  const idx = Math.abs(floorNumber - 1) % FLOOR_COLORS.length;
  return FLOOR_COLORS[idx].withAlpha(alpha);
}

export function getUnitColor(floorNumber, unitIndex = 0, propertyType = "", alpha = 0.75) {
  const floorHues = [0.42, 0.52, 0.60, 0.75, 0.90, 0.08, 0.15, 0.28];
  const baseHue = floorHues[Math.abs(floorNumber - 1) % floorHues.length];
  const hue = (baseHue + (unitIndex * 0.07)) % 1.0;

  let saturation = 0.75;
  let lightness = 0.50;

  const typeLower = (propertyType || "").toLowerCase();
  if (typeLower === "commercial") {
    saturation = 0.85;
    lightness = 0.55;
  } else if (typeLower === "residential") {
    saturation = 0.65;
    lightness = 0.60;
  }

  return Cesium.Color.fromHsl(hue, saturation, lightness, alpha);
}

/**
 * Convert a GeoJSON polygon / geometry / coordinate ring to a Cesium Cartesian3 array.
 * Strictly respects WGS84 GeoJSON coordinate order: [longitude, latitude].
 * Supports Polygon and MultiPolygon geometry objects.
 *
 * @param {Object|Array} geometryOrCoordinates
 * @returns {Array<Cesium.Cartesian3>} Array of Cesium Cartesian3 positions
 */
export function polygonToCartesian(geometryOrCoordinates) {
  if (!geometryOrCoordinates) return [];
  let ring = geometryOrCoordinates;

  // Handle GeoJSON Geometry or Feature object
  if (typeof geometryOrCoordinates === "object" && !Array.isArray(geometryOrCoordinates)) {
    const geom = geometryOrCoordinates.geometry || geometryOrCoordinates;
    if (geom.type === "Polygon" && Array.isArray(geom.coordinates)) {
      ring = geom.coordinates[0] || [];
    } else if (geom.type === "MultiPolygon" && Array.isArray(geom.coordinates)) {
      // Take exterior ring of first polygon component
      ring = geom.coordinates[0]?.[0] || [];
    } else if (geom.coordinates) {
      ring = geom.coordinates[0] || [];
    } else {
      return [];
    }
  }

  // Handle nested coordinate rings: [[[lon, lat], ...]]
  while (Array.isArray(ring) && ring.length > 0 && Array.isArray(ring[0]) && Array.isArray(ring[0][0])) {
    ring = ring[0];
  }

  if (!Array.isArray(ring)) return [];

  const positions = [];
  for (const pt of ring) {
    if (Array.isArray(pt) && pt.length >= 2) {
      const lon = Number(pt[0]); // Longitude is index 0
      const lat = Number(pt[1]); // Latitude is index 1
      if (!isNaN(lon) && !isNaN(lat) && lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90) {
        positions.push(Cesium.Cartesian3.fromDegrees(lon, lat));
      }
    } else if (typeof pt === "string") {
      const parts = pt.trim().split(/\s+/);
      if (parts.length >= 2) {
        const lon = Number(parts[0]);
        const lat = Number(parts[1]);
        if (!isNaN(lon) && !isNaN(lat) && lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90) {
          positions.push(Cesium.Cartesian3.fromDegrees(lon, lat));
        }
      }
    }
  }
  return positions;
}

export function getUndergroundColor(type) {
  return UNDERGROUND_COLORS[type] || Cesium.Color.GRAY;
}
