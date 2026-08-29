/**
 * Parcel Entity Module
 *
 * Creates Cesium polygon entities for cadastral parcels.
 * Parcels are displayed as semi-transparent ground polygons
 * with amber outline, just above the terrain surface.
 */

import * as Cesium from "cesium";
import { PARCEL_COLOR, PARCEL_OUTLINE_COLOR, polygonToCartesian } from "./utils";

/**
 * Create parcel entities on the viewer.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} parcels - Array of parcel records from api.js
 * @param {number} terrainHeight - Actual terrain height at sample location
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createParcelEntities(viewer, parcels, terrainHeight) {
  const entities = [];

  for (const parcel of parcels) {
    const positions = polygonToCartesian(parcel.geometry_2d);

    const entity = viewer.entities.add({
      id: `parcel:${parcel.parcel_id}`,
      name: `Parcel ${parcel.parcel_id}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: PARCEL_COLOR,
        outline: true,
        outlineColor: PARCEL_OUTLINE_COLOR,
        outlineWidth: 2,
        height: terrainHeight + 0.5, // just above terrain to be visible
      },
      properties: {
        entityType: "parcel",
        parcel_id: parcel.parcel_id,
        source: parcel.source,
      },
    });

    entities.push(entity);
  }

  return entities;
}

/**
 * Set visibility for all parcel entities.
 */
export function setParcelVisibility(entities, visible) {
  for (const entity of entities) {
    entity.show = visible;
  }
}
