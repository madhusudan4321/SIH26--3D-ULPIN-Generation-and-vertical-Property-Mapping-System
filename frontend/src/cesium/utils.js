/**
 * Cesium Utilities — Colors, CRS Config, Helpers
 *
 * CRS Configuration:
 * M1: All sample data uses EPSG:4326 (WGS84 lon/lat).
 * Future: This module will be extended with CRS detection
 * and transformation utilities (e.g., proj4js) when integrating
 * LiDAR, cadastral GIS, and drone data with varying CRSs.
 *
 * IMPORTANT: Do NOT assume LiDAR X/Y values are lat/lon.
 * CRS metadata determines coordinate interpretation.
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
  Cesium.Color.fromCssColorString("#ec4899"), // Floor 5 — Pink (future)
  Cesium.Color.fromCssColorString("#f59e0b"), // Floor 6 — Amber (future)
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
 * Falls back to cycling through available colors.
 */
export function getFloorColor(floorNumber, alpha = 0.7) {
  const idx = (floorNumber - 1) % FLOOR_COLORS.length;
  return FLOOR_COLORS[idx].withAlpha(alpha);
}

/**
 * Convert a polygon (array of [lon, lat]) to Cesium Cartesian3 array.
 * Assumes EPSG:4326 input.
 */
export function polygonToCartesian(coordinates) {
  const positions = [];
  for (const [lon, lat] of coordinates) {
    positions.push(Cesium.Cartesian3.fromDegrees(lon, lat));
  }
  return positions;
}

/**
 * Get underground asset color by type.
 */
export function getUndergroundColor(type) {
  return UNDERGROUND_COLORS[type] || Cesium.Color.GRAY;
}
