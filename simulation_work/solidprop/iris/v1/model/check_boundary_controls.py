"""Check pulse-edge load transfer without launching native jobs."""
import json
from pathlib import Path
from ops import ROOT,atomic,disks
from prepare_model import create_mesh
from coupler import initial_state,prepare_step,exposure

def main():
    disks();c=json.loads((ROOT/'configs/sustainer_al.json').read_text())
    c['heating']['pulse_duration_s']=7.;c['post_pulse_macro_dt_s']=.1;c['end_time_s']=127.
    mesh,_,_=create_mesh(c);s=initial_state(mesh,c);s['time_s']=6.995
    p,commands=prepare_step(mesh,c,s)
    assert abs(p['target']-7)<1e-12 and p['exposure_on']
    s['time_s']=7.;p,commands=prepare_step(mesh,c,s)
    assert abs(p['dt']-.1)<1e-12 and not p['exposure_on']
    assert p['totals']['char_rate_kg_s']==0 and p['totals']['hot_radiation_W']==0
    assert all(f['h']==8 and f['Tgas_C']==22 for f in p['faces'])
    assert 'SFEDELE,ALL,ALL,CONV' in commands
    out=dict(passed=True,checks=['Step lands exactly on pulse edge','Post-pulse gas resets to ambient with specified convection','Char consumption and hot radiation switch off','Old hot-face convection cleared before replacement'],scope='Controller logic test; native pulse verification remains required')
    atomic(ROOT/'validation/boundary_controls.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
