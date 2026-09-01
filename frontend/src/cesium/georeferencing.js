/**
 * Georeferencing Module
 *
 * Provides a reusable, standardized geographic transformation system for:
 * - Anchoring 3D models (GLB, GLTF, CAD, BIM, photogrammetry)
 * - Computing geographic transformation matrices (lat, lon, elevation, heading, pitch, roll, scale)
 * - Georeferencing footprint geometries and bounding spheres
 * - Converting WGS84 (EPSG:4326) coordinates to local ENU (East-North-Up) Cartesian frames
 */

import * as Cesium from "cesium";

export class Georeferencer {
  /**
   * Convert WGS84 (lat, lon, elevation) to Cesium Cartesian3 point.
   */
  static toCartesian(latitude, longitude, elevation = 0.0) {
    if (latitude == null || longitude == null) return null;
    return Cesium.Cartesian3.fromDegrees(longitude, latitude, elevation);
  }

  /**
   * Compute a 4x4 local East-North-Up (ENU) fixed-frame transformation matrix
   * anchored at (latitude, longitude, elevation) with orientation and scale.
   *
   * Reusable for 3D GLB/GLTF, BIM, CAD, and drone photogrammetry models.
   *
   * @param {Object} params
   * @param {number} params.latitude - Latitude in degrees (WGS84)
   * @param {number} params.longitude - Longitude in degrees (WGS84)
   * @param {number} [params.elevation=0] - Elevation in meters above terrain/ellipsoid
   * @param {number} [params.heading=0] - Heading angle in degrees (yaw)
   * @param {number} [params.pitch=0] - Pitch angle in degrees
   * @param {number} [params.roll=0] - Roll angle in degrees
   * @param {Object} [params.scale={x:1, y:1, z:1}] - Scale factors
   * @returns {Cesium.Matrix4} 4x4 transformation matrix
   */
  static toTransformMatrix({
    latitude,
    longitude,
    elevation = 0.0,
    heading = 0.0,
    pitch = 0.0,
    roll = 0.0,
    scale = { x: 1, y: 1, z: 1 },
  }) {
    const origin = Cesium.Cartesian3.fromDegrees(longitude, latitude, elevation);
    const hpr = new Cesium.HeadingPitchRoll(
      Cesium.Math.toRadians(heading),
      Cesium.Math.toRadians(pitch),
      Cesium.Math.toRadians(roll)
    );

    // Compute ENU local transform matrix
    const matrix = Cesium.Transforms.headingPitchRollToFixedFrame(origin, hpr);

    // Apply scale if non-unit
    if (scale.x !== 1 || scale.y !== 1 || scale.z !== 1) {
      const scaleMatrix = Cesium.Matrix4.fromScale(
        new Cesium.Cartesian3(scale.x, scale.y, scale.z)
      );
      Cesium.Matrix4.multiply(matrix, scaleMatrix, matrix);
    }

    return matrix;
  }

  /**
   * Calculate exact bounding sphere for camera fly-to and collision bounding.
   *
   * @param {Array<Cesium.Cartesian3>} positions - Array of Cartesian3 points
   * @returns {Cesium.BoundingSphere} Computed bounding sphere
   */
  static getBoundingSphere(positions) {
    if (!positions || positions.length === 0) return null;
    return Cesium.BoundingSphere.fromPoints(positions);
  }

  /**
   * Anchor a synthetic rectangular footprint around a geographic coordinate (lat, lon).
   * Used when explicit PostGIS polygon footprint is absent.
   *
   * @param {number} latitude
   * @param {number} longitude
   * @param {number} widthMeters - East-west width
   * @param {number} depthMeters - North-south depth
   * @returns {Array<Cesium.Cartesian3>} 4 corner Cartesian3 positions
   */
  static anchorRectangularFootprint(latitude, longitude, widthMeters = 20.0, depthMeters = 20.0) {
    const metersPerDegreeLat = 111320.0;
    const metersPerDegreeLon = 111320.0 * Math.cos((latitude * Math.PI) / 180.0);

    const deltaLat = (depthMeters / 2.0) / metersPerDegreeLat;
    const deltaLon = (widthMeters / 2.0) / metersPerDegreeLon;

    const minLat = latitude - deltaLat;
    const maxLat = latitude + deltaLat;
    const minLon = longitude - deltaLon;
    const maxLon = longitude + deltaLon;

    return [
      Cesium.Cartesian3.fromDegrees(minLon, minLat),
      Cesium.Cartesian3.fromDegrees(maxLon, minLat),
      Cesium.Cartesian3.fromDegrees(maxLon, maxLat),
      Cesium.Cartesian3.fromDegrees(minLon, maxLat),
    ];
  }
}
