/**
 * CesiumViewer — Main 3D Viewer Component
 *
 * Responsibilities:
 * 1. Initialize Cesium Viewer with terrain
 * 2. Sample terrain height at building location
 * 3. Load entities via modular create functions using real terrain heights
 * 4. Manage layer visibility from selection context
 * 5. Handle entity click → selection
 * 6. Handle fly-to from search/selection
 * 7. Highlight selected floor volume
 *
 * NOTE on React StrictMode:
 * React 18/19 StrictMode double-mounts components in dev mode.
 * The cleanup function destroys the Cesium viewer, so we must
 * reset initRef to allow re-initialization on the second mount.
 */

import { useEffect, useRef, useCallback } from "react";
import * as Cesium from "cesium";
import { useSelection } from "../hooks/useSelection";
import { getParcels, getBuildings, getFloors, getProperties, getUndergroundAssets } from "../services/api";
import { createParcelEntities, setParcelVisibility } from "./parcels";
import { createBuildingEntities, setBuildingVisibility } from "./buildings";
import { createFloorEntities, setFloorVisibility, highlightFloor } from "./floors";
import { createUndergroundEntities, setUndergroundVisibility } from "./underground";
import { SAMPLE_CENTER } from "./utils";

// Set Cesium Ion token if available
const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
if (ionToken && ionToken !== "your_cesium_ion_token_here") {
  Cesium.Ion.defaultAccessToken = ionToken;
}

export default function CesiumViewer() {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  const entitiesRef = useRef({
    parcels: [],
    buildings: [],
    floors: [],
    underground: [],
  });
  const floorsDataRef = useRef([]);
  const initRef = useRef(false);

  const {
    selectedPropertyId,
    flyToTarget,
    layerVisibility,
    selectProperty,
    consumeFlyTo,
  } = useSelection();

  // ─── Load Entities ──────────────────────────────────────

  const loadEntities = useCallback(async (viewer) => {
    if (!viewer || viewer.isDestroyed()) return;

    const [parcels, buildings, floors, properties, underground] =
      await Promise.all([
        getParcels(),
        getBuildings(),
        getFloors(),
        getProperties(),
        getUndergroundAssets(),
      ]);

    if (!viewer || viewer.isDestroyed()) return;

    // Sample actual terrain height at the building center
    let terrainHeight = 216.0; // fallback for New Delhi area
    try {
      const center = Cesium.Cartographic.fromDegrees(
        SAMPLE_CENTER.lon,
        SAMPLE_CENTER.lat
      );
      const terrainProvider = viewer.terrainProvider;
      // Use readyPromise for CesiumJS 1.144+ compatibility (terrainProvider.ready is deprecated)
      if (terrainProvider) {
        try {
          if (terrainProvider.readyPromise) {
            await terrainProvider.readyPromise;
          }
        } catch {
          // readyPromise may not exist on all providers; that's OK
        }
        if (!viewer || viewer.isDestroyed()) return;
        const samples = await Cesium.sampleTerrainMostDetailed(
          terrainProvider,
          [center]
        );
        if (samples && samples[0] && samples[0].height !== undefined) {
          terrainHeight = samples[0].height;
        }
      }
    } catch (e) {
      console.warn("Terrain sampling failed, using fallback height:", e);
    }

    if (!viewer || viewer.isDestroyed()) return;

    console.log("Terrain height at sample location:", terrainHeight);

    floorsDataRef.current = floors;

    entitiesRef.current.parcels = createParcelEntities(viewer, parcels, terrainHeight);
    entitiesRef.current.buildings = createBuildingEntities(viewer, buildings, terrainHeight);
    entitiesRef.current.floors = createFloorEntities(viewer, floors, properties, buildings, terrainHeight);
    entitiesRef.current.underground = createUndergroundEntities(viewer, underground, terrainHeight);

    // Underground hidden by default
    setUndergroundVisibility(entitiesRef.current.underground, false);
  }, []);

  // ─── Initialize Viewer ──────────────────────────────────
  //
  // Dependency array is intentionally empty []:
  // - The Cesium Viewer is an imperative, stateful object that must only
  //   be created once per mount cycle. Including deps like loadEntities or
  //   selectProperty would cause the viewer to be destroyed and recreated
  //   on every state change, losing all entities and camera state.
  // - selectProperty is stable (useCallback with no deps) so it won't
  //   cause stale closure issues.

  useEffect(() => {
    if (!containerRef.current || initRef.current) return;
    initRef.current = true;

    const viewer = new Cesium.Viewer(containerRef.current, {
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      vrButton: false,
      selectionIndicator: true,
      infoBox: false,
      creditContainer: document.createElement("div"),
    });

    // Scene settings
    viewer.scene.globe.enableLighting = false;
    viewer.scene.fog.enabled = false;
    viewer.scene.globe.depthTestAgainstTerrain = true;
    viewer.scene.skyAtmosphere.show = true;

    viewerRef.current = viewer;

    // Load entities (will sample terrain first)
    loadEntities(viewer);

    // Fly camera to sample area
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        SAMPLE_CENTER.lon - 0.001,
        SAMPLE_CENTER.lat - 0.001,
        350
      ),
      orientation: {
        heading: Cesium.Math.toRadians(30),
        pitch: Cesium.Math.toRadians(-30),
        roll: 0,
      },
      duration: 2.0,
    });

    // Click handler
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((click) => {
      const picked = viewer.scene.pick(click.position);
      if (Cesium.defined(picked) && picked.id) {
        const entityId = picked.id.id || "";
        if (entityId.startsWith("floor:")) {
          const ulpin = entityId.replace("floor:", "");
          selectProperty(ulpin);
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      handler.destroy();
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
      }
      viewerRef.current = null;
      // Reset initRef so viewer can re-initialize after React StrictMode
      // cleanup-and-remount cycle in development mode
      initRef.current = false;
      // Clear entity refs since viewer is destroyed
      entitiesRef.current = {
        parcels: [],
        buildings: [],
        floors: [],
        underground: [],
      };
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Layer Visibility ───────────────────────────────────

  useEffect(() => {
    setParcelVisibility(entitiesRef.current.parcels, layerVisibility.parcels);
    setBuildingVisibility(entitiesRef.current.buildings, layerVisibility.buildings);
    setFloorVisibility(entitiesRef.current.floors, layerVisibility.properties);
    setUndergroundVisibility(entitiesRef.current.underground, layerVisibility.underground);
  }, [layerVisibility]);

  // ─── Selection Highlight ────────────────────────────────

  useEffect(() => {
    highlightFloor(
      entitiesRef.current.floors,
      selectedPropertyId,
      floorsDataRef.current
    );
  }, [selectedPropertyId]);

  // ─── Fly-To ─────────────────────────────────────────────

  useEffect(() => {
    if (!flyToTarget || !viewerRef.current) return;

    const targetEntity = entitiesRef.current.floors.find(
      (e) => e.id === `floor:${flyToTarget}`
    );

    if (targetEntity) {
      viewerRef.current.flyTo(targetEntity, {
        duration: 1.5,
        offset: new Cesium.HeadingPitchRange(
          Cesium.Math.toRadians(30),
          Cesium.Math.toRadians(-30),
          150
        ),
      });
    }

    consumeFlyTo();
  }, [flyToTarget, consumeFlyTo]);

  return (
    <div
      ref={containerRef}
      className="cesium-container"
      style={{ width: "100%", height: "100%" }}
    />
  );
}
