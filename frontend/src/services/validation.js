/**
 * Validation Service — Client-side Topology Validation
 *
 * Implements 8 validation rules for 3D property records.
 * Returns structured results with PASS / WARNING / ERROR status.
 *
 * In M5+ this will be extended with PostGIS spatial/topology validation.
 */

import sampleParcels from "../data/sampleParcels";
import sampleBuildings from "../data/sampleBuildings";
import sampleFloors from "../data/sampleFloors";
import sampleProperties from "../data/sampleProperties";
import sampleRor from "../data/sampleRor";

/**
 * Validate a single 3D property record.
 *
 * @param {string} ulpin - The three_d_ulpin to validate
 * @returns {{ property_id: string, overall_status: string, timestamp: string, checks: Array }}
 */
export function validateProperty(ulpin) {
  const property = sampleProperties.find((p) => p.three_d_ulpin === ulpin);
  const checks = [];

  // Check 1: Property exists
  if (!property) {
    return {
      property_id: ulpin,
      overall_status: "ERROR",
      timestamp: new Date().toISOString(),
      checks: [
        {
          name: "Property exists",
          status: "ERROR",
          detail: `Property with ULPIN ${ulpin} not found`,
        },
      ],
    };
  }

  // Check 1: Parcel reference
  const parcel = sampleParcels.find(
    (p) => p.parcel_id === property.parcel_id
  );
  checks.push({
    name: "Parcel reference",
    status: parcel ? "PASS" : "ERROR",
    detail: parcel
      ? `${property.parcel_id} found`
      : `${property.parcel_id} not found`,
  });

  // Check 2: Building reference
  const building = sampleBuildings.find(
    (b) => b.building_id === property.building_id
  );
  checks.push({
    name: "Building reference",
    status: building ? "PASS" : "ERROR",
    detail: building
      ? `${property.building_id} found`
      : `${property.building_id} not found`,
  });

  // Check 3: Floor reference
  const floor = sampleFloors.find((f) => f.floor_id === property.floor_id);
  checks.push({
    name: "Floor reference",
    status: floor ? "PASS" : "ERROR",
    detail: floor
      ? `${property.floor_id} found`
      : `${property.floor_id} not found`,
  });

  // Check 4: Z-range validity
  if (floor) {
    const zValid = floor.z_min < floor.z_max;
    checks.push({
      name: "Floor Z range",
      status: zValid ? "PASS" : "ERROR",
      detail: zValid
        ? `${floor.z_min} < ${floor.z_max}`
        : `Invalid: z_min(${floor.z_min}) >= z_max(${floor.z_max})`,
    });
  } else {
    checks.push({
      name: "Floor Z range",
      status: "ERROR",
      detail: "Cannot validate — floor not found",
    });
  }

  // Check 5: ULPIN exists
  const ulpinExists =
    property.three_d_ulpin && property.three_d_ulpin.trim().length > 0;
  checks.push({
    name: "ULPIN exists",
    status: ulpinExists ? "PASS" : "ERROR",
    detail: ulpinExists ? property.three_d_ulpin : "ULPIN is empty or missing",
  });

  // Check 6: ULPIN uniqueness
  const duplicates = sampleProperties.filter(
    (p) => p.three_d_ulpin === property.three_d_ulpin
  );
  const isUnique = duplicates.length === 1;
  checks.push({
    name: "ULPIN uniqueness",
    status: isUnique ? "PASS" : "ERROR",
    detail: isUnique
      ? "No duplicates"
      : `${duplicates.length} records share this ULPIN`,
  });

  // Check 7: RoR reference
  if (property.ror_id) {
    const ror = sampleRor.find((r) => r.ror_id === property.ror_id);
    checks.push({
      name: "RoR reference",
      status: ror ? "PASS" : "WARNING",
      detail: ror
        ? `${property.ror_id} found`
        : `${property.ror_id} not found in records`,
    });
  } else {
    checks.push({
      name: "RoR reference",
      status: "WARNING",
      detail: "No RoR ID linked to this property",
    });
  }

  // Check 8: Required fields
  const requiredFields = [
    "property_id",
    "three_d_ulpin",
    "parcel_id",
    "building_id",
    "floor_id",
    "unit_number",
  ];
  const missingFields = requiredFields.filter(
    (f) => !property[f] || String(property[f]).trim().length === 0
  );
  checks.push({
    name: "Required fields",
    status: missingFields.length === 0 ? "PASS" : "ERROR",
    detail:
      missingFields.length === 0
        ? "All present"
        : `Missing: ${missingFields.join(", ")}`,
  });

  // Determine overall status: ERROR > WARNING > PASS
  let overall = "PASS";
  for (const check of checks) {
    if (check.status === "ERROR") {
      overall = "ERROR";
      break;
    }
    if (check.status === "WARNING") {
      overall = "WARNING";
    }
  }

  return {
    property_id: property.three_d_ulpin,
    overall_status: overall,
    timestamp: new Date().toISOString(),
    checks,
  };
}

/**
 * Validate all properties.
 * @returns {Array} Array of validation results
 */
export function validateAllProperties() {
  return sampleProperties.map((p) => validateProperty(p.three_d_ulpin));
}
