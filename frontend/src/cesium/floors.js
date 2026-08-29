/**
 * Floor Entity Module
 *
 * Creates individual extruded floor volumes in Cesium.
 * Each floor is a distinct selectable entity with its own color.
 * Uses absolute heights based on sampled terrain elevation.
 *
 * Relationship: Each floor may contain multiple properties.
 * Creates one entity per property for individual selection.
 */

import * as Cesium from "cesium";
import { getFloorColor, SELECTION_COLOR, polygonToCartesian } from "./utils";

/**
 * Create floor/property volume entities on the viewer.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} floors - Floor records from api.js
 * @param {Array} properties - Property records from api.js
 * @param {Array} buildings - Building records (for footprint lookup)
 * @param {number} terrainHeight - Actual terrain height at sample location
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createFloorEntities(viewer, floors, properties, buildings, terrainHeight) {
  const entities = [];

  // Build a footprint lookup by building_id
  const footprintMap = {};
  for (const b of buildings) {
    footprintMap[b.building_id] = b.footprint;
  }

  // Create one entity per property (supports multiple properties per floor)
  for (const property of properties) {
    const floor = floors.find((f) => f.floor_id === property.floor_id);
    if (!floor) continue;

    const footprint = footprintMap[property.building_id];
    if (!footprint) continue;

    const positions = polygonToCartesian(footprint);
    const color = getFloorColor(floor.floor_number);

    // z_min and z_max are relative to ground (0-3, 3-6, etc.)
    const absBase = terrainHeight + floor.z_min;
    const absTop = terrainHeight + floor.z_max;

    const entity = viewer.entities.add({
      id: `floor:${property.three_d_ulpin}`,
      name: `${property.three_d_ulpin} — Floor ${floor.floor_number}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: color,
        outline: true,
        outlineColor: Cesium.Color.WHITE.withAlpha(0.6),
        outlineWidth: 2,
        height: absBase,
        extrudedHeight: absTop,
      },
      properties: {
        entityType: "floor",
        three_d_ulpin: property.three_d_ulpin,
        property_id: property.property_id,
        parcel_id: property.parcel_id,
        building_id: property.building_id,
        floor_id: property.floor_id,
        floor_number: floor.floor_number,
        unit_number: property.unit_number,
        source: property.source,
      },
    });

    entities.push(entity);
  }

  return entities;
}

/**
 * Set visibility for all floor entities.
 */
export function setFloorVisibility(entities, visible) {
  for (const entity of entities) {
    entity.show = visible;
  }
}

/**
 * Highlight a specific floor entity by ULPIN.
 * Resets all others to their default color.
 */
export function highlightFloor(entities, ulpin, floors) {
  for (const entity of entities) {
    const entityUlpin = entity.properties?.three_d_ulpin?.getValue();
    const floorNumber = entity.properties?.floor_number?.getValue();

    if (ulpin && entityUlpin === ulpin) {
      entity.polygon.material = SELECTION_COLOR;
      entity.polygon.outlineColor = Cesium.Color.YELLOW;
      entity.polygon.outlineWidth = 3;
    } else {
      const color = getFloorColor(floorNumber || 1);
      entity.polygon.material = color;
      entity.polygon.outlineColor = Cesium.Color.WHITE.withAlpha(0.6);
      entity.polygon.outlineWidth = 2;
    }
  }
}
