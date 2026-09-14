import { useEffect, useRef, useCallback } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PLYLoader } from "three/addons/loaders/PLYLoader.js";

export default function PointCloudCanvas({
  sampleData,
  classifiedData,
  extractedBuilding,
  scanVisibility,
  showAxes = true,
  showScanners = true,
  pointSize = 1.5,
  showRawCloud = true,
  showGroundPoints = false,
  showNonGroundPoints = false,
  showBuildingPoints = false,
  showFootprint = true,
  meshUrl = null,
  showMesh = true,
  showMeshWireframe = false,
  meshOpacity = 0.75,
  activePreset = "fit",
  onCameraInfoChange = null,
}) {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const animFrameRef = useRef(null);

  const scanGroupsRef = useRef([]);
  const scannerGroupRef = useRef(null);
  const axesGroupRef = useRef(null);
  const gridGroupRef = useRef(null);
  const activePresetRef = useRef(activePreset);
  const prevPresetRef = useRef(activePreset);
  const modelCenterRef = useRef(new THREE.Vector3());

  const debugGroupsRef = useRef({
    ground: null,
    nonGround: null,
    building: null,
    footprint: null,
    meshSolid: null,
    meshWire: null,
  });

  activePresetRef.current = activePreset;

  // ── Helper to calculate bounding box & sphere of all visible content ──
  const calculateVisibleBounds = useCallback(() => {
    if (sceneRef.current) {
      sceneRef.current.updateMatrixWorld(true);
    }

    const box = new THREE.Box3();
    let hasObjects = false;

    if (sceneRef.current) {
      sceneRef.current.traverse((obj) => {
        if (!obj.visible) return;
        // Ignore helpers, grid, lights
        if (
          obj === gridGroupRef.current ||
          obj === axesGroupRef.current ||
          obj.isLight ||
          obj.type === "GridHelper"
        ) {
          return;
        }

        if (obj.isPoints || obj.isMesh || obj.isLineSegments || obj.isLineLoop) {
          if (obj.geometry) {
            if (!obj.geometry.boundingBox) {
              obj.geometry.computeBoundingBox();
            }
            if (obj.geometry.boundingBox && !obj.geometry.boundingBox.isEmpty()) {
              const objBox = obj.geometry.boundingBox.clone();
              objBox.applyMatrix4(obj.matrixWorld);
              box.union(objBox);
              hasObjects = true;
            }
          }
        }
      });
    }

    // Fallback if no visible geometry found or initial load
    if (!hasObjects || box.isEmpty()) {
      const b = sampleData?.coordinate_bounds || {
        x_min: -30, x_max: 30, y_min: -30, y_max: 30, z_min: -5, z_max: 20,
      };
      box.min.set(b.x_min, b.z_min, -b.y_max);
      box.max.set(b.x_max, b.z_max, -b.y_min);
    }

    const center = new THREE.Vector3();
    box.getCenter(center);
    modelCenterRef.current.copy(center);

    const sphere = new THREE.Sphere();
    box.getBoundingSphere(sphere);
    const radius = Math.max(sphere.radius, 5);

    return { box, center, radius };
  }, [sampleData]);

  // ── Report camera debug info to parent component ──
  const reportCameraInfo = useCallback((presetName = activePresetRef.current) => {
    if (!cameraRef.current || !controlsRef.current || !onCameraInfoChange) return;
    const cam = cameraRef.current.position;
    const tgt = controlsRef.current.target;
    const center = modelCenterRef.current;

    // Convert Three.js coordinates (X, Y, Z) back to Local Coordinates (X_loc, Y_loc, Z_loc):
    // Three.js X = Local X
    // Three.js Y = Local Z (Elevation)
    // Three.js Z = -Local Y  =>  Local Y = -Three.js Z
    onCameraInfoChange({
      cameraPosition: {
        x: cam.x.toFixed(2),
        y: (-cam.z).toFixed(2),
        z: cam.y.toFixed(2),
      },
      controlsTarget: {
        x: tgt.x.toFixed(2),
        y: (-tgt.z).toFixed(2),
        z: tgt.y.toFixed(2),
      },
      modelCenter: {
        x: center.x.toFixed(2),
        y: (-center.z).toFixed(2),
        z: center.y.toFixed(2),
      },
      activeView: (presetName || "FIT").toUpperCase(),
    });
  }, [onCameraInfoChange]);

  // ── Preset camera application ──
  const applyPreset = useCallback((preset) => {
    if (!cameraRef.current || !controlsRef.current) return;
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    const { center, radius } = calculateVisibleBounds();

    const fovRad = (camera.fov * Math.PI) / 180;
    const aspect = camera.aspect || 1.0;
    const distV = radius / Math.sin(fovRad / 2);
    const distH = radius / Math.sin(Math.atan(Math.tan(fovRad / 2) * aspect));
    const dist = Math.max(distV, distH) * 1.35;

    // CRITICAL: Disable OrbitControls damping during preset jump so damping doesn't snap position back!
    const wasDamping = controls.enableDamping;
    controls.enableDamping = false;

    controls.target.copy(center);

    switch (preset) {
      case "top":
        // Looking vertically downward along +Z local (+Y Three.js)
        camera.up.set(0, 0, -1); // North (+Y local) points Up on screen
        camera.position.set(center.x, center.y + dist * 1.3, center.z + 0.01);
        break;

      case "front":
        // Looking horizontally towards center along Local Y (Three.js Z axis)
        camera.up.set(0, 1, 0);
        camera.position.set(center.x, center.y + dist * 0.08, center.z + dist * 1.3);
        break;

      case "side":
        // Looking horizontally towards center along perpendicular Local X (Three.js X axis)
        camera.up.set(0, 1, 0);
        camera.position.set(center.x + dist * 1.3, center.y + dist * 0.08, center.z);
        break;

      case "fit":
      default:
        // Isometric perspective view
        camera.up.set(0, 1, 0);
        camera.position.set(center.x + dist * 0.75, center.y + dist * 0.55, center.z + dist * 0.75);
        break;
    }

    camera.lookAt(center);

    // Synchronize OrbitControls internal spherical state to new camera position & target
    controls.update();

    // Re-enable damping for smooth mouse dragging
    controls.enableDamping = wasDamping;

    if (rendererRef.current && sceneRef.current) {
      rendererRef.current.render(sceneRef.current, camera);
    }
    reportCameraInfo(preset);
  }, [calculateVisibleBounds, reportCameraInfo]);

  // Expose global callback for legacy button clicks & parent triggers
  useEffect(() => {
    window.__lidarCamPreset = (preset) => {
      applyPreset(preset);
    };
    return () => {
      delete window.__lidarCamPreset;
    };
  }, [applyPreset]);

  // Trigger camera preset when activePreset prop changes
  useEffect(() => {
    if (prevPresetRef.current !== activePreset) {
      prevPresetRef.current = activePreset;
      applyPreset(activePreset);
    }
  }, [activePreset, applyPreset]);

  // ── 1. MOUNT: Initialize persistent Three.js Scene, Camera, Renderer, Controls ──
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    container.innerHTML = "";

    const w = container.clientWidth || container.offsetWidth || 800;
    const h = container.clientHeight || container.offsetHeight || 600;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    sceneRef.current = scene;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);
    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.9);
    dirLight1.position.set(50, 80, 40);
    scene.add(dirLight1);
    const dirLight2 = new THREE.DirectionalLight(0x8899bb, 0.4);
    dirLight2.position.set(-30, 20, -50);
    scene.add(dirLight2);

    // Camera
    const camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 2000);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.domElement.style.touchAction = "none";
    renderer.domElement.style.outline = "none";
    renderer.domElement.style.display = "block";
    renderer.domElement.tabIndex = 1;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableRotate = true;
    controls.enableZoom = true;
    controls.enablePan = true;
    controls.screenSpacePanning = true;
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 1.0;
    controls.panSpeed = 0.8;
    controls.zoomSpeed = 1.2;
    controlsRef.current = controls;

    // Listen for manual orbit / pan / zoom changes
    controls.addEventListener("change", () => {
      reportCameraInfo("ORBIT");
    });

    // Animation Loop
    function animate() {
      animFrameRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();

    // Resize Listener
    const onResize = () => {
      if (!containerRef.current || !cameraRef.current || !rendererRef.current) return;
      const nw = containerRef.current.clientWidth;
      const nh = containerRef.current.clientHeight;
      if (nw === 0 || nh === 0) return;
      cameraRef.current.aspect = nw / nh;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(nw, nh);
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement) renderer.domElement.remove();
    };
  }, []); // Mounts ONLY ONCE

  // ── 2. DATA UPDATE: Raw Sampled Point Cloud ──
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !sampleData) return;

    // Clear old scan groups
    scanGroupsRef.current.forEach((g) => g && scene.remove(g));
    scanGroupsRef.current = [];

    const scanGroups = [];
    const scans = sampleData?.scans || [];
    for (const scan of scans) {
      const pts = scan.points || [];
      if (pts.length === 0) {
        scanGroups.push(null);
        continue;
      }

      const isFlat = typeof pts[0] === "number";
      const numPoints = isFlat ? Math.floor(pts.length / 6) : pts.length;

      const positions = new Float32Array(numPoints * 3);
      const colors = new Float32Array(numPoints * 3);

      if (isFlat) {
        for (let i = 0; i < numPoints; i++) {
          const base = i * 6;
          const x = pts[base], y = pts[base + 1], z = pts[base + 2];
          const r = pts[base + 3], g = pts[base + 4], b = pts[base + 5];

          positions[i * 3] = x;
          positions[i * 3 + 1] = z;
          positions[i * 3 + 2] = -y;

          colors[i * 3] = r / 255;
          colors[i * 3 + 1] = g / 255;
          colors[i * 3 + 2] = b / 255;
        }
      }

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

      const material = new THREE.PointsMaterial({
        size: pointSize || 1.5,
        vertexColors: true,
        sizeAttenuation: true,
      });

      const pointCloud = new THREE.Points(geometry, material);
      pointCloud.visible = showRawCloud;
      scene.add(pointCloud);
      scanGroups.push(pointCloud);
    }
    scanGroupsRef.current = scanGroups;

    // Scanner position markers
    if (scannerGroupRef.current) scene.remove(scannerGroupRef.current);
    const scannerGroup = new THREE.Group();
    const scannerPositions = sampleData?.scanner_positions || [];
    for (const sp of scannerPositions) {
      const [sx, sy, sz] = sp.position_m;
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(0.4, 12, 8),
        new THREE.MeshBasicMaterial({ color: 0xff6b35 })
      );
      marker.position.set(sx, sz, -sy);
      scannerGroup.add(marker);
    }
    scannerGroup.visible = showScanners;
    scene.add(scannerGroup);
    scannerGroupRef.current = scannerGroup;

    // Axes & Grid helpers
    const bounds = sampleData?.coordinate_bounds || {
      x_min: -50, x_max: 50, y_min: -50, y_max: 50, z_min: -5, z_max: 25,
    };
    const cx = (bounds.x_min + bounds.x_max) / 2;
    const cy = (bounds.y_min + bounds.y_max) / 2;
    const dx = bounds.x_max - bounds.x_min;
    const dy = bounds.y_max - bounds.y_min;
    const dz = bounds.z_max - bounds.z_min;
    const maxSpan = Math.max(dx, dy, dz) || 50;

    if (axesGroupRef.current) scene.remove(axesGroupRef.current);
    const axesGroup = new THREE.Group();
    const xLen = Math.max(20, dx * 0.6);
    axesGroup.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0), new THREE.Vector3(xLen,0,0)]),
      new THREE.LineBasicMaterial({ color: 0xff4444, linewidth: 2 })
    ));
    const yLen = Math.max(20, dy * 0.6);
    axesGroup.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0), new THREE.Vector3(0,0,-yLen)]),
      new THREE.LineBasicMaterial({ color: 0x44ff44, linewidth: 2 })
    ));
    const zLen = Math.max(20, dz * 0.6);
    axesGroup.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0), new THREE.Vector3(0,zLen,0)]),
      new THREE.LineBasicMaterial({ color: 0x4488ff, linewidth: 2 })
    ));
    axesGroup.visible = showAxes;
    scene.add(axesGroup);
    axesGroupRef.current = axesGroup;

    if (gridGroupRef.current) scene.remove(gridGroupRef.current);
    const grid = new THREE.GridHelper(Math.ceil(maxSpan * 1.2), 40, 0x1e293b, 0x1e293b);
    grid.position.set(cx, bounds.z_min, -cy);
    scene.add(grid);
    gridGroupRef.current = grid;

    // Apply initial fit view on sampleData load
    applyPreset("fit");
  }, [sampleData]);

  // ── 3. DATA UPDATE: Classified Point Clouds & Extracted Footprint ──
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    const db = debugGroupsRef.current;
    if (db.ground) scene.remove(db.ground);
    if (db.nonGround) scene.remove(db.nonGround);
    if (db.building) scene.remove(db.building);
    if (db.footprint) scene.remove(db.footprint);

    const makeDebugCloud = (flatPts, customColor = null) => {
      if (!flatPts || flatPts.length === 0) return null;
      const n = Math.floor(flatPts.length / 6);
      const pos = new Float32Array(n * 3);
      const col = new Float32Array(n * 3);

      for (let i = 0; i < n; i++) {
        const b = i * 6;
        pos[i * 3] = flatPts[b];
        pos[i * 3 + 1] = flatPts[b + 2];
        pos[i * 3 + 2] = -flatPts[b + 1];

        if (customColor) {
          col[i * 3] = customColor[0];
          col[i * 3 + 1] = customColor[1];
          col[i * 3 + 2] = customColor[2];
        } else {
          col[i * 3] = flatPts[b + 3] / 255;
          col[i * 3 + 1] = flatPts[b + 4] / 255;
          col[i * 3 + 2] = flatPts[b + 5] / 255;
        }
      }

      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
      const mat = new THREE.PointsMaterial({
        size: (pointSize || 1.5) * 1.2,
        vertexColors: true,
        sizeAttenuation: true,
      });
      return new THREE.Points(geo, mat);
    };

    if (classifiedData) {
      db.ground = makeDebugCloud(classifiedData.ground_points, [0.55, 0.63, 0.35]);
      if (db.ground) { db.ground.visible = showGroundPoints; scene.add(db.ground); }

      db.nonGround = makeDebugCloud(classifiedData.non_ground_points, [0.22, 0.74, 0.97]);
      if (db.nonGround) { db.nonGround.visible = showNonGroundPoints; scene.add(db.nonGround); }

      db.building = makeDebugCloud(classifiedData.selected_building_points, [0.93, 0.28, 0.60]);
      if (db.building) { db.building.visible = showBuildingPoints; scene.add(db.building); }
    }

    // Footprint
    const ftInfo = extractedBuilding?.footprint || classifiedData?.extracted_building?.footprint;
    const bounds = sampleData?.coordinate_bounds || { z_min: -5 };
    const groundZ = extractedBuilding?.elevation?.ground_z ?? classifiedData?.extracted_building?.elevation?.ground_z ?? bounds.z_min;
    const heightM = extractedBuilding?.dimensions?.height_m ?? classifiedData?.extracted_building?.dimensions?.height_m ?? 6.0;

    if (ftInfo && ftInfo.coordinates && ftInfo.coordinates.length > 0) {
      const footprintGroup = new THREE.Group();
      const polyCoords = ftInfo.coordinates;
      const ptsBottom = [];
      const ptsTop = [];

      for (const [lx, ly] of polyCoords) {
        ptsBottom.push(new THREE.Vector3(lx, groundZ, -ly));
        ptsTop.push(new THREE.Vector3(lx, groundZ + heightM, -ly));
      }

      const lineMat = new THREE.LineBasicMaterial({ color: 0xfbbf24, linewidth: 3 });
      footprintGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ptsBottom), lineMat));
      footprintGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ptsTop), lineMat));

      for (let k = 0; k < ptsBottom.length - 1; k++) {
        footprintGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([ptsBottom[k], ptsTop[k]]), lineMat));
      }

      footprintGroup.visible = showFootprint;
      scene.add(footprintGroup);
      db.footprint = footprintGroup;
    }
  }, [classifiedData, extractedBuilding]);

  // ── 4. DATA UPDATE: Reconstructed PLY Mesh ──
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !meshUrl) return;

    const loader = new PLYLoader();
    loader.load(
      meshUrl,
      (geometry) => {
        geometry.computeVertexNormals();

        // Solid mesh
        const solidMat = new THREE.MeshStandardMaterial({
          color: 0xd4a574,
          metalness: 0.1,
          roughness: 0.7,
          transparent: true,
          opacity: meshOpacity,
          side: THREE.DoubleSide,
          depthWrite: true,
        });
        const solidMesh = new THREE.Mesh(geometry, solidMat);
        solidMesh.rotation.x = -Math.PI / 2;
        solidMesh.visible = showMesh;

        if (debugGroupsRef.current.meshSolid) scene.remove(debugGroupsRef.current.meshSolid);
        scene.add(solidMesh);
        debugGroupsRef.current.meshSolid = solidMesh;

        // Wireframe
        const wireGeo = new THREE.WireframeGeometry(geometry);
        const wireMat = new THREE.LineBasicMaterial({
          color: 0x38bdf8,
          transparent: true,
          opacity: 0.4,
        });
        const wireLines = new THREE.LineSegments(wireGeo, wireMat);
        wireLines.rotation.x = -Math.PI / 2;
        wireLines.visible = showMeshWireframe;

        if (debugGroupsRef.current.meshWire) scene.remove(debugGroupsRef.current.meshWire);
        scene.add(wireLines);
        debugGroupsRef.current.meshWire = wireLines;
      },
      undefined,
      (err) => console.warn("PLY mesh load failed:", err)
    );
  }, [meshUrl]);

  // ── 5. LAYER VISIBILITY UPDATES ──
  useEffect(() => {
    const groups = scanGroupsRef.current;
    if (!groups) return;
    for (let i = 0; i < groups.length; i++) {
      if (groups[i]) {
        groups[i].visible = showRawCloud && (scanVisibility ? scanVisibility[i] !== false : true);
      }
    }
  }, [scanVisibility, showRawCloud]);

  useEffect(() => {
    const db = debugGroupsRef.current;
    if (!db) return;
    if (db.ground) db.ground.visible = showGroundPoints;
    if (db.nonGround) db.nonGround.visible = showNonGroundPoints;
    if (db.building) db.building.visible = showBuildingPoints;
    if (db.footprint) db.footprint.visible = showFootprint;
    if (db.meshSolid) {
      db.meshSolid.visible = showMesh;
      if (db.meshSolid.material) db.meshSolid.material.opacity = meshOpacity;
    }
    if (db.meshWire) db.meshWire.visible = showMeshWireframe;
  }, [showGroundPoints, showNonGroundPoints, showBuildingPoints, showFootprint, showMesh, showMeshWireframe, meshOpacity]);

  useEffect(() => {
    if (axesGroupRef.current) axesGroupRef.current.visible = showAxes;
    if (scannerGroupRef.current) scannerGroupRef.current.visible = showScanners;
  }, [showAxes, showScanners]);

  return (
    <div
      ref={containerRef}
      className="pointcloud-canvas-container"
      style={{ width: "100%", height: "100%", position: "relative" }}
    />
  );
}
