/**
 * Sample Buildings — DEMO DATA
 *
 * Synthetic demonstration building data.
 * Geographic context: New Delhi, India
 *
 * CRS: EPSG:4326 (WGS84 lon/lat)
 * Elevations: heights are RELATIVE TO GROUND for demo visualization.
 * elevation_source tracks where height data came from.
 * In M4+ this will be "LIDAR", "DEM", "DSM" etc.
 */

const sampleBuildings = [
  {
    building_id: "B01",
    parcel_id: "P001",
    // Building footprint (smaller polygon inside parcel) [lon, lat]
    footprint: [
      [77.2297, 28.6131],
      [77.2303, 28.6131],
      [77.2303, 28.6137],
      [77.2297, 28.6137],
      [77.2297, 28.6131],
    ],
    height: 12.0,            // meters total building height
    ground_elevation: 0.0,   // relative to ground surface
    roof_elevation: 12.0,    // ground_elevation + height
    num_floors: 4,
    confidence: 1.0,         // Will be YOLO confidence in M4+
    elevation_source: "DEMO_DATA",
    source: "DEMO_DATA",
  },
];

export default sampleBuildings;
