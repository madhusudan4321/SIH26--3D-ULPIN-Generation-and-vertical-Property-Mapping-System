/**
 * API Service — Data Abstraction Layer
 *
 * M1: Returns local sample data.
 * M2+: Will call FastAPI endpoints at VITE_API_BASE_URL.
 *
 * All functions return Promises (async) so swapping to fetch()
 * in M2 requires zero component changes.
 */

import sampleParcels from "../data/sampleParcels";
import sampleBuildings from "../data/sampleBuildings";
import sampleFloors from "../data/sampleFloors";
import sampleProperties from "../data/sampleProperties";
import sampleRor from "../data/sampleRor";
import sampleUnderground from "../data/sampleUnderground";

// const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// ─── Parcels ────────────────────────────────────────────────

export async function getParcels() {
  return sampleParcels;
}

export async function getParcel(parcelId) {
  return sampleParcels.find((p) => p.parcel_id === parcelId) || null;
}

// ─── Buildings ──────────────────────────────────────────────

export async function getBuildings() {
  return sampleBuildings;
}

export async function getBuilding(buildingId) {
  return sampleBuildings.find((b) => b.building_id === buildingId) || null;
}

// ─── Floors ─────────────────────────────────────────────────

export async function getFloors(buildingId = null) {
  if (buildingId) {
    return sampleFloors.filter((f) => f.building_id === buildingId);
  }
  return sampleFloors;
}

export async function getFloor(floorId) {
  return sampleFloors.find((f) => f.floor_id === floorId) || null;
}

// ─── Properties ─────────────────────────────────────────────

export async function getProperties() {
  return sampleProperties;
}

export async function getProperty(ulpin) {
  return sampleProperties.find((p) => p.three_d_ulpin === ulpin) || null;
}

export async function getPropertiesByFloor(floorId) {
  return sampleProperties.filter((p) => p.floor_id === floorId);
}

// ─── RoR ────────────────────────────────────────────────────

export async function getRor(rorId) {
  return sampleRor.find((r) => r.ror_id === rorId) || null;
}

export async function getAllRor() {
  return sampleRor;
}

// ─── Underground ────────────────────────────────────────────

export async function getUndergroundAssets() {
  return sampleUnderground;
}

// ─── Search ─────────────────────────────────────────────────

/**
 * Search across ULPINs, parcel IDs, and building IDs.
 * Returns unified results with type indicator.
 *
 * @param {string} query - Search query (case-insensitive partial match)
 * @returns {Promise<Array<{type: string, id: string, label: string, data: object}>>}
 */
export async function search(query) {
  if (!query || query.trim().length === 0) return [];

  const q = query.trim().toUpperCase();
  const results = [];

  // Search properties by 3D ULPIN
  for (const prop of sampleProperties) {
    if (prop.three_d_ulpin.toUpperCase().includes(q)) {
      results.push({
        type: "property",
        id: prop.three_d_ulpin,
        label: prop.three_d_ulpin,
        data: prop,
      });
    }
  }

  // Search parcels by parcel_id
  for (const parcel of sampleParcels) {
    if (parcel.parcel_id.toUpperCase().includes(q)) {
      results.push({
        type: "parcel",
        id: parcel.parcel_id,
        label: `Parcel ${parcel.parcel_id}`,
        data: parcel,
      });
    }
  }

  // Search buildings by building_id
  for (const building of sampleBuildings) {
    if (building.building_id.toUpperCase().includes(q)) {
      results.push({
        type: "building",
        id: building.building_id,
        label: `Building ${building.building_id}`,
        data: building,
      });
    }
  }

  return results;
}
