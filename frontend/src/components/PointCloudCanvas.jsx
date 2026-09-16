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
  const modelCenterRef = useRef(new THREE.Vector3(0, 0, 0));
  const onCameraInfoChangeRef = useRef(onCameraInfoChange);

  const debugGroupsRef = useRef({
    ground: null,
    nonGround: null,
    building: null,
    footprint: null,
    meshSolid: null,
    meshWire: null,
  });

  activePresetRef.current = activePreset;
  onCameraInfoChangeRef.current = onCameraInfoChange;

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
            const b = obj.geometry.boundingBox;
            if (
              b &&
              !b.isEmpty() &&
              Number.isFinite(b.min.x) && Number.isFinite(b.min.y) && Number.isFinite(b.min.z) &&
              Number.isFinite(b.max.x) && Number.isFinite(b.max.y) && Number.isFinite(b.max.z)
            ) {
              const objBox = b.clone();
              objBox.applyMatrix4(obj.matrixWorld);
              if (
                Number.isFinite(objBox.min.x) && Number.isFinite(objBox.min.y) && Number.isFinite(objBox.min.z) &&
                Number.isFinite(objBox.max.x) && Number.isFinite(objBox.max.y) && Number.isFinite(objBox.max.z)
              ) {
                box.union(objBox);
                hasObjects = true;
              }
            }
          }
        }
      });
    }

    // Fallback if no visible geometry found or box contains non-finite values
    if (
      !hasObjects ||
      box.isEmpty() ||
      !Number.isFinite(box.min.x) || !Number.isFinite(box.min.y) || !Number.isFinite(box.min.z) ||
      !Number.isFinite(box.max.x) || !Number.isFinite(box.max.y) || !Number.isFinite(box.max.z)
    ) {
      const b = sampleData?.coordinate_bounds || {
        x_min: -50, x_max: 50, y_min: -50, y_max: 50, z_min: -10, z_max: 30,
      };
      box.min.set(
        Number.isFinite(b.x_min) ? b.x_min : -50,
        Number.isFinite(b.z_min) ? b.z_min : -10,
        Number.isFinite(b.y_max) ? -b.y_max : -50
      );
      box.max.set(
        Number.isFinite(b.x_max) ? b.x_max : 50,
        Number.isFinite(b.z_max) ? b.z_max : 30,
        Number.isFinite(b.y_min) ? -b.y_min : 50
      );
    }

    const center = new THREE.Vector3();
    box.getCenter(center);

    // Validate center values
    if (!Number.isFinite(center.x)) center.x = 0;
    if (!Number.isFinite(center.y)) center.y = 0;
    if (!Number.isFinite(center.z)) center.z = 0;

    modelCenterRef.current.copy(center);

    const sphere = new THREE.Sphere();
    box.getBoundingSphere(sphere);
    let radius = sphere.radius;
    if (!Number.isFinite(radius) || radius <= 0) {
      radius = 15;
    }
    radius = Math.max(radius, 5);

    return { box, center, radius };
  }, [sampleData]);

  // ── Report camera debug info to parent component ──
  const reportCameraInfo = useCallback((presetName = activePresetRef.current) => {
    if (!cameraRef.current || !controlsRef.current || !onCameraInfoChangeRef.current) return;
    const cam = cameraRef.current.position;
    const tgt = controlsRef.current.target;
    const center = modelCenterRef.current;

    if (
      !Number.isFinite(cam.x) || !Number.isFinite(cam.y) || !Number.isFinite(cam.z) ||
      !Number.isFinite(tgt.x) || !Number.isFinite(tgt.y) || !Number.isFinite(tgt.z)
    ) {
      return;
    }

    onCameraInfoChangeRef.current({
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
  }, []);

  // ── Preset camera application ──
  const applyPreset = useCallback((preset) => {
    if (!cameraRef.current || !controlsRef.current) return;
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    const { box, center, radius } = calculateVisibleBounds();

    const fovRad = (camera.fov * Math.PI) / 180;
    const aspect = camera.aspect || 1.0;
    const distV = radius / Math.sin(fovRad / 2);
    const distH = radius / Math.sin(Math.atan(Math.tan(fovRad / 2) * aspect));
    let dist = Math.max(distV, distH) * 1.25;

    if (!Number.isFinite(dist) || dist <= 0) dist = 25;

    // Validate center coordinates
    if (!Number.isFinite(center.x) || !Number.isFinite(center.y) || !Number.isFinite(center.z)) {
      console.error("[CAMERA DEBUG] Model center contained invalid numbers:", center);
      return;
    }

    // Disable controls damping temporarily during instant camera jump
    const wasDamping = controls.enableDamping;
    controls.enableDamping = false;

    // Update distance limits based on current model radius
    controls.minDistance = Math.max(0.5, radius * 0.05);
    controls.maxDistance = Math.max(500, radius * 20);

    // Always maintain fixed Up vector along +Y in Three.js
    camera.up.set(0, 1, 0);

    let camX = center.x;
    let camY = center.y;
    let camZ = center.z;

    const presetLower = (preset || "fit").toLowerCase();

    switch (presetLower) {
      case "top":
        // Looking straight down along Three.js +Y axis (Local +Z elevation)
        // Adding small epsilon in Z (dist * 0.001) avoids 0 cross-product lookAt degeneracy in OrbitControls
        camX = center.x;
        camY = center.y + dist * 1.3;
        camZ = center.z + dist * 0.001;
        break;

      case "front":
        // Looking horizontally along Three.js +Z axis (towards -Local Y)
        camX = center.x;
        camY = center.y + dist * 0.08;
        camZ = center.z + dist * 1.3;
        break;

      case "side":
        // Looking horizontally along Three.js +X axis (Local +X)
        camX = center.x + dist * 1.3;
        camY = center.y + dist * 0.08;
        camZ = center.z;
        break;

      case "fit":
      default:
        // Isometric 3D view
        camX = center.x + dist * 0.6;
        camY = center.y + dist * 0.45;
        camZ = center.z + dist * 0.6;
        break;
    }

    // Validate calculated camera coordinates strictly
    if (!Number.isFinite(camX) || !Number.isFinite(camY) || !Number.isFinite(camZ)) {
      console.error("[CAMERA DEBUG] Calculated camera position contained invalid numbers:", { camX, camY, camZ });
      controls.enableDamping = wasDamping;
      return;
    }

    // Assign camera position & target
    camera.position.set(camX, camY, camZ);
    controls.target.copy(center);

    // Synchronize OrbitControls state
    controls.update();
    controls.enableDamping = wasDamping;

    // Phase 8: Log camera debug information
    console.log("[CAMERA DEBUG]", {
      View: presetLower.toUpperCase(),
      "Model center": { X: center.x, Y: center.y, Z: center.z },
      Bounds: {
        minX: box.min.x, maxX: box.max.x,
        minY: box.min.y, maxY: box.max.y,
        minZ: box.min.z, maxZ: box.max.z,
      },
      Radius: radius,
      Camera: { X: camera.position.x, Y: camera.position.y, Z: camera.position.z },
      Target: { X: controls.target.x, Y: controls.target.y, Z: controls.target.z },
      Distance: dist,
    });

    if (rendererRef.current && sceneRef.current) {
      rendererRef.current.render(sceneRef.current, camera);
    }
    reportCameraInfo(presetLower);
  }, [calculateVisibleBounds, reportCameraInfo]);

  // Expose global callback for legacy button triggers
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
    camera.up.set(0, 1, 0);
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

    // Orbit Controls — Phase 4 requirements
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enabled = true;
    controls.enableRotate = true;
    controls.enableZoom = true;
    controls.enablePan = true;
    controls.screenSpacePanning = true;
    controls.enableDamping = true;
    controls.dampingFactor = 0.15;
    controls.rotateSpeed = 1.0;
    controls.panSpeed = 1.0;
    controls.zoomSpeed = 1.2;
    controls.minDistance = 0.5;
    controls.maxDistance = 2000;

    // Configure explicit mouse button mapping: LEFT=rotate, RIGHT=pan, MIDDLE=dolly
    controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    };

    controlsRef.current = controls;

    // Report camera info only when user finishes dragging/zooming (avoids 60fps React re-renders)
    controls.addEventListener("end", () => {
      reportCameraInfo("ORBIT");
    });

    // Animation Loop
    function animate() {
      animFrameRef.current = requestAnimationFrame(animate);
      if (controlsRef.current) {
        controlsRef.current.update();
      }
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
    }
    animate();

    // Focus the canvas so mouse/keyboard interactions respond immediately
    const dom = renderer.domElement;
    dom.addEventListener("pointerdown", (e) => console.log("[INPUT DEBUG] pointerdown", e.button));
    dom.addEventListener("pointermove", () => console.log("[INPUT DEBUG] pointermove"));
    dom.addEventListener("pointerup", () => console.log("[INPUT DEBUG] pointerup"));
    dom.addEventListener("wheel", () => console.log("[INPUT DEBUG] wheel"));

    requestAnimationFrame(() => {
      if (renderer.domElement) renderer.domElement.focus();
    });

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
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));

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

    // Helper for guaranteed Float32Array line geometries (prevents Unsupported buffer data format error)
    const createFloat32LineGeometry = (vector3Array) => {
      const pos = new Float32Array(vector3Array.length * 3);
      for (let i = 0; i < vector3Array.length; i++) {
        pos[i * 3] = vector3Array[i].x;
        pos[i * 3 + 1] = vector3Array[i].y;
        pos[i * 3 + 2] = vector3Array[i].z;
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      return geo;
    };

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
      createFloat32LineGeometry([new THREE.Vector3(0,0,0), new THREE.Vector3(xLen,0,0)]),
      new THREE.LineBasicMaterial({ color: 0xff4444, linewidth: 2 })
    ));
    const yLen = Math.max(20, dy * 0.6);
    axesGroup.add(new THREE.Line(
      createFloat32LineGeometry([new THREE.Vector3(0,0,0), new THREE.Vector3(0,0,-yLen)]),
      new THREE.LineBasicMaterial({ color: 0x44ff44, linewidth: 2 })
    ));
    const zLen = Math.max(20, dz * 0.6);
    axesGroup.add(new THREE.Line(
      createFloat32LineGeometry([new THREE.Vector3(0,0,0), new THREE.Vector3(0,zLen,0)]),
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

    if (rendererRef.current && cameraRef.current) {
      rendererRef.current.render(scene, cameraRef.current);
    }
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
      geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      geo.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
      const mat = new THREE.PointsMaterial({
        size: (pointSize || 1.5) * 1.2,
        vertexColors: true,
        sizeAttenuation: true,
      });
      return new THREE.Points(geo, mat);
    };

    const createFloat32LineGeometry = (vector3Array) => {
      const pos = new Float32Array(vector3Array.length * 3);
      for (let i = 0; i < vector3Array.length; i++) {
        pos[i * 3] = vector3Array[i].x;
        pos[i * 3 + 1] = vector3Array[i].y;
        pos[i * 3 + 2] = vector3Array[i].z;
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      return geo;
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
      footprintGroup.add(new THREE.LineLoop(createFloat32LineGeometry(ptsBottom), lineMat));
      footprintGroup.add(new THREE.LineLoop(createFloat32LineGeometry(ptsTop), lineMat));

      for (let k = 0; k < ptsBottom.length - 1; k++) {
        footprintGroup.add(new THREE.Line(createFloat32LineGeometry([ptsBottom[k], ptsTop[k]]), lineMat));
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
        // Sanitize all PLYLoader geometry attributes to guaranteed Float32Array / TypedArray
        if (geometry.attributes.position && !(geometry.attributes.position.array instanceof Float32Array)) {
          geometry.setAttribute(
            "position",
            new THREE.Float32BufferAttribute(new Float32Array(geometry.attributes.position.array), geometry.attributes.position.itemSize)
          );
        }
        if (geometry.attributes.normal && !(geometry.attributes.normal.array instanceof Float32Array)) {
          geometry.setAttribute(
            "normal",
            new THREE.Float32BufferAttribute(new Float32Array(geometry.attributes.normal.array), geometry.attributes.normal.itemSize)
          );
        }
        if (geometry.attributes.color && !(geometry.attributes.color.array instanceof Float32Array)) {
          geometry.setAttribute(
            "color",
            new THREE.Float32BufferAttribute(new Float32Array(geometry.attributes.color.array), geometry.attributes.color.itemSize)
          );
        }
        if (geometry.index && !(geometry.index.array instanceof Uint16Array || geometry.index.array instanceof Uint32Array)) {
          geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(geometry.index.array), 1));
        }

        console.log("[MESH GEOMETRY DEBUG]", {
          position: {
            type: geometry.attributes.position?.array?.constructor?.name,
            count: geometry.attributes.position?.count,
            itemSize: geometry.attributes.position?.itemSize,
          },
          normal: geometry.attributes.normal ? {
            type: geometry.attributes.normal?.array?.constructor?.name,
            count: geometry.attributes.normal?.count,
            itemSize: geometry.attributes.normal?.itemSize,
          } : "none",
          color: geometry.attributes.color ? {
            type: geometry.attributes.color?.array?.constructor?.name,
            count: geometry.attributes.color?.count,
            itemSize: geometry.attributes.color?.itemSize,
          } : "none",
          index: geometry.index ? {
            type: geometry.index?.array?.constructor?.name,
            count: geometry.index?.count,
            itemSize: geometry.index?.itemSize,
          } : "none",
        });

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
