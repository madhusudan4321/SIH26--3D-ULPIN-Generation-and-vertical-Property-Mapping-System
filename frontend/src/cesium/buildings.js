/**
 * Building Entity Module
 *
 * Creates Cesium extruded polygon entities for buildings.
 * Buildings are displayed as translucent wireframe-style volumes
 * using absolute heights based on sampled terrain elevation.
 */

import * as Cesium from "cesium";
import { BUILDING_COLOR, BUILDING_OUTLINE_COLOR, polygonToCartesian } from "./utils";

/**
 * Create building entities on the viewer.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} buildings - Array of building records from api.js
 * @param {number} terrainHeight - Actual terrain height at sample location
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createBuildingEntities(viewer, buildings, terrainHeight) {
  const entities = [];

  for (const building of buildings) {
    const positions = polygonToCartesian(building.footprint);
    // ground_elevation and roof_elevation are relative to ground (0-12m)
    const baseHeight = terrainHeight + building.ground_elevation;
    const topHeight = terrainHeight + building.roof_elevation;

    const entity = viewer.entities.add({
      id: `building:${building.building_id}`,
      name: `Building ${building.building_id}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: BUILDING_COLOR,
        outline: true,
        outlineColor: BUILDING_OUTLINE_COLOR,
        outlineWidth: 1,
        height: baseHeight,
        extrudedHeight: topHeight,
      },
      properties: {
        entityType: "building",
        building_id: building.building_id,
        parcel_id: building.parcel_id,
        source: building.source,
      },
    });

    entities.push(entity);
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
