"""
Seed DEMO_DATA into PostgreSQL.

Seeds the existing frontend sample data into PostgreSQL so the
database-backed API can serve it. Safe to run multiple times —
skips records that already exist (checks by parcel_id/building_id etc.).

This is seeded data from the M1 prototype. All records are clearly
marked with source = "DEMO_DATA" or "synthetic_demo".
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from app.database import SessionLocal
from app.models import Parcel, Building, Floor, Property3D, RoR


# ── Sample coordinates (New Delhi area, matching frontend DEMO_DATA) ──
SAMPLE_CENTER_LON = 77.2090
SAMPLE_CENTER_LAT = 28.6139

# Parcel polygon (simplified rectangle around sample center)
PARCEL_WKT = (
    f"POLYGON(("
    f"{SAMPLE_CENTER_LON - 0.001} {SAMPLE_CENTER_LAT - 0.001},"
    f"{SAMPLE_CENTER_LON + 0.001} {SAMPLE_CENTER_LAT - 0.001},"
    f"{SAMPLE_CENTER_LON + 0.001} {SAMPLE_CENTER_LAT + 0.001},"
    f"{SAMPLE_CENTER_LON - 0.001} {SAMPLE_CENTER_LAT + 0.001},"
    f"{SAMPLE_CENTER_LON - 0.001} {SAMPLE_CENTER_LAT - 0.001}"
    f"))"
)

# Building footprint (smaller rectangle within parcel)
BUILDING_WKT = (
    f"POLYGON(("
    f"{SAMPLE_CENTER_LON - 0.0005} {SAMPLE_CENTER_LAT - 0.0005},"
    f"{SAMPLE_CENTER_LON + 0.0005} {SAMPLE_CENTER_LAT - 0.0005},"
    f"{SAMPLE_CENTER_LON + 0.0005} {SAMPLE_CENTER_LAT + 0.0005},"
    f"{SAMPLE_CENTER_LON - 0.0005} {SAMPLE_CENTER_LAT + 0.0005},"
    f"{SAMPLE_CENTER_LON - 0.0005} {SAMPLE_CENTER_LAT - 0.0005}"
    f"))"
)


def seed():
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.execute(
            text("SELECT COUNT(*) FROM parcels WHERE parcel_id = 'P001'")
        ).scalar()
        if existing > 0:
            print("DEMO_DATA already seeded. Skipping.")
            return

        print("Seeding DEMO_DATA into PostgreSQL...")

        # ── Parcel ──
        parcel = Parcel(
            parcel_id="P001",
            survey_number="SV-2024-001",
            geometry_2d=f"SRID=4326;{PARCEL_WKT}",
            area=500.0,
            crs_source="EPSG:4326",
            source="DEMO_DATA",
        )
        db.add(parcel)
        db.flush()  # Get parcel.id for FK references

        # ── Building ──
        building = Building(
            building_id="B01",
            name="Demo Building Alpha",
            parcel_uuid=parcel.id,
            latitude=SAMPLE_CENTER_LAT,
            longitude=SAMPLE_CENTER_LON,
            height=12.0,
            num_floors=4,
            ground_elevation=0.0,
            source="DEMO_DATA",
        )
        db.add(building)
        db.flush()

        # ── RoR Records ──
        ror_data = [
            {"ror_id": "ROR001", "owner": "Demo Owner A", "land_use": "Residential", "rights": "Freehold", "area": 120.0},
            {"ror_id": "ROR002", "owner": "Demo Owner B", "land_use": "Commercial", "rights": "Leasehold", "area": 100.0},
            {"ror_id": "ROR003", "owner": "Demo Owner C", "land_use": "Residential", "rights": "Freehold", "area": 110.0},
            {"ror_id": "ROR004", "owner": "Demo Owner D", "land_use": "Mixed Use", "rights": "Freehold", "area": 130.0},
        ]
        for rd in ror_data:
            ror = RoR(
                ror_id=rd["ror_id"],
                parcel_uuid=parcel.id,
                owner_name=rd["owner"],
                area=rd["area"],
                land_use=rd["land_use"],
                rights=rd["rights"],
                source="synthetic_demo",
            )
            db.add(ror)

        # ── Floors ──
        floors = []
        floor_defs = [
            {"floor_id": "F01", "number": 1, "z_min": 0, "z_max": 3},
            {"floor_id": "F02", "number": 2, "z_min": 3, "z_max": 6},
            {"floor_id": "F03", "number": 3, "z_min": 6, "z_max": 9},
            {"floor_id": "F04", "number": 4, "z_min": 9, "z_max": 12},
        ]
        for fd in floor_defs:
            floor = Floor(
                floor_id=fd["floor_id"],
                building_uuid=building.id,
                floor_number=fd["number"],
                z_min=fd["z_min"],
                z_max=fd["z_max"],
                elevation_source="DEMO_DATA",
            )
            db.add(floor)
            floors.append(floor)
        db.flush()

        # ── Properties ──
        prop_defs = [
            {"prop_id": "PROP001", "ulpin": "3D-P001-B01-F01-U101", "floor_idx": 0, "unit": "U101", "ror": "ROR001", "type": "residential"},
            {"prop_id": "PROP002", "ulpin": "3D-P001-B01-F02-U201", "floor_idx": 1, "unit": "U201", "ror": "ROR002", "type": "commercial"},
            {"prop_id": "PROP003", "ulpin": "3D-P001-B01-F03-U301", "floor_idx": 2, "unit": "U301", "ror": "ROR003", "type": "residential"},
            {"prop_id": "PROP004", "ulpin": "3D-P001-B01-F04-U401", "floor_idx": 3, "unit": "U401", "ror": "ROR004", "type": "mixed"},
        ]
        for pd_item in prop_defs:
            prop = Property3D(
                property_id=pd_item["prop_id"],
                ulpin=pd_item["ulpin"],
                building_uuid=building.id,
                floor_uuid=floors[pd_item["floor_idx"]].id,
                unit_id=pd_item["unit"],
                property_type=pd_item["type"],
                area=120.0,
                geometry=f"SRID=4326;{BUILDING_WKT}",
                z_min=floors[pd_item["floor_idx"]].z_min,
                z_max=floors[pd_item["floor_idx"]].z_max,
                ror_id=pd_item["ror"],
                data_source="DEMO_DATA",
                geometry_source="building_footprint",
                verification_status="unverified",
            )
            db.add(prop)

        db.commit()
        print("DEMO_DATA seeded successfully:")
        print("  1 parcel (P001)")
        print("  1 building (B01)")
        print("  4 floors (F01-F04)")
        print("  4 properties (PROP001-PROP004)")
        print("  4 RoR records (ROR001-ROR004)")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
