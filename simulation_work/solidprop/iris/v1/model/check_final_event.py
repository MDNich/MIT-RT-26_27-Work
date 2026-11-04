"""Manufactured final-row bookkeeping fixture; no physical lifetime claim."""
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import coupler
from prepare_model import create_mesh
from ops import ROOT,TMP,atomic,disks


def main():
    disks();c=json.loads((ROOT/'configs/sustainer_al.json').read_text());c['end_time_s']=1.
    c['heating']['gas_temperature_C']=22.;c['char_law']['reactive_activity']=0.
    mesh,nodes,_=create_mesh(c);s=coupler.initial_state(mesh,c)
    rv=c['material']['virgin_reference_density_kg_m3'];rc=c['material']['char_reference_density_kg_m3']
    s['layer']=c['geometry']['phenolic_radial_rows']-1
    s['temperatures']={str(n):22. for n,x,y,z in nodes}
    volume=sum(e['volume'] for e in mesh['elements'].values() if e['mat']==1)
    last={str(f['element']) for f in mesh['rows'][-1]};retained=0.
    for eid,e in mesh['elements'].items():
        if e['mat']!=1:continue
        s['alpha'][eid]=1.
        left=.0005*rv*e['volume'] if eid in last else 0.
        s['char_consumed'][eid]=rc*e['volume']-left;retained+=left
    s['gas_cumulative_kg']=(rv-rc)*volume
    s['char_cumulative_kg']=rc*volume-retained
    p,commands=coupler.prepare_step(mesh,c,s)
    dead={str(f['element']) for row in mesh['rows'][:-1] for f in row}
    live=set(mesh['elements'])-dead
    fields={eid:[1. if mesh['elements'][eid]['mat']==1 else 0.,0.,0.,0.] for eid in live}
    energy={eid:[0.]*7 for eid in live}
    new,a=coupler.accept_step(mesh,c,s,p,s['temperatures'],fields,energy,p['target'])
    assert new['status']=='PHENOLIC_CONSUMED' and new['layer']==len(mesh['rows'])
    assert a['phenolic_remaining_thickness_m']==0 and a['elements_scheduled_for_removal']==c['geometry']['faces_per_row']
    assert abs(new['residual_ejected_kg']-retained)<1e-18
    with tempfile.TemporaryDirectory(dir=TMP) as temp:
        base=Path(temp);root=base/'runs/final_event';root.mkdir(parents=True)
        for name,value in [('config',c),('mesh_map',mesh),('state',new)]:coupler.save(root/f'{name}.json',value)
        coupler.save(base/'host_storage_status.json',dict(allowed=True,checked_epoch=time.time(),guest_checked_epoch=time.time(),mac_free_bytes=500_000_000_000))
        with patch.object(sys,'argv',['coupler.py','prepare','--root',str(root)]),patch('shutil.disk_usage',return_value=SimpleNamespace(free=20_000_000_000)),patch.object(coupler,'prepare_step',side_effect=AssertionError('Must not access a nonexistent next row')):
            coupler.main()
        assert 'V0_DONE=1' in (root/'step_control.inp').read_text()
    out=dict(passed=True,qualification='Manufactured controller fixture; no native solve and no physical burnthrough estimate',
             checks=['Final row records exhaustion and zero retained mesh thickness','Residual mass is ejected exactly once','Exactly one final row is scheduled','Next prepare exits before indexing a nonexistent phenolic row'],
             final_mass_residual_kg=a['mass_residual_kg'],residual_ejected_kg=new['residual_ejected_kg'])
    atomic(ROOT/'validation/final_event_controls.json',out);print(json.dumps(out,indent=2))

if __name__=='__main__':main()
