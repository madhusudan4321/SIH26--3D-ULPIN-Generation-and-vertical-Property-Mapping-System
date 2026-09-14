"""
E57 Metadata Inspection Utility — Read-Only Point Cloud Audit

Utility for metadata-only inspection of E57 point cloud files (e.g. Aam Khas Bagh LiDAR).
Uses `pye57` to parse XML nodes and scan headers without reading point arrays into memory.

Output:
- Printed JSON report to stdout
- Written to backend/tools/e57_inspection_report.json
"""

import json
import os
import sys
from pathlib import Path
import pye57
import pye57.libe57 as e57lib

def get_node_value(node):
    """Safely extract string or primitive value from a libe57 node."""
    if node is None:
        return None
    try:
        ntype = node.type()
        if ntype == e57lib.NodeType.E57_STRING:
            return e57lib.StringNode(node).value()
        elif ntype == e57lib.NodeType.E57_INTEGER:
            return e57lib.IntegerNode(node).value()
        elif ntype == e57lib.NodeType.E57_FLOAT:
            return e57lib.FloatNode(node).value()
        elif ntype == e57lib.NodeType.E57_STRUCTURE:
            struct_node = e57lib.StructureNode(node)
            res = {}
            for i in range(struct_node.childCount()):
                child = struct_node.get(i)
                res[child.elementName()] = get_node_value(child)
            return res
    except Exception:
        pass
    return str(node)

def inspect_e57(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"E57 file not found: {file_path}")

    file_size_bytes = path.stat().st_size
    file_size_gb = round(file_size_bytes / (1024 ** 3), 3)

    e57 = pye57.E57(str(path))
    scan_count = e57.scan_count

    root = e57.image_file.root()

    # Extract root XML metadata
    coord_meta = ""
    if root.isDefined("coordinateMetadata"):
        coord_meta = get_node_value(root.get("coordinateMetadata")) or ""

    library_ver = ""
    if root.isDefined("e57LibraryVersion"):
        library_ver = get_node_value(root.get("e57LibraryVersion")) or ""

    creation_time = ""
    if root.isDefined("creationDateTime"):
        c_node = root.get("creationDateTime")
        if c_node.type() == e57lib.NodeType.E57_STRUCTURE:
            s_node = e57lib.StructureNode(c_node)
            if s_node.isDefined("dateTimeValue"):
                creation_time = get_node_value(s_node.get("dateTimeValue")) or ""

    scans_meta = []
    total_points = 0
    global_x_min = float("inf")
    global_x_max = float("-inf")
    global_y_min = float("inf")
    global_y_max = float("-inf")
    global_z_min = float("inf")
    global_z_max = float("-inf")

    all_attributes = set()
    has_poses = False

    for idx in range(scan_count):
        h = e57.get_header(idx)
        n_pts = h.point_count
        total_points += n_pts

        for field in h.point_fields:
            all_attributes.add(field)

        x_min, x_max = float(h.xMinimum), float(h.xMaximum)
        y_min, y_max = float(h.yMinimum), float(h.yMaximum)
        z_min, z_max = float(h.zMinimum), float(h.zMaximum)

        global_x_min = min(global_x_min, x_min)
        global_x_max = max(global_x_max, x_max)
        global_y_min = min(global_y_min, y_min)
        global_y_max = max(global_y_max, y_max)
        global_z_min = min(global_z_min, z_min)
        global_z_max = max(global_z_max, z_max)

        trans = [float(v) for v in h.translation]
        rot = [float(v) for v in h.rotation]

        if any(t != 0.0 for t in trans) or any(r != 0.0 for r in rot[1:]):
            has_poses = True

        scans_meta.append({
            "scan_index": idx,
            "guid": getattr(h, "guid", None),
            "point_count": n_pts,
            "bounds": {
                "x_min": round(x_min, 3),
                "x_max": round(x_max, 3),
                "y_min": round(y_min, 3),
                "y_max": round(y_max, 3),
                "z_min": round(z_min, 3),
                "z_max": round(z_max, 3),
            },
            "translation_m": [round(v, 4) for v in trans],
            "rotation_quaternion": [round(v, 6) for v in rot],
        })

    # Attribute categorization
    attr_list = sorted(list(all_attributes))
    attr_types = []
    if any(f in attr_list for f in ["cartesianX", "cartesianY", "cartesianZ"]):
        attr_types.append("XYZ")
    if any(f in attr_list for f in ["colorRed", "colorGreen", "colorBlue"]):
        attr_types.append("RGB")
    if "intensity" in attr_list:
        attr_types.append("intensity")
    if "rowIndex" in attr_list or "columnIndex" in attr_list:
        attr_types.append("grid_index")
    if "cartesianInvalidState" in attr_list:
        attr_types.append("invalid_state")

    # Determine coordinate system type
    coord_sys_type = "unknown"
    if not coord_meta or coord_meta.strip() == "":
        coord_sys_type = "local"
    elif "EPSG" in coord_meta.upper() or "UTM" in coord_meta.upper() or "WGS" in coord_meta.upper():
        coord_sys_type = "projected_or_geographic"

    report = {
        "file": str(path.name),
        "file_size_gb": file_size_gb,
        "scan_count": scan_count,
        "total_points": total_points,
        "coordinate_bounds": {
            "x_min": round(global_x_min, 3),
            "x_max": round(global_x_max, 3),
            "y_min": round(global_y_min, 3),
            "y_max": round(global_y_max, 3),
            "z_min": round(global_z_min, 3),
            "z_max": round(global_z_max, 3),
        },
        "crs": coord_meta if coord_meta else "None / Not Embedded (Local Coordinate Frame)",
        "coordinate_system_type": coord_sys_type,
        "registered": has_poses,
        "scanner_positions_available": has_poses,
        "attributes": attr_types,
        "raw_attributes": attr_list,
        "metadata": {
            "e57_library_version": library_ver,
            "creation_date_time": creation_time,
            "guid": get_node_value(root.get("guid")) if root.isDefined("guid") else None,
            "scans": scans_meta,
        }
    }

    return report

def main():
    default_path = Path("d:/SIH26- 3D ULPIN Generation and vertical Property Mapping System/data/aam_khas_bagh/lidar/7csx-ne47_terresterial_lidar.e57")
    if len(sys.argv) > 1:
        e57_path = Path(sys.argv[1])
    else:
        e57_path = default_path

    print(f"=== INSPECTING E57 FILE: {e57_path.name} ===")
    report = inspect_e57(str(e57_path))

    # Write report to backend/tools/e57_inspection_report.json
    out_dir = Path("d:/SIH26- 3D ULPIN Generation and vertical Property Mapping System/backend/tools")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "e57_inspection_report.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[PASS] Inspection complete. Report saved to {report_file}\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
