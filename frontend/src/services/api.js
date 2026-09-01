/**
 * API Service — Data Abstraction Layer
 *
 * M2: Calls FastAPI backend via fetch().
 * On backend error: throws explicit error (NOT silent DEMO fallback).
 * Demo data can only be loaded by explicit user action.
 */

import sampleParcels from "../data/sampleParcels";
import sampleBuildings from "../data/sampleBuildings";
import sampleFloors from "../data/sampleFloors";
import sampleProperties from "../data/sampleProperties";
import sampleRor from "../data/sampleRor";
import sampleUnderground from "../data/sampleUnderground";

// ─── Internal Helpers ───────────────────────────────────────

/**
 * Fetch JSON from backend. Throws on error.
 * NEVER silently falls back to demo data.
 */
async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json();
}

/**
 * Check if backend is available.
 * Returns { ok, data } or { ok: false, error }.
 */
export async function checkHealth() {
  try {
    const data = await apiFetch("/api/health/db");
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// ─── Buildings (from PostgreSQL) ────────────────────────────

export async function getBuildings() {
  return apiFetch("/api/buildings");
}

export async function getBuilding(buildingId) {
  return apiFetch(`/api/buildings/${buildingId}`);
}

export async function getBuildingProperties(buildingId) {
  return apiFetch(`/api/buildings/${buildingId}/properties`);
}

// ─── Properties (from PostgreSQL) ───────────────────────────

export async function getProperty(ulpin) {
  return apiFetch(`/api/properties/${ulpin}`);
}

export async function getPropertyRor(ulpin) {
  return apiFetch(`/api/properties/${ulpin}/ror`);
}

// ─── Search (from PostgreSQL) ───────────────────────────────

export async function search(query) {
  if (!query || query.trim().length === 0) return [];
  const data = await apiFetch(`/api/search?q=${encodeURIComponent(query)}`);
  // Transform backend results to match frontend format
  return (data.results || []).map((r) => ({
    type: r.type,
    id: r.ulpin || r.building_id || r.parcel_id,
    label: r.ulpin || r.building_name || r.building_id || r.parcel_id,
    data: r,
  }));
}

export async function deleteBuilding(buildingId) {
  return apiFetch(`/api/buildings/${buildingId}`, {
    method: "DELETE",
  });
}

// ─── Upload ─────────────────────────────────────────────────

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Upload failed: ${detail}`);
  }
  return res.json();
}

export async function getReviewData(datasetId) {
  return apiFetch(`/api/upload/${datasetId}/review`);
}

export async function updateReviewData(datasetId, updatedData) {
  return apiFetch(`/api/upload/${datasetId}/review`, {
    method: "PUT",
    body: JSON.stringify(updatedData),
  });
}

export async function confirmDataset(datasetId, overwrite = false) {
  return apiFetch(`/api/upload/${datasetId}/confirm?overwrite=${overwrite}`, {
    method: "POST",
  });
}

// ─── Manual Entry ───────────────────────────────────────────

export async function submitManualEntry(buildingData, overwrite = false) {
  return apiFetch(`/api/manual-entry?overwrite=${overwrite}`, {
    method: "POST",
    body: JSON.stringify(buildingData),
  });
}

// ─── Demo Data (EXPLICIT user action only) ──────────────────

/**
 * Load demo data from local sample files.
 * This is ONLY called when the user explicitly clicks "Load Demo Data".
 * NEVER called automatically as a silent fallback.
 */
export function loadDemoData() {
  return {
    parcels: sampleParcels,
    buildings: sampleBuildings,
    floors: sampleFloors,
    properties: sampleProperties,
    ror: sampleRor,
    underground: sampleUnderground,
  };
}

// ─── Legacy API shims (for components not yet fully migrated) ─

export async function getParcels() {
  return sampleParcels;
}

export async function getFloors(buildingId = null) {
  if (buildingId) {
    return sampleFloors.filter((f) => f.building_id === buildingId);
  }
  return sampleFloors;
}

export async function getFloor(floorId) {
  return sampleFloors.find((f) => f.floor_id === floorId) || null;
}

export async function getRor(rorId) {
  return sampleRor.find((r) => r.ror_id === rorId) || null;
}

export async function getUndergroundAssets() {
  return sampleUnderground;
}

export async function getProperties() {
  return sampleProperties;
}
