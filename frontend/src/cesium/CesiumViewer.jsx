/**
 * CesiumViewer — Main 3D Viewer Component
 *
 * Responsibilities:
 * 1. Initialize Cesium Viewer with guaranteed Google Maps / OSM imagery provider
 * 2. Configure 100% unlocked, responsive 3D desktop camera controls (rotate, orbit, zoom, pan, tilt)
 * 3. Load 3D buildings, PostGIS ground footprint polygon highlights, and per-property unit volume geometries
 * 4. Georeferencing building models & footprints using relative ground height references
 * 5. Dynamically toggle Google Maps Roadmap vs Satellite mode without destroying scene or camera state
 * 6. Manage Building Shell mode (Transparent / Opaque / Hidden) & Floor Isolation / Exploded Floor View
 * 7. Manage layer visibility & selection highlight (building footprint highlight + property unit volume highlight)
 * 8. Handle unit/building entity click → selection, camera fly-to, and property panel details
 * 9. Provide interactive camera view navigation (Top View, 3D/Reset View, Compass N/S/E/W)
 */

import { useEffect, useRef, useCallback } from "react";
import * as Cesium from "cesium";
import { useSelection } from "../hooks/useSelection";
import { getParcels, getBuildings, getBuilding, getUndergroundAssets, loadDemoData } from "../services/api";
import { createParcelEntities, setParcelVisibility } from "./parcels";
import { createBuildingEntities, setBuildingVisibility, updateBuildingShell, highlightBuilding } from "./buildings";
import { createFloorEntities, setFloorVisibility, updateFloorEntities, highlightFloor } from "./floors";
import { createUndergroundEntities, setUndergroundVisibility } from "./underground";
import { createGoogleBasemapProvider, setupBaseMap, togglePhotorealistic3DTiles } from "./basemap";
import { SAMPLE_CENTER } from "./utils";

// Set Cesium Ion token if available
const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
if (ionToken && ionToken !== "your_cesium_ion_token_here") {
  Cesium.Ion.defaultAccessToken = ionToken;
}

