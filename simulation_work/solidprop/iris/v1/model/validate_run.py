"""Audit every accepted step and sealed native input in a finished runtime."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from coupler import fingerprint
from ops import ROOT,TMP,atomic,disks


def validate(runtime):
    cfg=json.loads((runtime/'config.json').read_text());s=json.loads((runtime/'state.json').read_text())
    assert s['config_sha256']==fingerprint(cfg)
    manifest=json.loads((runtime/'input_manifest.json').read_text())
    for name,want in manifest.items():assert hashlib.sha256((runtime/name).read_bytes()).hexdigest()==want,name
    assert s['status'] in ['COMPLETED_HORIZON','PHENOLIC_CONSUMED','CASE_PROPERTY_LIMIT_REACHED']
    audits=[];previous=0.;g=cfg['geometry'];pitch=g['phenolic_thickness_m']/g['phenolic_radial_rows']
    for i in range(1,s['index']+1):
        a=json.loads((runtime/'checkpoints'/f'audit_{i:06d}.json').read_text())
        assert a['time_s']>previous and abs(a['time_s']-previous-a['dt_s'])<1e-8
        assert a['energy_relative_error']<=cfg['numerics']['energy_relative_tolerance']
        assert a['hot_power_relative_error']<=cfg['numerics']['hot_power_relative_tolerance']
        assert abs(a['mass_residual_kg'])<=max(1e-13,1e-6*s['mass_initial_kg'])
        assert a['hot_faces']==g['faces_per_row']
        assert math.isclose(a['phenolic_remaining_thickness_m'],(g['phenolic_radial_rows']-a['rows_scheduled'])*pitch,abs_tol=1e-12)
        assert a['rows_scheduled'] in [a['rows_removed'],a['rows_removed']+1]
        previous=a['time_s'];audits.append(a)
    assert abs(previous-s['time_s'])<1e-8
    if s['status']=='COMPLETED_HORIZON':assert abs(s['time_s']-cfg['end_time_s'])<1e-8
    warnings=[];logs=[]
    for path in sorted(runtime.glob('solve_*.out')):
        text=path.read_text(errors='replace')
        assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',text),path
        assert 'RUN COMPLETED' in text,path
        for part in text.split('*** WARNING ***')[1:]:warnings.append(part.split('\n\n')[0][:650])
        logs.append(dict(name=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    result=dict(runtime=runtime.name,passed=True,accepted_steps=len(audits),time_s=s['time_s'],status=s['status'],
                max_energy_relative_error=max(a['energy_relative_error'] for a in audits),
                max_hot_power_relative_error=max(a['hot_power_relative_error'] for a in audits),
                max_abs_mass_residual_kg=max(abs(a['mass_residual_kg']) for a in audits),
                removal_steps=sum(a['elements_scheduled_for_removal']>0 for a in audits),
                warning_blocks=warnings,native_logs=logs,config_sha256=hashlib.sha256((runtime/'config.json').read_bytes()).hexdigest())
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime');a=p.parse_args();disks()
    r=validate(TMP/'runs'/a.runtime);atomic(ROOT/'validation'/f'accepted_{a.runtime}.json',r);print(json.dumps(r,indent=2))
