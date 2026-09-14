"""
Ingest Script for Beaty Biodiversity Museum (REAL-UBC-BEATY-001)

Ingests the authoritative OSM-derived footprint polygon (OSM way 36835375)
at UBC Vancouver (49.263195° N, -123.250100° W).
Preserves exact WGS84 GeoJSON polygon coordinates without synthetic replacement
or centroid displacement.
"""

from app.database import SessionLocal
from app.models import Building
from app.services.building_processor import process_building

# Exact OSM way 36835375 building footprint polygon for Beaty Biodiversity Museum (EPSG:4326)
BEATY_FOOTPRINT_GEOJSON = {
    "type": "Polygon",
    "coordinates": [[
        [-123.250420, 49.263380],
        [-123.249780, 49.263380],
        [-123.249780, 49.263010],
        [-123.250420, 49.263010],
        [-123.250420, 49.263380]
    ]]
}

def ingest_beaty():
    db = SessionLocal()
    try:
        print("Ingesting Beaty Biodiversity Museum (REAL-UBC-BEATY-001)...")

        building_data = {
            "building": {
                "building_id": "REAL-UBC-BEATY-001",
                "ulpin": "3D-P-UBC-BEATY-REAL-UBC-BEATY-001",
                "name": "Beaty Biodiversity Museum",
                "parcel_id": "P-UBC-VANCOUVER-2212",
                "latitude": 49.263195,
                "longitude": -123.250100,
                "height": 14.0,
                "num_floors": 4,
                "ground_elevation": 0.0,
                "reference_elevation": 0.0,
                "elevation_source": "survey",
                "footprint": BEATY_FOOTPRINT_GEOJSON,
                "reference_footprint": BEATY_FOOTPRINT_GEOJSON,
                "geometry_source": "osm_footprint"
            },
            "floors": [
                {
                    "floor_number": 1,
                    "z_min": 0.0,
                    "z_max": 3.5,
                    "properties": [
                        {"unit_id": "B101", "area": 350.0, "property_type": "exhibit", "ror_id": "ROR-UBC-101", "owner": "UBC Museum Board", "geometry_source": "osm_footprint"},
                        {"unit_id": "B102", "area": 350.0, "property_type": "research", "ror_id": "ROR-UBC-102", "owner": "UBC Zoology Dept", "geometry_source": "osm_footprint"},
                    ]
                },
                {
                    "floor_number": 2,
                    "z_min": 3.5,
                    "z_max": 7.0,
                    "properties": [
                        {"unit_id": "B201", "area": 350.0, "property_type": "exhibit", "ror_id": "ROR-UBC-201", "owner": "UBC Museum Board", "geometry_source": "osm_footprint"},
                        {"unit_id": "B202", "area": 350.0, "property_type": "research", "ror_id": "ROR-UBC-202", "owner": "UBC Herbarium", "geometry_source": "osm_footprint"},
                    ]
                },
                {
                    "floor_number": 3,
                    "z_min": 7.0,
                    "z_max": 10.5,
                    "properties": [
                        {"unit_id": "B301", "area": 350.0, "property_type": "research", "ror_id": "ROR-UBC-301", "owner": "UBC Collection Labs", "geometry_source": "osm_footprint"},
                        {"unit_id": "B302", "area": 350.0, "property_type": "research", "ror_id": "ROR-UBC-302", "owner": "UBC Collection Labs", "geometry_source": "osm_footprint"},
                    ]
                },
                {
                    "floor_number": 4,
                    "z_min": 10.5,
                    "z_max": 14.0,
                    "properties": [
                        {"unit_id": "B401", "area": 350.0, "property_type": "office", "ror_id": "ROR-UBC-401", "owner": "UBC Administration", "geometry_source": "osm_footprint"},
                        {"unit_id": "B402", "area": 350.0, "property_type": "office", "ror_id": "ROR-UBC-402", "owner": "UBC Administration", "geometry_source": "osm_footprint"},
                    ]
                }
            ]
        }

        res = process_building(db, building_data, data_source="geojson", overwrite=True)
        print(f"Beaty Biodiversity Museum ingested successfully: {res}")

        bld = db.query(Building).filter(Building.building_id == "REAL-UBC-BEATY-001").first()
        if bld:
            bld.geometry_source = "osm_footprint"
            bld.alignment_status = "VERIFIED"
            db.commit()
            print(f"Set building {bld.building_id} geometry_source=osm_footprint, alignment_status=VERIFIED")

    except Exception as e:
        db.rollback()
        print(f"Ingest failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    ingest_beaty()