export default function CesiumViewer({ useDemoData = false }) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  const entitiesRef = useRef({
    parcels: [],
    buildings: [],
    floors: [],
    underground: [],
  });
  const buildingsDataRef = useRef([]);
  const floorsDataRef = useRef([]);
  const initRef = useRef(false);

  const {
    selectedBuildingId,
    selectedPropertyId,
    basemapMode,
    flyToTarget,
    cameraCommand,
    shellMode,
    visibleFloors,
    isolatedFloorNumber,
    explodedView,
    explodeOffset,
    layerVisibility,
    selectProperty,
    selectBuilding,
    consumeFlyTo,
    consumeCameraCommand,
  } = useSelection();

  // ─── Load Entities ──────────────────────────────────────

  const loadEntities = useCallback(async (viewer) => {
    if (!viewer || viewer.isDestroyed()) return;

    let parcels = [];
    let buildings = [];
    let floors = [];
    let properties = [];
    let underground = [];

    if (useDemoData) {
      const demo = loadDemoData();
      parcels = demo.parcels;
      buildings = demo.buildings;
      floors = demo.floors;
      properties = demo.properties;
      underground = demo.underground;
    } else {
      try {
        const bSummaries = await getBuildings();
        if (bSummaries && bSummaries.length > 0) {
          for (const summary of bSummaries) {
            const bDetail = await getBuilding(summary.building_id);
            if (bDetail) {
              buildings.push(bDetail);
              if (bDetail.floors) floors.push(...bDetail.floors);
              if (bDetail.properties) properties.push(...bDetail.properties);
            }
          }
        }

        parcels = await getParcels().catch(() => []);
        underground = await getUndergroundAssets().catch(() => []);

        // If no DB buildings exist yet, show demo data
        if (buildings.length === 0) {
          const demo = loadDemoData();
          buildings = demo.buildings;
          floors = demo.floors;
          properties = demo.properties;
        }
      } catch (e) {
        console.warn("API load failed, using fallback demo data:", e);
        const demo = loadDemoData();
        buildings = demo.buildings;
        floors = demo.floors;
        properties = demo.properties;
        parcels = demo.parcels;
        underground = demo.underground;
      }
    }

    if (!viewer || viewer.isDestroyed()) return;

    buildingsDataRef.current = buildings;
    floorsDataRef.current = floors;

    entitiesRef.current.parcels = createParcelEntities(viewer, parcels);
    entitiesRef.current.buildings = createBuildingEntities(viewer, buildings);
    entitiesRef.current.floors = createFloorEntities(viewer, floors, properties, buildings);
    entitiesRef.current.underground = createUndergroundEntities(viewer, underground);

    updateBuildingShell(entitiesRef.current.buildings, shellMode);
    updateFloorEntities(entitiesRef.current.floors, {
      visibleFloors,
      isolatedFloorNumber,
      explodedView,
      explodeOffset,
    });

    setUndergroundVisibility(entitiesRef.current.underground, false);
  }, [useDemoData]);

  // ─── Initialize Viewer ──────────────────────────────────

  useEffect(() => {
    if (!containerRef.current || initRef.current) return;
    initRef.current = true;

    // Guaranteed initial basemap imagery provider (prevents 0-layer crash)
    const initialImageryProvider = createGoogleBasemapProvider(basemapMode);

    const viewer = new Cesium.Viewer(containerRef.current, {
      imageryProvider: initialImageryProvider,
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
      contextOptions: {
        webgl: {
          alpha: false,
          depth: true,
          stencil: false,
          antialias: true,
          premultipliedAlpha: true,
          preserveDrawingBuffer: true,
          failIfMajorPerformanceCaveat: false,
        },
      },
    });

    // Save viewer instance on window for console debugging
    window.cesiumViewer = viewer;

    // Handle render errors gracefully without crashing viewer
    if (viewer.scene && viewer.scene.renderError) {
      viewer.scene.renderError.addEventListener((scene, error) => {
        console.warn("Captured Cesium render error:", error);
      });
    }

    // Configure 100% unlocked 3D mouse camera controller
    const controller = viewer.scene.screenSpaceCameraController;
    controller.enableRotate = true;
    controller.enableZoom = true;
    controller.enableTranslate = true;
    controller.enableTilt = true;
    controller.enableLook = true;
    controller.minimumZoomDistance = 1.0;
    controller.maximumZoomDistance = 50000.0;
    controller.inertiaSpin = 0.8;
    controller.inertiaTranslate = 0.8;
    controller.inertiaZoom = 0.8;

    viewer.scene.globe.enableLighting = false;
    viewer.scene.fog.enabled = false;
    viewer.scene.globe.depthTestAgainstTerrain = true;
    viewer.scene.skyAtmosphere.show = true;

    // Configure real Google Maps Platform basemap provider (Roadmap / Satellite)
    setupBaseMap(viewer, { mode: basemapMode });

    // Extension hook for future Google Photorealistic 3D Tiles (disabled per milestone specs)
    togglePhotorealistic3DTiles(viewer, false);

    viewerRef.current = viewer;

    loadEntities(viewer);

    // Initial camera view focused on target region
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

    // Click handler — resolves unit entity (floor:*), footprint polygon (footprint:*), or building entity (building:*)
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((click) => {
      const pickedObjects = viewer.scene.drillPick(click.position);
      if (pickedObjects && pickedObjects.length > 0) {
        // 1. First check for 3D property unit volume
        const propertyPick = pickedObjects.find((p) => {
          const id = p.id?.id || "";
          return (
            id.startsWith("floor:") ||
            p.id?.properties?.entityType?.getValue() === "floor"
          );
        });

        if (propertyPick && propertyPick.id) {
          const entityId = propertyPick.id.id || "";
          const ulpin = entityId.replace("floor:", "");
          const bldId = propertyPick.id.properties?.building_id?.getValue();
          selectProperty(ulpin, bldId);
          return;
        }

        // 2. Next check for building or footprint entity
        const buildingPick = pickedObjects.find((p) => {
          const id = p.id?.id || "";
          return (
            id.startsWith("building:") ||
            id.startsWith("footprint:") ||
            p.id?.properties?.entityType?.getValue() === "building" ||
            p.id?.properties?.entityType?.getValue() === "footprint"
          );
        });

        if (buildingPick && buildingPick.id) {
          const entityId = buildingPick.id.id || "";
          const bldId = entityId.replace("building:", "").replace("footprint:", "");
          selectBuilding(bldId);
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      handler.destroy();
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
      }
      viewerRef.current = null;
      initRef.current = false;
      entitiesRef.current = {
        parcels: [],
        buildings: [],
        floors: [],
        underground: [],
      };
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Basemap Mode Toggle Effect ─────────────────────────

  useEffect(() => {
    if (viewerRef.current && !viewerRef.current.isDestroyed()) {
      setupBaseMap(viewerRef.current, { mode: basemapMode });
    }
  }, [basemapMode]);

  // ─── Layer Visibility ───────────────────────────────────

  useEffect(() => {
    setParcelVisibility(entitiesRef.current.parcels, layerVisibility.parcels);
    setBuildingVisibility(entitiesRef.current.buildings, layerVisibility.buildings);
    setFloorVisibility(entitiesRef.current.floors, layerVisibility.properties);
    setUndergroundVisibility(entitiesRef.current.underground, layerVisibility.underground);
  }, [layerVisibility]);

  // ─── Shell Mode Effect ──────────────────────────────────

  useEffect(() => {
    updateBuildingShell(entitiesRef.current.buildings, shellMode);
  }, [shellMode]);

  // ─── Floor Visibility & Exploded View Effect ───────────

  useEffect(() => {
    updateFloorEntities(entitiesRef.current.floors, {
      visibleFloors,
      isolatedFloorNumber,
      explodedView,
      explodeOffset,
    });
  }, [visibleFloors, isolatedFloorNumber, explodedView, explodeOffset]);

  // ─── Selection Highlight Effects ────────────────────────

  useEffect(() => {
    highlightFloor(entitiesRef.current.floors, selectedPropertyId);
  }, [selectedPropertyId]);

  useEffect(() => {
    highlightBuilding(entitiesRef.current.buildings, selectedBuildingId);
  }, [selectedBuildingId]);

  // ─── Fly-To Handling (Building Location or Property Unit) ─

  useEffect(() => {
    if (!flyToTarget || !viewerRef.current) return;

    const targetType = typeof flyToTarget === "object" ? flyToTarget.type : "property";
    const targetId = typeof flyToTarget === "object" ? flyToTarget.id : flyToTarget;

    if (targetType === "building") {
      const bData = buildingsDataRef.current.find((b) => b.building_id === targetId);
      if (bData && bData.latitude != null && bData.longitude != null) {
        const center = Cesium.Cartesian3.fromDegrees(bData.longitude, bData.latitude, (bData.height || 15.0) / 2.0);
        const boundingSphere = new Cesium.BoundingSphere(center, 40.0);
        viewerRef.current.camera.flyToBoundingSphere(boundingSphere, {
          duration: 1.5,
          offset: new Cesium.HeadingPitchRange(
            Cesium.Math.toRadians(30),
            Cesium.Math.toRadians(-25),
            75
          ),
        });
      }
    } else {
      const targetEntity = entitiesRef.current.floors.find(
        (e) => e.id === `floor:${targetId}` || e.properties?.sub_ulpin?.getValue() === targetId
      );

      if (targetEntity) {
        viewerRef.current.flyTo(targetEntity, {
          duration: 1.5,
          offset: new Cesium.HeadingPitchRange(
            Cesium.Math.toRadians(30),
            Cesium.Math.toRadians(-25),
            35
          ),
        });
      }
    }

    consumeFlyTo();
  }, [flyToTarget, consumeFlyTo]);

  // ─── Camera Navigation Controls Effect (Top, 3D, Reset, N/S/E/W) ───

  useEffect(() => {
    if (!cameraCommand || !viewerRef.current) return;

    const viewer = viewerRef.current;
    const mode = cameraCommand.mode;

    let targetLon = SAMPLE_CENTER.lon;
    let targetLat = SAMPLE_CENTER.lat;
    let targetHeight = 15.0;
    let isPropertyTarget = false;

    let activeBuildingId = selectedBuildingId;

    if (selectedPropertyId) {
      const pEntity = entitiesRef.current.floors.find(
        (e) => e.id === `floor:${selectedPropertyId}` || e.properties?.sub_ulpin?.getValue() === selectedPropertyId
      );
      if (pEntity) {
        isPropertyTarget = true;
        const bId = pEntity.properties?.building_id?.getValue();
        if (bId) activeBuildingId = bId;
      }
    }

    if (activeBuildingId) {
      const b = buildingsDataRef.current.find((b) => b.building_id === activeBuildingId);
      if (b && b.longitude != null && b.latitude != null) {
        targetLon = b.longitude;
        targetLat = b.latitude;
        targetHeight = b.height || 15.0;
      }
    } else if (buildingsDataRef.current.length > 0) {
      const b = buildingsDataRef.current[0];
      if (b && b.longitude != null && b.latitude != null) {
        targetLon = b.longitude;
        targetLat = b.latitude;
        targetHeight = b.height || 15.0;
      }
    }

    const defaultRange = isPropertyTarget ? 35 : 75;

    let heading = Cesium.Math.toRadians(30);
    let pitch = Cesium.Math.toRadians(-35);
    let range = defaultRange;

    switch (mode) {
      case "top":
        heading = 0;
        pitch = Cesium.Math.toRadians(-89.9);
        range = defaultRange;
        break;
      case "3d":
      case "reset":
        heading = Cesium.Math.toRadians(30);
        pitch = Cesium.Math.toRadians(-35);
        range = defaultRange;
        break;
      case "N":
        heading = 0;
        pitch = Cesium.Math.toRadians(-30);
        range = defaultRange;
        break;
      case "S":
        heading = Cesium.Math.toRadians(180);
        pitch = Cesium.Math.toRadians(-30);
        range = defaultRange;
        break;
      case "E":
        heading = Cesium.Math.toRadians(90);
        pitch = Cesium.Math.toRadians(-30);
        range = defaultRange;
        break;
      case "W":
        heading = Cesium.Math.toRadians(270);
        pitch = Cesium.Math.toRadians(-30);
        range = defaultRange;
        break;
      default:
        break;
    }

    const center = Cesium.Cartesian3.fromDegrees(targetLon, targetLat, targetHeight / 2.0);
    const boundingSphere = new Cesium.BoundingSphere(center, 40.0);

    viewer.camera.flyToBoundingSphere(boundingSphere, {
      duration: 1.0,
      offset: new Cesium.HeadingPitchRange(heading, pitch, range),
    });

    consumeCameraCommand();
  }, [cameraCommand, selectedBuildingId, selectedPropertyId, consumeCameraCommand]);

  return (
    <div
      ref={containerRef}
      className="cesium-container"
      style={{ width: "100%", height: "100%" }}
    />
  );
}
