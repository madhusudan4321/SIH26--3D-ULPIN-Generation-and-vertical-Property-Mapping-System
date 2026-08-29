/**
 * Sample Parcels — DEMO DATA
 *
 * Synthetic demonstration parcel data.
 * NOT a real government cadastral record.
 * Geographic context: New Delhi, India (India Gate vicinity)
 *
 * CRS: EPSG:4326 (WGS84 lon/lat)
 */

const sampleParcels = [
  {
    parcel_id: "P001",
    ulpin: null, // No official ULPIN assigned in demo
    survey_number: "DEMO-SN-001",
    // Polygon coordinates [lon, lat] — EPSG:4326
    geometry_2d: [
      [77.2295, 28.6129],
      [77.2305, 28.6129],
      [77.2305, 28.6139],
      [77.2295, 28.6139],
      [77.2295, 28.6129],
    ],
    area: 2500.0, // sq meters (synthetic)
    ror_id: "ROR001",
    crs: "EPSG:4326",
    source: "DEMO_DATA",
  },
];

export default sampleParcels;
