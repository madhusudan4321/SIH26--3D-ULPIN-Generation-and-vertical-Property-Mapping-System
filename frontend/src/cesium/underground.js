/**
 * Underground Asset Entity Module
 *
 * Creates polyline entities for underground infrastructure.
 * Assets are displayed below the surface using terrain-relative depths.
 *
 * This is purely synthetic demo data visualization.
 */

import * as Cesium from "cesium";
import { getUndergroundColor } from "./utils";

/**
 * Create underground asset entities on the viewer.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} assets - Underground asset records from api.js
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createUndergroundEntities(viewer, assets) {
  const entities = [];
  if (!Array.isArray(assets)) return entities;

  for (const asset of assets) {
    if (!asset || !asset.coordinates) continue;

    const color = getUndergroundColor(asset.type);
    const depth = typeof asset.depth === "number" && !isNaN(asset.depth) ? asset.depth : -2.0;

    // Create Cartesian3 positions at depth below ground
    const positions = [];
    if (Array.isArray(asset.coordinates)) {
      for (const pt of asset.coordinates) {
        if (Array.isArray(pt) && pt.length >= 2) {
          const lon = Number(pt[0]);
          const lat = Number(pt[1]);
          if (!isNaN(lon) && !isNaN(lat)) {
            positions.push(Cesium.Cartesian3.fromDegrees(lon, lat, depth));
          }
        }
      }
    }

    if (positions.length < 2) continue;

    const entity = viewer.entities.add({
      id: `underground:${asset.asset_id}`,
      name: `${(asset.type || "").replace(/_/g, " ")} (${asset.asset_id})`,
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
        depth: depth,
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
