/**
 * Floor Entity Module — 3D Property Volumes
 *
 * Creates individual extruded 3D property volume entities in Cesium.
 * Each property (shop/apartment) is a distinct, independently selectable
 * 3D volume using its 2D unit footprint polygon and exact floor z_min / z_max boundaries.
 *
 * Uses Cesium.HeightReference.RELATIVE_TO_GROUND to ensure 3D unit volumes
 * anchor perfectly to terrain surface height without underground depth-clipping.
 */

import * as Cesium from "cesium";
import { getUnitColor, SELECTION_COLOR, polygonToCartesian } from "./utils";

/**
 * Create floor/property volume entities on the viewer.
 *
 * ONE UNIT = ONE PICKABLE CESIUM ENTITY.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Array} floors - Floor records
 * @param {Array} properties - Property records from API (with geometry_geojson, z_min, z_max, etc.)
 * @param {Array} buildings - Building records
 * @returns {Array<Cesium.Entity>} Created entities
 */
export function createFloorEntities(viewer, floors, properties, buildings) {
  const entities = [];

  // Footprint lookup map by building_id
  const buildingMap = {};
  for (const b of buildings) {
    buildingMap[b.building_id] = b;
  }

  // Group properties per floor to track unit index for distinct visual coloring
  const floorUnitIndices = {};

  // Create one 3D entity per property unit
  for (const property of properties) {
    const ulpin = property.ulpin || property.three_d_ulpin;
    if (!ulpin) continue;

    const floorNumber = property.floor_number || 1;
    const building = buildingMap[property.building_id];

    // Track unit index on this floor
    if (!floorUnitIndices[floorNumber]) {
      floorUnitIndices[floorNumber] = 0;
    }
    const unitIndex = floorUnitIndices[floorNumber];
    floorUnitIndices[floorNumber] += 1;

    // Priority for unit geometry:
    // 1. Property's own unit geometry (geometry_geojson)
    // 2. Building footprint (fallback if unit geometry missing)
    let unitGeometry = property.geometry_geojson;
    if (!unitGeometry && building) {
      unitGeometry = building.footprint_geojson || building.footprint;
    }

    if (!unitGeometry) continue;

    const positions = polygonToCartesian(unitGeometry);
    if (!positions || positions.length < 3) continue;

    const propertyType = property.property_type || "";
    const color = getUnitColor(floorNumber, unitIndex, propertyType, 0.75);

    // Elevation steps relative to ground level
    const zMin = property.z_min != null ? property.z_min : (floorNumber - 1) * 3.0;
    const zMax = property.z_max != null ? property.z_max : floorNumber * 3.0;

    const unitId = property.unit_id || property.unit_number || "Unit";
    const subUlpin = property.sub_ulpin || `SUB-ULPIN-${property.building_id}-${unitId}`;

    const entity = viewer.entities.add({
      id: `floor:${ulpin}`,
      name: `${unitId} (${subUlpin}) — Floor ${floorNumber}`,
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: color,
        outline: true,
        outlineColor: Cesium.Color.WHITE.withAlpha(0.85),
        outlineWidth: 2,
        height: zMin,
        extrudedHeight: zMax,
        heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
        extrudedHeightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
      },
      properties: {
        entityType: "floor",
        ulpin: ulpin,
        sub_ulpin: subUlpin,
        three_d_ulpin: ulpin,
        unit_id: unitId,
        property_id: property.property_id,
        building_id: property.building_id,
        floor_id: property.floor_id,
        floor_number: floorNumber,
        unit_index: unitIndex,
        ror_id: property.ror_id,
        property_type: propertyType,
        area: property.area,
        z_min: zMin,
        z_max: zMax,
        geometry_source: property.geometry_source || "synthetic_subdivision",
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
 * Dynamically update floor entities for Floor Visibility, Floor Isolation, and Exploded Floor View.
 */
export function updateFloorEntities(entities, options = {}) {
  const {
    visibleFloors = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    isolatedFloorNumber = null,
    explodedView = false,
    explodeOffset = 5.0,
  } = options;

  for (const entity of entities) {
    const floorNumber = entity.properties?.floor_number?.getValue() || 1;
    const zMin = entity.properties?.z_min?.getValue() ?? (floorNumber - 1) * 3.0;
    const zMax = entity.properties?.z_max?.getValue() ?? floorNumber * 3.0;

    // Check floor visibility & isolation
    const isVisible = isolatedFloorNumber != null
      ? floorNumber === isolatedFloorNumber
      : visibleFloors.includes(floorNumber);

    entity.show = isVisible;

    // Calculate vertical displacement for Exploded View
    const zOffset = explodedView ? (floorNumber - 1) * (explodeOffset || 5.0) : 0.0;

    const baseZ = zMin + zOffset;
    const topZ = zMax + zOffset;

    if (entity.polygon) {
      entity.polygon.height = baseZ;
      entity.polygon.extrudedHeight = topZ;
    }
  }
}

/**
 * Highlight ONLY the selected property volume entity by ULPIN / Sub-ULPIN.
 * Resets all other unit entities to their specific unit color.
 */
export function highlightFloor(entities, ulpin) {
  for (const entity of entities) {
    const entityUlpin =
      entity.properties?.ulpin?.getValue() ||
      entity.properties?.three_d_ulpin?.getValue();
    const entitySubUlpin = entity.properties?.sub_ulpin?.getValue();
    const floorNumber = entity.properties?.floor_number?.getValue() || 1;
    const unitIndex = entity.properties?.unit_index?.getValue() || 0;
    const propertyType = entity.properties?.property_type?.getValue() || "";

    const isMatch = ulpin && (entityUlpin === ulpin || entitySubUlpin === ulpin);

    if (isMatch) {
      entity.polygon.material = SELECTION_COLOR;
      entity.polygon.outlineColor = Cesium.Color.YELLOW;
      entity.polygon.outlineWidth = 4;
    } else {
      const color = getUnitColor(floorNumber, unitIndex, propertyType, 0.75);
      entity.polygon.material = color;
      entity.polygon.outlineColor = Cesium.Color.WHITE.withAlpha(0.85);
      entity.polygon.outlineWidth = 2;
    }
  }
}
