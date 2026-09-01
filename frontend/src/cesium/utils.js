/**
 * Cesium Utilities — Colors, CRS Config, Helpers
 *
 * CRS Configuration:
 * M1: All sample data uses EPSG:4326 (WGS84 lon/lat).
 */

import * as Cesium from "cesium";

// ─── CRS ────────────────────────────────────────────────────

export const SAMPLE_DATA_CRS = "EPSG:4326";

// ─── Camera Target ──────────────────────────────────────────

// Center of sample parcel area (India Gate vicinity, New Delhi)
export const SAMPLE_CENTER = {
  lon: 77.23,
  lat: 28.6134,
};

// ─── Color Palette ──────────────────────────────────────────

// Floor colors — distinct per floor number for visual separation
export const FLOOR_COLORS = [
  Cesium.Color.fromCssColorString("#10b981"), // Floor 1 — Emerald
  Cesium.Color.fromCssColorString("#06b6d4"), // Floor 2 — Cyan
  Cesium.Color.fromCssColorString("#3b82f6"), // Floor 3 — Blue
  Cesium.Color.fromCssColorString("#8b5cf6"), // Floor 4 — Violet
  Cesium.Color.fromCssColorString("#ec4899"), // Floor 5 — Pink
  Cesium.Color.fromCssColorString("#f59e0b"), // Floor 6 — Amber
];

export const PARCEL_COLOR = Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.25); // Amber
export const PARCEL_OUTLINE_COLOR = Cesium.Color.fromCssColorString("#f59e0b"); // Amber
export const BUILDING_COLOR = Cesium.Color.fromCssColorString("#94a3b8").withAlpha(0.15); // Slate
export const BUILDING_OUTLINE_COLOR = Cesium.Color.fromCssColorString("#cbd5e1").withAlpha(0.6);
export const SELECTION_COLOR = Cesium.Color.fromCssColorString("#facc15").withAlpha(0.85); // Yellow highlight
export const UNDERGROUND_COLORS = {
  water_pipeline: Cesium.Color.fromCssColorString("#3b82f6"), // Blue
  sewer: Cesium.Color.fromCssColorString("#a855f7"),          // Purple
  electricity_cable: Cesium.Color.fromCssColorString("#ef4444"), // Red
};

// ─── Helpers ────────────────────────────────────────────────

/**
 * Get floor color by floor number (1-indexed).
 */
export function getFloorColor(floorNumber, alpha = 0.7) {
  const idx = Math.abs(floorNumber - 1) % FLOOR_COLORS.length;
  return FLOOR_COLORS[idx].withAlpha(alpha);
}

/**
 * Get distinct unit color for 3D property volume rendering.
 * Uses Cesium.Color.fromHsl(hue, saturation, lightness, alpha) to differentiate
 * adjacent units on the same floor visually.
 */
export function getUnitColor(floorNumber, unitIndex = 0, propertyType = "", alpha = 0.75) {
  // Base hues per floor number (0.0 to 1.0)
  const floorHues = [0.42, 0.52, 0.60, 0.75, 0.90, 0.08, 0.15, 0.28];
  const baseHue = floorHues[Math.abs(floorNumber - 1) % floorHues.length];

  // Shift hue slightly by unitIndex to make adjacent units on the same floor visually distinct
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
 * Convert a polygon (array of [lon, lat]) to Cesium Cartesian3 array.
 * Assumes EPSG:4326 input.
 */
export function polygonToCartesian(geometryOrCoordinates) {
  if (!geometryOrCoordinates) return [];
  let ring = geometryOrCoordinates;

  // Handle GeoJSON geometry dict: { type: "Polygon", coordinates: [[[lon, lat], ...]] }
  if (typeof geometryOrCoordinates === "object" && !Array.isArray(geometryOrCoordinates)) {
    if (geometryOrCoordinates.coordinates) {
      ring = geometryOrCoordinates.coordinates[0] || [];
    } else {
      return [];
    }
  }

  // Handle GeoJSON coordinates: [[[lon, lat], ...]] (nested 3D array)
  if (Array.isArray(ring) && ring.length > 0 && Array.isArray(ring[0]) && Array.isArray(ring[0][0])) {
    ring = ring[0];
  }

  if (!Array.isArray(ring)) return [];

  const positions = [];
  for (const pt of ring) {
    if (Array.isArray(pt) && pt.length >= 2) {
      const lon = Number(pt[0]);
      const lat = Number(pt[1]);
      if (!isNaN(lon) && !isNaN(lat)) {
        positions.push(Cesium.Cartesian3.fromDegrees(lon, lat));
      }
    } else if (typeof pt === "string") {
      const parts = pt.trim().split(/\s+/);
      if (parts.length >= 2) {
        const lon = Number(parts[0]);
        const lat = Number(parts[1]);
        if (!isNaN(lon) && !isNaN(lat)) {
          positions.push(Cesium.Cartesian3.fromDegrees(lon, lat));
        }
      }
    }
  }
  return positions;
}

/**
 * Get underground asset color by type.
 */
export function getUndergroundColor(type) {
  return UNDERGROUND_COLORS[type] || Cesium.Color.GRAY;
}
