/**
 * Sample Record of Rights — DEMO DATA
 *
 * Synthetic demonstration RoR data.
 * NOT real government ownership information.
 * All records clearly marked with source: "DEMO_DATA".
 *
 * In M2+ these will come from the backend database via FastAPI.
 */

const sampleRor = [
  {
    ror_id: "ROR001",
    parcel_id: "P001",
    owner_name: "Demo Owner A",
    area: 120.0,
    land_use: "Residential",
    rights: "Freehold",
    source: "DEMO_DATA",
  },
  {
    ror_id: "ROR002",
    parcel_id: "P001",
    owner_name: "Demo Owner B",
    area: 95.0,
    land_use: "Residential",
    rights: "Freehold",
    source: "DEMO_DATA",
  },
  {
    ror_id: "ROR003",
    parcel_id: "P001",
    owner_name: "Demo Owner C",
    area: 85.0,
    land_use: "Commercial",
    rights: "Leasehold",
    source: "DEMO_DATA",
  },
  {
    ror_id: "ROR004",
    parcel_id: "P001",
    owner_name: "Demo Owner D",
    area: 110.0,
    land_use: "Residential",
    rights: "Freehold",
    source: "DEMO_DATA",
  },
];

export default sampleRor;
