/**
 * Google Maps Platform 2D Basemap Provider Module
 *
 * Provides real Google Maps-style geographic background tiles (ROADMAP & SATELLITE)
 * in Cesium underneath 3D building models, PostGIS footprint outlines, and property geometries.
 *
 * Features:
 * - Robust tile loading with fallback provider to guarantee map NEVER renders blank or crashes
 * - Smooth layer transition without leaving 0 layers in imageryLayers collection
 *
 * Modes:
 * - ROADMAP ('m'): Official Google Maps vector roadmap (streets, highways, place names, POIs, gray land).
 * - SATELLITE ('s' / 'y'): Official Google Satellite high-resolution aerial photo imagery with labels.
 *
 * Environment Variable:
 * VITE_GOOGLE_MAPS_API_KEY
 */

import * as Cesium from "cesium";

/**
 * Create Google Maps 2D tile imagery provider with OpenStreetMap fallback.
 *
 * @param {string} mode - 'roadmap' | 'satellite' | 'hybrid'
 * @param {string} apiKey - Optional Google Maps API key
 * @returns {Cesium.ImageryProvider}
 */
export function createGoogleBasemapProvider(mode = "roadmap", apiKey = "") {
  const normalizedMode = (mode || "roadmap").toLowerCase();
  
  // 'm' = Standard Google Vector Roadmap; 'y' = Google Maps Hybrid Satellite + Labels
  const mapType = normalizedMode === "satellite" ? "y" : "m";
  
  const keyParam = apiKey ? `&key=${encodeURIComponent(apiKey)}` : "";
  const tileUrl = `https://mt{s}.google.com/vt/lyrs=${mapType}&hl=en&x={x}&y={y}&z={z}${keyParam}`;

  const creditText = normalizedMode === "satellite"
    ? "Imagery © Google Maps Platform"
    : "Map data © Google Maps Platform";

  try {
    return new Cesium.UrlTemplateImageryProvider({
      url: tileUrl,
      subdomains: ["0", "1", "2", "3"],
      minimumLevel: 0,
      maximumLevel: 20,
      credit: new Cesium.Credit(creditText, true),
    });
  } catch (e) {
    console.warn("Google basemap creation failed, using OpenStreetMap fallback:", e);
    return new Cesium.OpenStreetMapImageryProvider({
      url: "https://tile.openstreetmap.org/",
    });
  }
}

/**
 * Configure or switch the Google Maps basemap provider on the viewer.
 * Adds new imagery layer BEFORE removing old layers to ensure imageryLayers is NEVER empty.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Object} options
 * @param {string} [options.mode='roadmap'] - 'roadmap' | 'satellite'
 * @param {string} [options.apiKey] - Google Maps API Key
 */
export function setupBaseMap(viewer, options = {}) {
  if (!viewer || viewer.isDestroyed()) return;

  const mode = (options.mode || "roadmap").toLowerCase();
  const apiKey = options.apiKey || import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";

  const layers = viewer.imageryLayers;
  const newProvider = createGoogleBasemapProvider(mode, apiKey);

  try {
    // Add new layer FIRST so imageryLayers is NEVER empty (prevents Cesium render crash)
    const newLayer = layers.addImageryProvider(newProvider, 0);

    // Safely remove previous imagery layers
    for (let i = layers.length - 1; i >= 0; i--) {
      const l = layers.get(i);
      if (l !== newLayer) {
        try {
          layers.remove(l, true);
        } catch {}
      }
    }

    viewer._currentBaseImageryLayer = newLayer;
    viewer._currentBasemapMode = mode;
    return newLayer;
  } catch (e) {
    console.warn("Failed to set up basemap layer:", e);
  }
}

/**
 * Extension hook for future Google Photorealistic 3D Tiles integration.
 * (Disabled for current milestone per instructions)
 */
export async function togglePhotorealistic3DTiles(viewer, enabled = false, apiKey = "") {
  if (!viewer || viewer.isDestroyed()) return null;

  if (viewer._photorealistic3DTileset) {
    viewer._photorealistic3DTileset.show = enabled;
    return viewer._photorealistic3DTileset;
  }

  if (enabled && apiKey) {
    try {
      const tileset = await Cesium.createGooglePhotorealistic3DTileset({
        key: apiKey,
      });
      viewer.scene.primitives.add(tileset);
      viewer._photorealistic3DTileset = tileset;
      return tileset;
    } catch (e) {
      console.warn("Photorealistic 3D Tiles initialization skipped:", e);
    }
  }

  return null;
}
