# 3D ULPIN Generation & Vertical Property Mapping System

> **SIH 2026 — Problem Statement 26011**

A technically credible, working end-to-end prototype demonstrating how existing 2D cadastral records can be extended into a 3D/volumetric cadastral system for urban properties.

## Concept

```
Existing 2D Cadastral Data + RoR
            ↓
    Our 3D Processing System
            ↓
  3D Property Volumes + 3D ULPIN
            ↓
   Interactive 3D Cadastral Viewer
```

## Quick Start (Milestone 1 — Frontend Prototype)

```bash
cd frontend
npm install
npm run dev
```

> **Note:** For terrain visualization, obtain a free Cesium Ion token at [cesium.com/ion](https://cesium.com/ion) and add it to `frontend/.env`:
> ```
> VITE_CESIUM_ION_TOKEN=your_token_here
> ```
> The application works without a token (ellipsoid fallback).

## Project Structure

```
├── frontend/          # React + Vite + Tailwind + CesiumJS
├── backend/           # FastAPI (Milestone 2+)
├── data/sample/       # Synthetic demo data
└── README.md
```

## Architecture

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + Tailwind CSS | Dashboard UI |
| 3D Viewer | CesiumJS (via Resium) | Geographic 3D visualization |
| Backend | FastAPI (M2+) | REST API |
| Database | PostgreSQL + PostGIS (M2+) | Spatial data store |
| AI | YOLO + PyTorch (M4+) | Building extraction |
| Geospatial | GDAL, GeoPandas, PDAL (M4+) | Data processing |

## Data Disclaimer

> ⚠️ **All property, ownership, and cadastral data displayed in this application is synthetic demonstration data.**
> No real government records are used or implied.
> Geographic context (New Delhi, India) is used solely for realistic 3D visualization.

## Milestones

| # | Scope | Status |
|---|---|---|
| M1 | React + CesiumJS + Sample Data Dashboard | 🔄 In Progress |
| M2 | FastAPI + PostgreSQL/PostGIS | Planned |
| M3 | Full Domain Model (Parcel→Building→Floor→Property→ULPIN→RoR) | Planned |
| M4 | Drone + YOLO + LiDAR + Height/Floor Processing | Planned |
| M5 | Underground Assets + Topology Validation + Integration | Planned |

## License

Academic / Hackathon prototype — SIH 2026
