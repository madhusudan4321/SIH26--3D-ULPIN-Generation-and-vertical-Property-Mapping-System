/**
 * Building Entity Module
 *
 * Creates Cesium 3D building envelope entities, PostGIS source model footprint polygons,
 * authoritative reference footprint polygons, and local ENU centroid anchor points.
 * Positioned using WGS84 geographic coordinates and relative ground heights.
 */

import * as Cesium from "cesium";
import { BUILDING_OUTLINE_COLOR, polygonToCartesian } from "./utils";

/**
 * Create building 3D volume, PostGIS model footprint, reference footprint, and anchor point entities on the viewer.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} buildings - Array of building records from API or sample data
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createBuildingEntities(viewer, buildings) {
  const entities = [];

  for (const building of buildings) {
    const footprintGeom = building.footprint_geojson || building.footprint;
    if (!footprintGeom) continue;

    const positions = polygonToCartesian(footprintGeom);
    if (!positions || positions.length < 3) continue;

    const groundElev = building.ground_elevation || 0.0;
    const refElev = building.reference_elevation || groundElev;
    const height = building.height || building.roof_elevation || 18.0;

    // 1. Authoritative Reference Footprint Entity (if available)
    const refGeom = building.reference_footprint_geojson || building.reference_footprint;
    if (refGeom) {
      const refPositions = polygonToCartesian(refGeom);
      if (refPositions && refPositions.length >= 3) {
        const refEntity = viewer.entities.add({
          id: `ref_footprint:${building.building_id}`,
          name: `Reference Footprint ${building.name || building.building_id}`,
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(refPositions),
            material: Cesium.Color.fromCssColorString("#a855f7").withAlpha(0.20), // Purple highlight for Cadastral Reference
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString("#a855f7"),
            outlineWidth: 3,
            height: refElev + 0.05,
            heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
          },
          properties: {
            entityType: "ref_footprint",
            building_id: building.building_id,
            name: building.name,
          },
        });
        entities.push(refEntity);
      }
    }

    // 2. PostGIS Source Model Ground Footprint Polygon Highlight Entity
    const footprintEntity = viewer.entities.add({
      id: `footprint:${building.building_id}`,
      name: `Model Footprint ${building.name || building.building_id}`,
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

    // 3. Local ENU Centroid Anchor Point Entity
    const anchorLat = building.model_anchor_lat || building.latitude;
    const anchorLon = building.model_anchor_lon || building.longitude;
    if (anchorLat != null && anchorLon != null) {
      const anchorEntity = viewer.entities.add({
        id: `anchor:${building.building_id}`,
        name: `Anchor (${building.building_id})`,
        position: Cesium.Cartesian3.fromDegrees(anchorLon, anchorLat, groundElev + 0.3),
        point: {
          pixelSize: 8,
          color: Cesium.Color.RED,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
        },
        properties: {
          entityType: "anchor",
          building_id: building.building_id,
        },
      });
      entities.push(anchorEntity);
    }

    // 4. 3D Building Envelope Volume Entity
    const envelopeEntity = viewer.entities.add({
      id: `building:${building.building_id}`,
      name: `Building ${building.name || building.building_id}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: Cesium.Color.SLATEGRAY.withAlpha(0.14),
        outline: true,
        outlineColor: BUILDING_OUTLINE_COLOR,
        outlineWidth: 2,
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
        entity.polygon.material = Cesium.Color.SLATEGRAY.withAlpha(0.14);
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
        entity.polygon.outlineWidth = 2;
      }
    }
  }
}
