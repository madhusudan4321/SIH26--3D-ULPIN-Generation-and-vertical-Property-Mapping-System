/**
 * Google Maps Platform 2D Basemap Provider Module
 *
 * Provides real Google Maps-style geographic background tiles (ROADMAP & SATELLITE)
 * in Cesium underneath 3D building models, PostGIS footprint outlines, and property geometries.
 *
 * Features:
 * - Robust tile loading with fallback provider to guarantee map NEVER renders blank or crashes
 * - Smooth layer transition without leaving 0 layers in imageryLayers collection
 * - Surfacing provider errors and status updates (ROADMAP, SATELLITE, FALLBACK, ERROR)
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
 * Fallback provider creation chain:
 * 1. OpenStreetMap Imagery Provider
 * 2. TileMapService or SingleTileImageryProvider neutral globe
 */
export function createFallbackBasemapProvider() {
  try {
    return new Cesium.OpenStreetMapImageryProvider({
      url: "https://tile.openstreetmap.org/",
      maximumLevel: 19,
    });
  } catch (e) {
    console.warn("OSM fallback creation failed, using neutral single tile provider:", e);
    // Create a 1x1 neutral gray canvas data URL as absolute fallback
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(0, 0, 1, 1);
    }
    return new Cesium.SingleTileImageryProvider({
      url: canvas.toDataURL(),
      rectangle: Cesium.Rectangle.MAX_VALUE,
    });
  }
}

/**
 * Create Google Maps 2D tile imagery provider with tile error listener.
 *
 * @param {string} mode - 'roadmap' | 'satellite' | 'hybrid'
 * @param {string} apiKey - Optional Google Maps API key
 * @param {Function} [onError] - Tile error callback
 * @returns {Cesium.ImageryProvider}
 */
export function createGoogleBasemapProvider(mode = "roadmap", apiKey = "", onError = null) {
  const normalizedMode = (mode || "roadmap").toLowerCase();
  
  // 'm' = Standard Google Vector Roadmap; 'y' = Google Maps Hybrid Satellite + Labels
  const mapType = normalizedMode === "satellite" ? "y" : "m";
  
  const keyParam = apiKey ? `&key=${encodeURIComponent(apiKey)}` : "";
  const tileUrl = `https://mt{s}.google.com/vt/lyrs=${mapType}&hl=en&x={x}&y={y}&z={z}${keyParam}`;

  const creditText = normalizedMode === "satellite"
    ? "Imagery © Google Maps Platform"
    : "Map data © Google Maps Platform";

  try {
    const provider = new Cesium.UrlTemplateImageryProvider({
      url: tileUrl,
      subdomains: ["0", "1", "2", "3"],
      minimumLevel: 0,
      maximumLevel: 20,
      credit: new Cesium.Credit(creditText, true),
    });

    if (onError && provider.errorEvent) {
      let errCount = 0;
      provider.errorEvent.addEventListener((err) => {
        errCount++;
        if (errCount >= 2) {
          console.warn(`Google ${normalizedMode} basemap tile errors encountered (${errCount}). Switching to fallback.`);
          onError(err);
        }
      });
    }

    return provider;
  } catch (e) {
    console.warn("Google basemap creation failed, using fallback:", e);
    if (onError) onError(e);
    return createFallbackBasemapProvider();
  }
}

/**
 * Configure or switch the basemap provider on the viewer.
 * Adds new imagery layer BEFORE removing old layers to ensure imageryLayers is NEVER empty.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Object} options
 * @param {string} [options.mode='roadmap'] - 'roadmap' | 'satellite'
 * @param {string} [options.apiKey] - Google Maps API Key
 * @param {Function} [options.onStatusChange] - Status callback ('ROADMAP'|'SATELLITE'|'FALLBACK'|'ERROR')
 */
export function setupBaseMap(viewer, options = {}) {
  if (!viewer || viewer.isDestroyed()) return;

  const mode = (options.mode || "roadmap").toLowerCase();
  const apiKey = options.apiKey || import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";
  const onStatusChange = options.onStatusChange || null;

  // Don't skip if we previously failed or if mode changed
  if (viewer._currentBasemapMode === mode && viewer._currentBaseImageryLayer && viewer._basemapStatus === mode.toUpperCase()) {
    return viewer._currentBaseImageryLayer;
  }

  const layers = viewer.imageryLayers;
  const updateStatus = (status) => {
    viewer._basemapStatus = status;
    if (onStatusChange) onStatusChange(status);
  };

  let fallbackTriggered = false;

  const handleGoogleTileError = () => {
    if (fallbackTriggered || !viewer || viewer.isDestroyed()) return;
    fallbackTriggered = true;
    console.warn(`Google basemap mode '${mode}' tiles failed to load. Applying fallback provider.`);
    
    try {
      const fallbackProvider = createFallbackBasemapProvider();
      const fallbackLayer = layers.addImageryProvider(fallbackProvider, 0);

      for (let i = layers.length - 1; i >= 0; i--) {
        const l = layers.get(i);
        if (l && l !== fallbackLayer) {
          try {
            l.show = false;
            layers.remove(l, false);
          } catch {}
        }
      }
      viewer._currentBaseImageryLayer = fallbackLayer;
      updateStatus("FALLBACK");
    } catch (err) {
      console.error("Critical: Fallback basemap setup failed:", err);
      updateStatus("ERROR");
    }
  };

  try {
    const googleProvider = createGoogleBasemapProvider(mode, apiKey, handleGoogleTileError);
    const newLayer = layers.addImageryProvider(googleProvider, 0);

    // Safely remove previous imagery layers
    for (let i = layers.length - 1; i >= 0; i--) {
      const l = layers.get(i);
      if (l && l !== newLayer) {
        try {
          l.show = false;
          layers.remove(l, false);
        } catch {}
      }
    }

    viewer._currentBaseImageryLayer = newLayer;
    viewer._currentBasemapMode = mode;
    updateStatus(mode.toUpperCase());
    return newLayer;
  } catch (e) {
    console.warn("Failed to set up Google basemap layer, attempting fallback:", e);
    handleGoogleTileError();
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

