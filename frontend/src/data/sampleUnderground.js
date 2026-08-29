/**
 * Sample Underground Assets — DEMO DATA
 *
 * Synthetic underground infrastructure for demonstration.
 * NOT real underground survey data.
 * No GPR or real underground detection is performed.
 *
 * Each asset has coordinates [lon, lat], depth (negative = below surface),
 * and explicit source labeling.
 */

const sampleUnderground = [
  {
    asset_id: "WATER_PIPE_001",
    parcel_id: "P001",
    type: "water_pipeline",
    coordinates: [
      [77.229, 28.6134],
      [77.231, 28.6134],
    ],
    depth: -2.0, // meters below surface
    source: "DEMO_DATA",
  },
  {
    asset_id: "SEWER_001",
    parcel_id: "P001",
    type: "sewer",
    coordinates: [
      [77.23, 28.6125],
      [77.23, 28.6142],
    ],
    depth: -3.5,
    source: "DEMO_DATA",
  },
  {
    asset_id: "ELEC_001",
    parcel_id: "P001",
    type: "electricity_cable",
    coordinates: [
      [77.2293, 28.6131],
      [77.2307, 28.6137],
    ],
    depth: -1.0,
    source: "DEMO_DATA",
  },
];

export default sampleUnderground;
