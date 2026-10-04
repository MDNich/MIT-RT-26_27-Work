"""Extract sparse radial calibration/validation profiles from immutable checkpoints."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / 'ansystmp/windows'
cfg = json.loads((ROOT/'config.json').read_text())
g = cfg['geometry']
sector_factor = math.radians(g['angle_deg']) * g['length_m']
mesh = json.loads((ROOT/'mesh_map.json').read_text())
row_ids = [[str(f['element']) for f in row] for row in mesh['rows']]
radii = np.r_[np.linspace(g['inner_radius_m'],g['phenolic_outer_radius_m'],241),
              np.linspace(g['phenolic_outer_radius_m'],g['outer_radius_m'],65)[1:]]
selected = sorted({13, 385, 425, 498, *range(20,499,20)})
out=[]
sources={}
for idx in selected:
    p=ROOT/'checkpoints'/f'state_{idx:06d}.json.gz'
    raw=p.read_bytes(); st=json.loads(gzip.decompress(raw))
    ts=st['temperatures']
    mid=np.array([ts[str(ir*753+377)] for ir in range(305)])
    axisym=max(abs(ts[str(ir*753+1)]-ts[str(ir*753+753)]) for ir in range(st['layer'],305))
    assert axisym < 1e-5
    aa=np.array([sum(st['alpha'][e] for e in row)/500 for row in row_ids])
    cc=np.array([sum(st['char_consumed'].get(e,0.) for e in row)/sector_factor for row in row_ids])
    audit=json.loads((ROOT/'checkpoints'/f'audit_{idx:06d}.json').read_text())
    out.append({'index':idx,'time_s':st['time_s'],'temperature_C':mid.tolist(),
                'alpha':aa.tolist(),'char_consumed_kg_per_rad_m':cc.tolist(),
                'layer':st['layer'],'gas_rate_kg_per_rad_m_s':st['gas_rate_kg_s']/sector_factor,
                'char_rate_kg_per_rad_m_s':st.get('char_rate_kg_s',0)/sector_factor,
                'qcond_surface_W_m2':sum(st['radial_flux'][e] for e in row_ids[st['layer']])/500,
                'audit_hot_C':audit['Ts_mean_C'],'audit_h':audit['h_W_m2_K'],
                'axisymmetry_sample_difference_K':axisym})
    sources[p.name]=hashlib.sha256(raw).hexdigest()
result={'configuration':cfg,'radii_m':radii.tolist(),'profiles':out,'source_sha256':sources}
(HERE/'radial_profiles.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'profiles':len(out),'first_time':out[0]['time_s'],'last_time':out[-1]['time_s'],
                  'max_axisymmetry_error_K':max(x['axisymmetry_sample_difference_K'] for x in out)},indent=2))
