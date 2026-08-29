/**
 * Selection Context — State Management
 *
 * Manages:
 * - selectedPropertyId (three_d_ulpin of selected property)
 * - flyToTarget (triggers camera fly-to when set)
 * - layerVisibility (show/hide Cesium entity groups)
 * - panelOpen (PropertyPanel visibility)
 */

import { createContext, useContext, useState, useCallback } from "react";

const SelectionContext = createContext(null);

const DEFAULT_LAYERS = {
  parcels: true,
  buildings: true,
  properties: true, // 3D floor volumes
  underground: false,
};

export function SelectionProvider({ children }) {
  const [selectedPropertyId, setSelectedPropertyId] = useState(null);
  const [flyToTarget, setFlyToTarget] = useState(null);
  const [layerVisibility, setLayerVisibility] = useState(DEFAULT_LAYERS);
  const [panelOpen, setPanelOpen] = useState(false);

  const selectProperty = useCallback((ulpin) => {
    setSelectedPropertyId(ulpin);
    setPanelOpen(true);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedPropertyId(null);
    setPanelOpen(false);
  }, []);

  const flyTo = useCallback(
    (ulpin) => {
      setFlyToTarget(ulpin);
      selectProperty(ulpin);
    },
    [selectProperty]
  );

  const consumeFlyTo = useCallback(() => {
    setFlyToTarget(null);
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
        selectedPropertyId,
        flyToTarget,
        layerVisibility,
        panelOpen,
        selectProperty,
        clearSelection,
        flyTo,
        consumeFlyTo,
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
