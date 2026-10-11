"""Read accepted checkpoints only; write a derived analysis snapshot, never runtime files."""
import gzip
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
V0 = HERE.parents[2]
ROOT = V0 / 'ansystmp/windows'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    raw_state = (ROOT / 'state.json').read_bytes()
    state = json.loads(raw_state)
    raw_mesh = (ROOT / 'mesh_map.json').read_bytes()
    mesh = json.loads(raw_mesh)
    cfg = json.loads((ROOT / 'config.json').read_text())
    assert state['index'] == 498 and state['status'] == 'PAUSED_AT_CHECKPOINT'
    ph = {n for e in mesh['elements'].values() if e['mat'] == 1 for n in e['nodes']}
    al = {n for e in mesh['elements'].values() if e['mat'] == 2 for n in e['nodes']}
    interface = sorted(ph & al)
    outer = sorted({n for f in mesh['outer'] for n in f['nodes']})
    assert len(interface) == len(outer) == 753 and not set(interface) & set(outer)
    rows = [[(str(f['element']), f['volume']) for f in row] for row in mesh['rows']]
    weights = [sum(v for _, v in row) for row in rows]
    thickness = 1000 * cfg['geometry']['phenolic_thickness_m']
    pitch = thickness / len(rows)

    def front(st):
        a = st['alpha']
        means = [sum(a[e] * v for e, v in row) / w for row, w in zip(rows, weights)]
        j = next((j for j, a in enumerate(means) if a < .98), len(means))
        if j == 0:
            return 0.
        if j == len(means):
            return thickness
        return (j - .5 + (means[j-1] - .98) / (means[j-1] - means[j])) * pitch

    points = [{'index': 0, 'time_s': 0., 'interface_max_C': 22., 'outer_max_C': 22.,
               'interface_min_C': 22., 'outer_min_C': 22., 'front98_mm': 0.}]
    sources = {'state.json': digest(raw_state), 'mesh_map.json': digest(raw_mesh)}
    for j, path in enumerate(sorted((ROOT / 'checkpoints').glob('state_*.json.gz')), 1):
        raw = path.read_bytes()
        st = json.loads(gzip.decompress(raw))
        assert st['index'] == j and st['time_s'] > points[-1]['time_s']
        inside = [st['temperatures'][str(n)] for n in interface]
        outside = [st['temperatures'][str(n)] for n in outer]
        assert all(math.isfinite(v) for v in inside + outside)
        points.append({'index': j, 'time_s': st['time_s'],
                       'interface_max_C': max(inside), 'outer_max_C': max(outside),
                       'interface_min_C': min(inside), 'outer_min_C': min(outside),
                       'front98_mm': front(st)})
        sources[str(path.relative_to(ROOT))] = digest(raw)
        if j % 100 == 0:
            print('Read', j, 'accepted checkpoints', flush=True)
    assert points[-1]['index'] == 498
    assert (ROOT / 'state.json').read_bytes() == raw_state
    result = {'analysis_date': '2026-10-04', 'runtime': str(ROOT),
              'accepted_index': 498, 'accepted_time_s': state['time_s'],
              'initial_temperature_C': cfg['initial_temperature_C'],
              'interface_radius_mm': 1000 * cfg['geometry']['phenolic_outer_radius_m'],
              'outer_radius_mm': 1000 * cfg['geometry']['outer_radius_m'],
              'interface_node_count': len(interface), 'outer_node_count': len(outer),
              'phenolic_initial_thickness_mm': thickness,
              'pyrolysis_definition': 'Contiguous alpha >= 0.98 front from original bore; volume-weighted row means and interpolation between centres. Not material disappearance.',
              'qualification': cfg['qualification'], 'points': points, 'source_sha256': sources}
    (HERE / 'temperature_history.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'last': points[-1], 'sample_count': len(points),
                      'interface_max_C': max(p['interface_max_C'] for p in points),
                      'outer_max_C': max(p['outer_max_C'] for p in points)}, indent=2))


if __name__ == '__main__':
    main()
