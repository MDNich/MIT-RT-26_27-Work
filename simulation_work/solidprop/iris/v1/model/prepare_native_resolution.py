"""Prepare separate, sealed corrected-material resolution cases; never launch."""
import copy
import hashlib
import json
import subprocess
import sys
from ops import ROOT,TMP,atomic,disks

CASES=['sustainer_al','sustainer_cf','booster_al','booster_cf']
# Same-mesh quarter steps isolate coupling error before the spatial comparison.
LEVELS=[('time_quarter',80,20,.003125,.0625),
        ('space160',160,40,.003125,.0625),
        ('joint320',320,80,.0015625,.03125)]


def main():
    disks()
    records=[]
    for case in CASES:
        source=ROOT/'configs'/f'{case}_pulse7_n80_midpoint_tight.json'
        original=json.loads(source.read_text())
        levels=LEVELS+([('joint640',640,160,.00078125,.015625)] if case=='sustainer_cf' else [])
        for level,nph,ncase,dt,post in levels:
            name=f'{case}_pulse7_midpoint_{level}'
            cfg=copy.deepcopy(original)
            cfg.update(windows_root='C:\\IrisStudy\\runs\\'+name,host_runtime='I:\\ansystmp\\runs\\'+name,
                       macro_dt_s=dt,post_pulse_macro_dt_s=post,
                       post_pulse_initial_dt_s=min(post,dt*5),
                       campaign_role='native_resolution',resolution_level=level)
            cfg['geometry'].update(phenolic_radial_rows=nph,aluminium_radial_rows=ncase)
            cfg['expected_elements']=(nph+ncase)*cfg['geometry']['faces_per_row']
            cfg['expected_nodes']=(nph+ncase+1)*(cfg['geometry']['angular_divisions']+1)*(cfg['geometry']['axial_divisions']+1)
            cfg['provenance']['resolution_parent']=dict(file=str(source.relative_to(ROOT)),
                sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            cfg['provenance']['cooling_schedule']='First cooling second uses five times the heating step; subsequent cooling uses the specified refined ceiling. Exactly one native substep is required per accepted interval.'
            path=ROOT/'configs'/f'{name}.json'
            if path.exists():
                assert json.loads(path.read_text())==cfg, 'Never overwrite an existing configuration'
            else:
                atomic(path,cfg)
            runtime=TMP/'runs'/name
            if not (runtime/'input_manifest.json').exists():
                subprocess.run([sys.executable,str(ROOT/'model/prepare_model.py'),'--config',str(path),'--output',str(runtime)],
                               check=True,stdout=subprocess.DEVNULL)
            else:
                assert json.loads((runtime/'config.json').read_text())==cfg
            records.append(dict(runtime=name,case=case,level=level,phenolic_cells=nph,case_cells=ncase,
                heating_dt_s=dt,cooling_dt_s=post,end_time_s=cfg['end_time_s'],
                config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                initial_status='PREPARED_NOT_DISPATCHED'))
            print('Prepared',name,flush=True)
    atomic(ROOT/'validation/native_resolution_plan.json',dict(
        status='PREPARED_NOT_DISPATCHED',cases=records,
        basis=['validation/pulse_resolution.json','validation/partial_capacity_resolution.json'],
        comparisons=['Primary 80-row schedule versus same-mesh quarter time steps',
                     '80 versus 160 rows at identical time steps',
                     '160 versus 320 rows with halved time steps',
                     'Sustainer CF additionally 320 versus 640 rows with halved time steps'],
        acceptance=dict(casing_peak_difference_K=5,scope_time_relative_change=.05,
            remaining_thickness='max(0.02 mm, 1 percent of initial phenolic thickness)'),
        qualification='Native results remain pending. Stop at provisional material scope. Each run must pass complete audits and same-mesh independent comparison before queue advance. Compare censored histories by scope-time brackets, never by an uncomputed later peak.'))


if __name__=='__main__':
    main()
