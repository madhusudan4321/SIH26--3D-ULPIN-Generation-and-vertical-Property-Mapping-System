/**
 * Building Entity Module
 *
 * Creates Cesium 3D building envelope entities and PostGIS footprint highlight polygons.
 * Positioned using WGS84 geographic coordinates and relative ground heights.
 */

import * as Cesium from "cesium";
import { BUILDING_OUTLINE_COLOR, polygonToCartesian } from "./utils";

/**
 * Create building 3D volume and PostGIS ground footprint entities on the viewer.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} buildings - Array of building records from API or sample data
 * @returns {Array<Cesium.Entity>} Created entities (envelope + ground footprint)
 */
export function createBuildingEntities(viewer, buildings) {
  const entities = [];

  for (const building of buildings) {
    const footprintGeom = building.footprint_geojson || building.footprint;
    if (!footprintGeom) continue;

    const positions = polygonToCartesian(footprintGeom);
    if (!positions || positions.length < 3) continue;

    const groundElev = building.ground_elevation || 0.0;
    const height = building.height || building.roof_elevation || 18.0;

    // 1. PostGIS Ground Footprint Polygon Highlight Entity
    const footprintEntity = viewer.entities.add({
      id: `footprint:${building.building_id}`,
      name: `Footprint ${building.name || building.building_id}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: Cesium.Color.fromCssColorString("#38bdf8").withAlpha(0.15),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#38bdf8"),
        outlineWidth: 2,
        height: groundElev + 0.1,
        heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
      },
      properties: {
        entityType: "footprint",
        building_id: building.building_id,
        name: building.name,
      },
    });

    // 2. 3D Building Envelope Volume Entity
    const envelopeEntity = viewer.entities.add({
      id: `building:${building.building_id}`,
      name: `Building ${building.name || building.building_id}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: Cesium.Color.SLATEGRAY.withAlpha(0.04),
        outline: true,
        outlineColor: BUILDING_OUTLINE_COLOR,
        outlineWidth: 1,
        height: groundElev,
        extrudedHeight: groundElev + height,
        heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
        extrudedHeightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
      },
      properties: {
        entityType: "building",
        building_id: building.building_id,
        parcel_id: building.parcel_id,
        source: building.source,
      },
    });

    entities.push(footprintEntity, envelopeEntity);
  }

  return entities;
}

/**
 * Set visibility for all building entities.
 */
export function setBuildingVisibility(entities, visible) {
  for (const entity of entities) {
    entity.show = visible;
  }
}

/**
 * Update Building Shell Visualization Mode (Opaque vs Transparent vs Hidden).
 */
export function updateBuildingShell(entities, shellMode = "transparent") {
  for (const entity of entities) {
    const type = entity.properties?.entityType?.getValue();
    if (type === "building") {
      if (shellMode === "hidden") {
        entity.show = false;
      } else if (shellMode === "opaque") {
        entity.show = true;
        entity.polygon.material = Cesium.Color.SLATEGRAY.withAlpha(0.65);
      } else {
        // transparent default
        entity.show = true;
        entity.polygon.material = Cesium.Color.SLATEGRAY.withAlpha(0.04);
      }
    }
  }
}

/**
 * Highlight PostGIS footprint polygon and building envelope when building is selected.
 *
 * @param {Array<Cesium.Entity>} entities
 * @param {string} selectedBuildingId
 */
export function highlightBuilding(entities, selectedBuildingId) {
  for (const entity of entities) {
    const bId = entity.properties?.building_id?.getValue();
    const type = entity.properties?.entityType?.getValue();

    const isSelected = selectedBuildingId && bId === selectedBuildingId;

    if (type === "footprint") {
      if (isSelected) {
        entity.polygon.material = Cesium.Color.fromCssColorString("#facc15").withAlpha(0.35);
        entity.polygon.outlineColor = Cesium.Color.YELLOW;
        entity.polygon.outlineWidth = 4;
      } else {
        entity.polygon.material = Cesium.Color.fromCssColorString("#38bdf8").withAlpha(0.15);
        entity.polygon.outlineColor = Cesium.Color.fromCssColorString("#38bdf8");
        entity.polygon.outlineWidth = 2;
      }
    } else if (type === "building") {
      if (isSelected) {
        entity.polygon.outlineColor = Cesium.Color.YELLOW;
        entity.polygon.outlineWidth = 2;
      } else {
        entity.polygon.outlineColor = BUILDING_OUTLINE_COLOR;
        entity.polygon.outlineWidth = 1;
      }
    }
  }
}
