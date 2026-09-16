import json

with open('../data/aam_khas_bagh/derived/aam_khas_bagh_vegetation_classification.json', 'r') as f:
    r = json.load(f)

sd = r['score_distribution']
print('SCORE DISTRIBUTION:')
for k, v in sd.items():
    print(f'  {k}: {v}')

print('\nSPATIAL COHERENCE:')
sc = r['spatial_coherence']
print(f'  Building point count: {sc["building_point_count"]}')
print(f'  Components: {sc["component_count"]}')
print(f'  Largest component: {sc["largest_component_size"]} pts ({sc["largest_component_pct"]}%)')
print(f'  XY fill ratio: {sc["xy_fill_ratio_1m_pct"]}%')
for c in sc.get('components', [])[:5]:
    print(f'    Component {c["component_id"]}: {c["point_count"]} pts ({c["pct_of_building"]}%)')

print('\nBUILDING Z DISTRIBUTION:')
bld_z = r['per_class_analysis']['BUILDING'].get('z_distribution', {})
for k, v in bld_z.items():
    bar = '#' * int(v['pct'])
    print(f'  {k:>8s}: {v["count"]:>5d} ({v["pct"]:>5.1f}%) {bar}')

print('\nFEATURE SEPARATION:')
for feat, info in r['feature_separation'].items():
    if isinstance(info, dict) and 'difference' in info:
        bm = info["building_median"]
        vm = info["vegetation_median"]
        d = info["difference"]
        t = info["expected_trend_present"]
        print(f'  {feat:>22s}: bld={bm:.4f} veg={vm:.4f} diff={d:+.4f} trend={t}')

print('\nNORMALIZATION BOUNDARIES:')
for feat, bounds in r['normalization']['boundaries_used'].items():
    print(f'  {feat}: {bounds}')

print('\nCOMPARISON WITH ORIGINAL:')
comp = r['comparison_with_original']
print(f'  Original candidate: {comp["original_candidate"]["count"]} pts')
fb = comp.get('filtered_building', {})
print(f'  Filtered building: {fb.get("count", 0)} pts')
if 'z_range_m' in fb:
    print(f'  Building Z range: {fb["z_range_m"]}m')
    print(f'  Building X range: {fb["x_range_m"]}m')
    print(f'  Building Y range: {fb["y_range_m"]}m')
