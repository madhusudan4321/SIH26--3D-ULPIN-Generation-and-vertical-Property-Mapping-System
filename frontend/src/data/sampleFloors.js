/**
 * Sample Floors — DEMO DATA
 *
 * Synthetic demonstration floor data.
 * Each floor has z_min / z_max defining its vertical extent.
 * Heights are RELATIVE TO GROUND for demo visualization.
 * In M4+ these will be derived from LiDAR peak detection.
 *
 * Relationship: BUILDING 1 → MANY FLOORS
 * elevation_source tracks data provenance.
 */

const sampleFloors = [
  {
    floor_id: "F01",
    building_id: "B01",
    floor_number: 1,
    z_min: 0.0,    // ground level
    z_max: 3.0,    // 3m above ground
    elevation_source: "DEMO_DATA",
    source: "DEMO_DATA",
  },
  {
    floor_id: "F02",
    building_id: "B01",
    floor_number: 2,
    z_min: 3.0,
    z_max: 6.0,
    elevation_source: "DEMO_DATA",
    source: "DEMO_DATA",
  },
  {
    floor_id: "F03",
    building_id: "B01",
    floor_number: 3,
    z_min: 6.0,
    z_max: 9.0,
    elevation_source: "DEMO_DATA",
    source: "DEMO_DATA",
  },
  {
    floor_id: "F04",
    building_id: "B01",
    floor_number: 4,
    z_min: 9.0,
    z_max: 12.0,
    elevation_source: "DEMO_DATA",
    source: "DEMO_DATA",
  },
];

export default sampleFloors;
