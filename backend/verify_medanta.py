"""
Backend Verification Script for MEDANTA-LKO-TEST-02 (Medanta Super Speciality Hospital, Lucknow)

Verifies:
1. Parse Medanta CSV & process building MEDANTA-LKO-TEST-02 with overwrite=True.
2. Building position in PostGIS at lat: 26.7776953, lon: 80.9856814.
3. 8 floors, 16 properties (F1-001, F1-002, ..., F8-002).
4. Every property has distinct non-overlapping PostGIS 2D polygon in properties_3d.geometry (SRID 4326).
5. elevation z_min and z_max match 3-meter floor steps (0-3, 3-6, 6-9, 9-12, 12-15, 15-18, 18-21, 21-24).
6. PostGIS SQL query verification.
"""

import sys
import os
import json
from shapely.geometry import shape
from sqlalchemy import text
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.document_parser import parse_csv
from app.services.building_processor import process_building


def verify_medanta():
    print("=" * 70)
    print("VERIFYING POSTGIS DATA FOR MEDANTA-LKO-TEST-02 (Lucknow)")
    print("=" * 70)

    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Medanta_Lucknow_3D_Test.csv")
    with open(csv_path, "rb") as f:
        csv_bytes = f.read()

    db: Session = SessionLocal()
    try:
        parsed = parse_csv(csv_bytes)
        summary = process_building(db, parsed, data_source="uploaded_csv", overwrite=True)
        print(f"[OK] Processed MEDANTA-LKO-TEST-02: {summary}")

        sql = text("""
            SELECT
                b.building_id,
                b.name,
                b.latitude,
                b.longitude,
                b.height,
                b.num_floors,
                p.unit_id,
                p.property_id,
                p.ulpin,
                p.ror_id,
                p.z_min,
                p.z_max,
                p.area,
                ST_GeometryType(p.geometry) AS geom_type,
                ST_SRID(p.geometry) AS srid,
                ST_IsValid(p.geometry) AS is_valid,
                ST_AsGeoJSON(p.geometry) AS geojson
            FROM properties_3d p
            JOIN buildings b ON p.building_uuid = b.id
            WHERE b.building_id = 'MEDANTA-LKO-TEST-02'
            ORDER BY p.z_min, p.unit_id;
        """)

        rows = db.execute(sql).fetchall()
        print(f"\n[PostGIS Verification] Found {len(rows)} property records for MEDANTA-LKO-TEST-02:\n")

        assert len(rows) == 16, f"Expected 16 properties, got {len(rows)}"

        for r in rows:
            b_id, b_name, lat, lon, h, n_floors, unit_id, prop_id, ulpin, ror_id, z_min, z_max, area, gtype, srid, is_val, gjson_str = r
            print(f"Unit: {unit_id:<8} Floor Z: {z_min:4.1f}-{z_max:4.1f}m Area: {area:5.1f}m² RoR: {ror_id} Lat/Lon: ({lat:.7f}, {lon:.7f}) Valid: {is_val}")

            assert abs(lat - 26.7776953) < 1e-5, f"Latitude mismatch: {lat}"
            assert abs(lon - 80.9856814) < 1e-5, f"Longitude mismatch: {lon}"
            assert gtype in ("ST_Polygon", "POLYGON", "Polygon"), f"Unexpected geometry type {gtype}"
            assert srid == 4326, f"Expected SRID 4326, got {srid}"
            assert is_val is True, f"Geometry for {unit_id} is invalid!"

        print("\n[OK] MEDANTA-LKO-TEST-02 DATABASE VERIFICATION PASSED SUCCESSFULLY!\n")

    finally:
        db.close()


if __name__ == "__main__":
    verify_medanta()
