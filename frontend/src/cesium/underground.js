/**
 * Underground Asset Entity Module
 *
 * Creates polyline entities for underground infrastructure.
 * Assets are displayed below the surface using terrain-relative depths.
 *
 * This is purely synthetic demo data visualization.
 * No real GPR or underground detection is performed.
 */

import * as Cesium from "cesium";
import { getUndergroundColor } from "./utils";

/**
 * Create underground asset entities on the viewer.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} assets - Underground asset records from api.js
 * @param {number} terrainHeight - Actual terrain height at sample location
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createUndergroundEntities(viewer, assets, terrainHeight) {
  const entities = [];

  for (const asset of assets) {
    const color = getUndergroundColor(asset.type);
    // depth is negative (e.g., -2.0 means 2m below surface)
    const absHeight = terrainHeight + asset.depth;

    // Create Cartesian3 positions at underground depth
    const positions = [];
    for (const [lon, lat] of asset.coordinates) {
      positions.push(Cesium.Cartesian3.fromDegrees(lon, lat, absHeight));
    }

    const entity = viewer.entities.add({
      id: `underground:${asset.asset_id}`,
      name: `${asset.type.replace(/_/g, " ")} (${asset.asset_id})`,
      polyline: {
        positions: positions,
        width: 5,
        material: new Cesium.PolylineDashMaterialProperty({
          color: color.withAlpha(0.9),
          dashLength: 12.0,
        }),
        clampToGround: false,
      },
      properties: {
        entityType: "underground",
        asset_id: asset.asset_id,
        type: asset.type,
        depth: asset.depth,
        source: asset.source,
      },
    });

    entities.push(entity);
  }

  return entities;
}

/**
 * Set visibility for all underground entities.
 */
export function setUndergroundVisibility(entities, visible) {
  for (const entity of entities) {
    entity.show = visible;
  }
}
