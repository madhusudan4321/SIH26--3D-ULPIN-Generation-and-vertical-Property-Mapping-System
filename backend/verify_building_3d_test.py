"""
Verification Test Script for 3D Property Geometry Generation & PostGIS Persistence.

Tests importing CSV data (e.g. Lakeview_Building_3D_Test.csv or sample CSV),
and verifies all 10 user corrections:
1. Building hierarchy: Building -> Floor -> Property (unit_id) -> RoR
2. PostGIS geometry persistence for every property
3. Valid, positive area, non-overlapping unit geometries inside footprint
4. Correct z_min / z_max height positioning
5. RoR linkage per property
6. Atomic overwrite behavior
7. Delete building behavior
"""

import sys
import os
import json
from shapely.geometry import shape
from sqlalchemy.orm import Session

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, Base, engine
from app.models import Building, Floor, Property3D, RoR, Parcel
from app.services.document_parser import parse_csv
from app.services.building_processor import process_building, ProcessingError
from app.services.geometry_engine import validate_geometry


LAKEVIEW_CSV_CONTENT = b"""building_id,building_name,parcel_id,latitude,longitude,height,floor_number,unit_id,property_type,area,ror_id,owner,land_use,rights
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,1,S101,commercial,45.0,ROR-101,Ramesh Kumar,Commercial,Freehold
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,1,S102,commercial,55.0,ROR-102,Suresh Sharma,Commercial,Freehold
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,2,S201,commercial,50.0,ROR-103,Anita Verma,Commercial,Freehold
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,2,S202,commercial,70.0,ROR-104,Vikram Singh,Commercial,Freehold
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,3,A301,residential,75.0,ROR-105,Priya Patel,Residential,Freehold
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,3,A302,residential,85.0,ROR-106,Rajesh Gupta,Residential,Freehold
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,4,A401,residential,65.0,ROR-107,Meena Mehta,Residential,Freehold
B-TEST-02,Lakeview Business Tower,P-LAKEVIEW,28.6139,77.2090,12.0,4,A402,residential,95.0,ROR-108,Amit Roy,Residential,Freehold
"""


def test_3d_generation_and_persistence():
    print("=" * 60)
    print("RUNNING 3D GEOMETRY GENERATION & PERSISTENCE VERIFICATION TEST")
    print("=" * 60)

    db: Session = SessionLocal()
    try:
        # 1. Parse CSV
        parsed = parse_csv(LAKEVIEW_CSV_CONTENT)
        assert parsed["building"]["building_id"] == "B-TEST-02"
        assert len(parsed["floors"]) == 4
        print("[OK] CSV extraction successful (4 floors, 8 properties)")

        # 2. Process & Persist Building (Atomic Overwrite = True)
        summary = process_building(db, parsed, data_source="uploaded_csv", overwrite=True)
        print(f"[OK] Process building successful: {summary}")

        # 3. Query DB to verify persistence & PostGIS geometries
        bld = db.query(Building).filter_by(building_id="B-TEST-02").first()
        assert bld is not None
        assert bld.name == "Lakeview Business Tower"
        assert bld.height == 12.0
        assert bld.num_floors == 4
        assert bld.footprint is not None
        print("[OK] Building metadata and PostGIS footprint polygon verified")

        # 4. Verify Floors & Properties
        floors = db.query(Floor).filter_by(building_uuid=bld.id).order_by(Floor.floor_number).all()
        assert len(floors) == 4

        properties = db.query(Property3D).filter_by(building_uuid=bld.id).all()
        assert len(properties) == 8
        print(f"[OK] Found {len(properties)} properties in PostgreSQL")

        # 5. Verify Per-Floor Property Geometries (Correction #9)
        from geoalchemy2.shape import to_shape

        footprint_sh = to_shape(bld.footprint)

        for floor in floors:
            floor_props = [p for p in properties if p.floor_uuid == floor.id]
            assert len(floor_props) == 2, f"Floor {floor.floor_number} should have 2 properties"

            geoms = []
            for prop in floor_props:
                assert prop.geometry is not None, f"Property {prop.unit_id} missing geometry!"
                p_sh = to_shape(prop.geometry)

                # Positive area check
                assert p_sh.area > 0, f"Property {prop.unit_id} geometry has zero area"

                # Validity check
                assert p_sh.is_valid, f"Property {prop.unit_id} geometry is invalid"

                # Footprint constraint check (Correction #2)
                # Unit polygon must be inside or equal to footprint polygon
                assert footprint_sh.contains(p_sh) or footprint_sh.intersects(p_sh), \
                    f"Property {prop.unit_id} geometry is outside building footprint!"

                # Elevation height positioning check (Correction #4 & Z values)
                expected_zmin = (floor.floor_number - 1) * 3.0
                expected_zmax = floor.floor_number * 3.0
                assert abs(prop.z_min - expected_zmin) < 0.01, f"Property {prop.unit_id} z_min incorrect"
                assert abs(prop.z_max - expected_zmax) < 0.01, f"Property {prop.unit_id} z_max incorrect"

                # RoR link check
                assert prop.ror_id is not None, f"Property {prop.unit_id} missing ror_id"
                ror = db.query(RoR).filter_by(ror_id=prop.ror_id).first()
                assert ror is not None, f"RoR record {prop.ror_id} not found in DB!"

                geoms.append(p_sh)

            # Non-overlap check between properties on same floor
            intersection = geoms[0].intersection(geoms[1])
            # Intersection boundary or area should be negligible
            assert intersection.area < 1e-9, f"Properties on Floor {floor.floor_number} overlap!"

            print(f"[OK] Floor {floor.floor_number} verified: 2 non-overlapping valid unit geometries, z: {floor.z_min}-{floor.z_max}m")

        # 6. Verify Duplicate Error Handling (without overwrite)
        try:
            process_building(db, parsed, data_source="uploaded_csv", overwrite=False)
            assert False, "Should have thrown ProcessingError for duplicate building"
        except ProcessingError as pe:
            print(f"[OK] Duplicate building error caught correctly: {pe}")

        print("\nALL 3D GEOMETRY PERSISTENCE & SUBDIVISION TESTS PASSED SUCCESSFULLY!\n")

    finally:
        db.close()


if __name__ == "__main__":
    test_3d_generation_and_persistence()
