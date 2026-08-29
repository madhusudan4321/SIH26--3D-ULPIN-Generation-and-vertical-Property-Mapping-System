/**
 * Sample 3D Properties — DEMO DATA
 *
 * Synthetic demonstration 3D property volumes.
 * Each property has a prototype 3D ULPIN.
 *
 * Relationship: FLOOR 1 → MANY PROPERTY_3D
 * M1 uses one property per floor for simplicity.
 * The architecture supports multiple properties per floor
 * (e.g., apartments/units within a floor).
 *
 * 3D ULPIN format: 3D-{parcel_id}-{building_id}-F{floor_number:02d}-U{unit_number}
 * This is a PROTOTYPE identifier scheme, NOT the official Government of India format.
 */

const sampleProperties = [
  {
    property_id: "PROP001",
    three_d_ulpin: "3D-P001-B01-F01-U101",
    parcel_id: "P001",
    building_id: "B01",
    floor_id: "F01",
    unit_number: "U101",
    ror_id: "ROR001",
    source: "DEMO_DATA",
  },
  {
    property_id: "PROP002",
    three_d_ulpin: "3D-P001-B01-F02-U201",
    parcel_id: "P001",
    building_id: "B01",
    floor_id: "F02",
    unit_number: "U201",
    ror_id: "ROR002",
    source: "DEMO_DATA",
  },
  {
    property_id: "PROP003",
    three_d_ulpin: "3D-P001-B01-F03-U301",
    parcel_id: "P001",
    building_id: "B01",
    floor_id: "F03",
    unit_number: "U301",
    ror_id: "ROR003",
    source: "DEMO_DATA",
  },
  {
    property_id: "PROP004",
    three_d_ulpin: "3D-P001-B01-F04-U401",
    parcel_id: "P001",
    building_id: "B01",
    floor_id: "F04",
    unit_number: "U401",
    ror_id: "ROR004",
    source: "DEMO_DATA",
  },
];

export default sampleProperties;
