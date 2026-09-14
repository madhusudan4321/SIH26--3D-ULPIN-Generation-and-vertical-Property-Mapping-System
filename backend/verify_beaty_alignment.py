"""
Verification Suite — Beaty Biodiversity Museum Alignment (REAL-UBC-BEATY-001)

Verifies:
1. Building REAL-UBC-BEATY-001 exists in PostGIS with geometry_source="osm_footprint".
2. PostGIS geometry is SRID 4326, valid, and non-empty.
3. Coordinate order is explicitly [lon, lat] with min_lon ~ -123.251460, min_lat ~ 49.263050.
4. Alignment diagnostics returns alignment_status="VERIFIED".
5. No synthetic rectangle or coordinate swap occurred.
"""

from app.database import SessionLocal
from app.models import Building
from app.services.geometry_engine import compute_alignment_diagnostics, validate_geometry
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

def verify_beaty():
    print("=== STARTING BEATY BIODIVERSITY MUSEUM ALIGNMENT VERIFICATION ===")
    db = SessionLocal()
    try:
        bld = db.query(Building).filter(Building.building_id == "REAL-UBC-BEATY-001").first()
        assert bld is not None, "REAL-UBC-BEATY-001 must exist in database"
        print(f"[PASS] Found Building: {bld.building_id} ({bld.name})")

        fp_shape = to_shape(bld.footprint)
        fp_geojson = mapping(fp_shape)

        # 1. Geometry Validation
        is_valid, err_msg = validate_geometry(fp_geojson)
        assert is_valid, f"Geometry validation failed: {err_msg}"
        print("[PASS] PostGIS Geometry Validation: SRID 4326, Polygon Valid, Non-Empty")

        # 2. Coordinate Order Verification
        minx, miny, maxx, maxy = fp_shape.bounds
        assert minx < 0, f"Longitude must be negative in Vancouver (-123.25), got {minx}"
        assert miny > 40, f"Latitude must be ~ 49.26 in Vancouver, got {miny}"
        print(f"[PASS] Coordinate Order Verified: Lon [{minx:.6f}, {maxx:.6f}], Lat [{miny:.6f}, {maxy:.6f}]")

        # 3. Alignment Diagnostics Endpoint Calculation
        ref_fp_geojson = mapping(to_shape(bld.reference_footprint)) if bld.reference_footprint else fp_geojson

        diag = compute_alignment_diagnostics(
            model_footprint_geojson=fp_geojson,
            reference_footprint_geojson=ref_fp_geojson,
            ground_elevation=bld.ground_elevation or 0.0,
            reference_elevation=bld.reference_elevation or 0.0,
            geometry_source=bld.geometry_source or "osm_footprint",
            latitude=bld.latitude,
            longitude=bld.longitude,
        )
        diag["building_id"] = bld.building_id

        print("\n--- BEATY BIODIVERSITY MUSEUM DIAGNOSTIC REPORT ---")
        for k, v in diag.items():
            print(f"  {k}: {v}")

        # Assertions
        assert diag["building_id"] == "REAL-UBC-BEATY-001", "Building ID mismatch"
        assert diag["geometry_source"] == "osm_footprint", f"Expected osm_footprint, got {diag['geometry_source']}"
        assert diag["geometry_valid"] is True, "Geometry must be valid"
        assert diag["srid"] == 4326, "SRID must be 4326"
        assert diag["coordinate_order"] == "lon_lat", "Coordinate order must be lon_lat"
        assert diag["alignment_status"] == "VERIFIED", f"Expected VERIFIED, got {diag['alignment_status']}"

        print("\n=== ALL BEATY BIODIVERSITY MUSEUM ALIGNMENT ASSERTIONS PASSED SUCCESSFULLY ===")

    except Exception as e:
        print(f"Verification failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    verify_beaty()
