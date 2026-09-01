/**
 * Parcel Entity Module
 *
 * Creates Cesium polygon entities for cadastral parcels.
 * Parcels are displayed as semi-transparent ground polygons
 * with amber outline, anchored relative to the terrain surface.
 */

import * as Cesium from "cesium";
import { PARCEL_COLOR, PARCEL_OUTLINE_COLOR, polygonToCartesian } from "./utils";

/**
 * Create parcel entities on the viewer using terrain-relative height.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} parcels - Array of parcel records from api.js
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createParcelEntities(viewer, parcels) {
  const entities = [];
  if (!Array.isArray(parcels)) return entities;

  for (const parcel of parcels) {
    if (!parcel) continue;
    const positions = polygonToCartesian(parcel.geometry_2d);
    if (!positions || positions.length < 3) continue;

    const entity = viewer.entities.add({
      id: `parcel:${parcel.parcel_id}`,
      name: `Parcel ${parcel.parcel_id}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: PARCEL_COLOR,
        outline: true,
        outlineColor: PARCEL_OUTLINE_COLOR,
        outlineWidth: 2,
        height: 0.2, // 0.2 meters above ground surface to prevent z-fighting
        heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
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
