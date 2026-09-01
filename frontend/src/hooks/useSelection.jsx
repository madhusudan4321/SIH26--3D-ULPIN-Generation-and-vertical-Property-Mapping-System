/**
 * Selection Context — State Management
 *
 * Manages:
 * - selectedBuildingId (building_id of selected building)
 * - selectedPropertyId (ulpin / sub_ulpin of selected property unit)
 * - selectionType ("building" | "property" | null)
 * - flyToTarget ({ type: "building" | "property", id, latitude, longitude, height })
 * - cameraCommand ({ mode: "top" | "3d" | "reset" | "N" | "S" | "E" | "W", timestamp })
 * - shellMode ("transparent" | "opaque" | "hidden") — Building envelope visualization mode
 * - visibleFloors (Array of visible floor numbers)
 * - isolatedFloorNumber (Single isolated floor number or null)
 * - explodedView (Boolean — vertical floor displacement)
 * - explodeOffset (Number — displacement step in meters)
 * - layerVisibility (show/hide Cesium entity groups)
 * - panelOpen (Property/Building Details Panel visibility)
 */

import { createContext, useContext, useState, useCallback } from "react";

const SelectionContext = createContext(null);

const DEFAULT_LAYERS = {
  parcels: true,
  buildings: true,
  properties: true, // 3D property volume units
  underground: false,
};

const ALL_FLOORS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

export function SelectionProvider({ children }) {
  const [selectedBuildingId, setSelectedBuildingId] = useState(null);
  const [selectedPropertyId, setSelectedPropertyId] = useState(null);
  const [selectionType, setSelectionType] = useState(null); // "building" | "property" | null

  const [basemapMode, setBasemapMode] = useState("roadmap"); // "roadmap" | "satellite"
  const [flyToTarget, setFlyToTarget] = useState(null);
  const [cameraCommand, setCameraCommand] = useState(null);

  // Building Shell & Floor Controls
  const [shellMode, setShellMode] = useState("transparent"); // "transparent" | "opaque" | "hidden"
  const [visibleFloors, setVisibleFloors] = useState(ALL_FLOORS);
  const [isolatedFloorNumber, setIsolatedFloorNumber] = useState(null); // null or floor integer
  const [explodedView, setExplodedView] = useState(false);
  const [explodeOffset, setExplodeOffset] = useState(5.0); // meters per floor

  const [layerVisibility, setLayerVisibility] = useState(DEFAULT_LAYERS);
  const [panelOpen, setPanelOpen] = useState(false);

  const selectProperty = useCallback((ulpin, buildingId = null) => {
    setSelectedPropertyId(ulpin);
    if (buildingId) {
      setSelectedBuildingId(buildingId);
    }
    setSelectionType("property");
    setPanelOpen(true);
  }, []);

  const selectBuilding = useCallback((buildingId) => {
    setSelectedBuildingId(buildingId);
    setSelectedPropertyId(null);
    setSelectionType("building");
    setPanelOpen(true);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedPropertyId(null);
    setSelectedBuildingId(null);
    setSelectionType(null);
    setPanelOpen(false);
  }, []);

  const flyTo = useCallback(
    (ulpin) => {
      setFlyToTarget({ type: "property", id: ulpin });
      selectProperty(ulpin);
    },
    [selectProperty]
  );

  const flyToBuilding = useCallback(
    (buildingId, coords = {}) => {
      setFlyToTarget({
        type: "building",
        id: buildingId,
        latitude: coords.latitude,
        longitude: coords.longitude,
        height: coords.height,
      });
      selectBuilding(buildingId);
    },
    [selectBuilding]
  );

  const consumeFlyTo = useCallback(() => {
    setFlyToTarget(null);
  }, []);

  const triggerCameraView = useCallback((mode) => {
    setCameraCommand({ mode, timestamp: Date.now() });
  }, []);

  const consumeCameraCommand = useCallback(() => {
    setCameraCommand(null);
  }, []);

  const toggleFloorVisibility = useCallback((floorNum) => {
    setIsolatedFloorNumber(null);
    setVisibleFloors((prev) =>
      prev.includes(floorNum)
        ? prev.filter((f) => f !== floorNum)
        : [...prev, floorNum]
    );
  }, []);

  const isolateFloor = useCallback((floorNum) => {
    setIsolatedFloorNumber((prev) => (prev === floorNum ? null : floorNum));
  }, []);

  const showAllFloors = useCallback(() => {
    setIsolatedFloorNumber(null);
    setVisibleFloors(ALL_FLOORS);
  }, []);

  const toggleLayer = useCallback((layerName) => {
    setLayerVisibility((prev) => ({
      ...prev,
      [layerName]: !prev[layerName],
    }));
  }, []);

  return (
    <SelectionContext.Provider
      value={{
        selectedBuildingId,
        selectedPropertyId,
        selectionType,
        basemapMode,
        setBasemapMode,
        flyToTarget,
        cameraCommand,
        shellMode,
        setShellMode,
        visibleFloors,
        isolatedFloorNumber,
        explodedView,
        setExplodedView,
        explodeOffset,
        setExplodeOffset,
        toggleFloorVisibility,
        isolateFloor,
        showAllFloors,
        layerVisibility,
        panelOpen,
        selectProperty,
        selectBuilding,
        clearSelection,
        flyTo,
        flyToBuilding,
        consumeFlyTo,
        triggerCameraView,
        consumeCameraCommand,
        toggleLayer,
      }}
    >
      {children}
    </SelectionContext.Provider>
  );
}

export function useSelection() {
  const ctx = useContext(SelectionContext);
  if (!ctx) {
    throw new Error("useSelection must be used within SelectionProvider");
  }
  return ctx;
}
