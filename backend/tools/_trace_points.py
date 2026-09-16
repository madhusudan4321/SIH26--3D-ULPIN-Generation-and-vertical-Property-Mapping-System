import json

with open('../data/aam_khas_bagh/derived/aam_khas_bagh_classified_cloud.json', 'r') as f:
    data = json.load(f)

for key in ['ground_points', 'non_ground_points', 'selected_building_points']:
    flat = data.get(key, [])
    print(f'{key}: {len(flat)//6} points ({len(flat)} floats)')

cands = data.get('building_candidates', [])
print(f'\nBuilding candidates: {len(cands)}')
for c in cands:
    cid = c['candidate_id']
    pc = c['point_count']
    sc = c['building_score']
    w = c['width_m']
    l = c['length_m']
    h = c['height_m']
    print(f'  Candidate {cid}: {pc} pts, score={sc}, dims={w}x{l}x{h}m')

total_cand_pts = sum(c['point_count'] for c in cands)
print(f'Total candidate points (all candidates): {total_cand_pts}')

# Check the mesh metadata for the 21124 number
with open('../data/aam_khas_bagh/derived/aam_khas_bagh_mesh_metadata.json', 'r') as f:
    mesh_meta = json.load(f)
print(f'\nMesh metadata input_point_count: {mesh_meta.get("input_point_count")}')
print(f'Mesh metadata points_after_cleaning: {mesh_meta.get("points_after_cleaning")}')
print(f'Mesh metadata outliers_removed: {mesh_meta.get("outliers_removed")}')
