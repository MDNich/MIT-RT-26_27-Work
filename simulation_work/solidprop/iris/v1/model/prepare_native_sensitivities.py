"""Prepare bounded native confirmation of influential input applications."""
import copy
import hashlib
import json
import subprocess
import sys
from combined_pulse_sensitivities import SCENARIOS
from ops import ROOT,TMP,atomic,disks

CASES=[
    ('sustainer_al','higher_heating',{'heating':{'h0_W_m2_K':2000.}}),
    ('booster_cf','alternative_cf',{'material':{'aluminium_density_kg_m3':1596.},
        '_root':{'cf_radial_k':.3832,'cf_cp_constant_J_kg_K':886.}}),
    ('sustainer_cf','heating_transport',SCENARIOS['heating_transport']),
    ('booster_cf','heating_consumption',SCENARIOS['heating_consumption'])]


def main():
    disks();records=[]
    for case,scenario,changes in CASES:
        source=ROOT/'configs'/f'{case}_pulse7_n80_midpoint_tight.json'
        cfg=json.loads(source.read_text())
        for section,values in changes.items():
            (cfg if section=='_root' else cfg[section]).update(values)
        name=f'{case}_sensitivity_{scenario}_midpoint_control20'
        cfg.update(windows_root='C:\\IrisStudy\\runs\\'+name,host_runtime='I:\\ansystmp\\runs\\'+name,
            end_time_s=20.,macro_dt_s=.003125,post_pulse_macro_dt_s=.0625,post_pulse_initial_dt_s=.015625,
            campaign_role='native_sensitivity_verification',sensitivity_scenario=scenario)
        cfg['provenance']['sensitivity_parent']=dict(file=str(source.relative_to(ROOT)),
            sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        cfg['provenance']['exposure']='Bounded native numerical confirmation: assumed seven-second pulse then cooling only through 20 s or earlier material-scope flag. Not a full cooling-peak or lifetime prediction.'
        cfg['provenance']['sensitivity']='Selected from the earlier independent sensitivity screen and the joint-input pulse scenarios. The alternative CF tuple is the already documented NASA reference, not measured Iris material. Engineering perturbations are not confidence bounds.'
        cfg['provenance']['cooling_schedule']='First cooling second uses 0.015625 s, then 0.0625 s; require exactly one native substep in every accepted interval.'
        path=ROOT/'configs'/f'{name}.json';runtime=TMP/'runs'/name
        if path.exists():assert json.loads(path.read_text())==cfg
        else:atomic(path,cfg)
        if not (runtime/'input_manifest.json').exists():
            subprocess.run([sys.executable,str(ROOT/'model/prepare_model.py'),'--config',str(path),'--output',str(runtime)],
                check=True,stdout=subprocess.DEVNULL)
        else:assert json.loads((runtime/'config.json').read_text())==cfg
        records.append(dict(runtime=name,case=case,scenario=scenario,changes=changes,
            horizon_s=20.,pulse_s=7.,phenolic_cells=80,case_cells=20,
            config_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        print('Prepared',name,flush=True)
    atomic(ROOT/'validation/native_sensitivity_plan.json',dict(
        status='PREPARED_NOT_DISPATCHED',cases=records,
        qualification='These bounded controls test native application of influential and combined inputs, reaction/source response, removal/load transfer and cooling against the same-mesh independent model. They do not establish full-history sensitivity or convergence of a later peak or scope time.',
        acceptance='Unchanged native audit gates and same-mesh profile/conversion/mass/exact-row plus topology/cooling checks. Any failed comparison stops continuation.',
        physical_scope='All parameters are inherited assumptions, published alternative CF data or the existing labelled engineering perturbations. No actual motor lifetime claim.'))


if __name__=='__main__':
    main()
