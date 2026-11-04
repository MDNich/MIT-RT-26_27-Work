"""Test successive tighter removal cutoffs and joint spatial/time refinement."""
import fcntl
import hashlib
import json
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,disks,host_check,utc


def run_one(case,nph,fraction):
    dt=.0015625*320/nph;post=.03125*320/nph;ncase=nph//4
    cfg=json.loads((ROOT/'configs'/f'{case}_pulse7_n80_midpoint_tight.json').read_text())
    cfg['geometry'].update(phenolic_radial_rows=nph,aluminium_radial_rows=ncase)
    cfg['numerics']['row_residual_mass_fraction']=fraction
    cfg.update(macro_dt_s=dt,post_pulse_macro_dt_s=post,post_pulse_initial_dt_s=dt*5)
    source=(ROOT/'model/radial_model.py').read_bytes();sha=hashlib.sha256(source).hexdigest()
    archive=ROOT/'validation/source_archive'/f'radial_model_{sha}.py'
    if not archive.exists():archive.write_bytes(source)
    cfg_sha=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    path=ROOT/'validation/radial'/f'{case}_cutoff_n{nph}_f{fraction:g}.json'
    if path.exists():
        d=json.loads(path.read_text())
        assert d['configuration_sha256']==cfg_sha and d['model_sha256']==sha
        return d
    host_check()
    atomic(TMP/'tight_cutoff_progress.json',dict(utc=utc(),case=case,cells=nph,fraction=fraction,status='RUNNING',native=False))
    m=RadialModel(cfg)
    state,h,_=m.run(cfg['end_time_s'],dt=dt,post_dt=post,record_dt=.1,
        targets=[7.],check=host_check,stop_at_property_limit=True)
    peaks={k:max(h,key=lambda a:a[k]) for k in ['interface_C','outer_C']}
    initial=cfg['material']['virgin_reference_density_kg_m3']*sum(m.vol[:nph])
    d=dict(method='Independent radial finite elements, NOT ANSYS',case=case,
        phenolic_cells=nph,case_cells=ncase,removal_cutoff_fraction=fraction,
        configuration=cfg,configuration_sha256=cfg_sha,model_sha256=sha,
        eligible_for_motor_lifetime=False,final=h[-1],scope_bracket_s=m.property_bracket,
        exhaustion_bracket_s=m.event_bracket,
        sampled_maxima={k:dict(temperature_C=v[k],time_s=v['time_s']) for k,v in peaks.items()},
        expelled_residual_fraction_initial_mass=state.eject_total/initial,
        max_energy_relative_error=m.max_energy_error,max_mass_relative_error=m.max_mass_error,
        qualification='Numerical cutoff perturbation only; not a calibrated material law or physical error bound.')
    atomic(path,d);print(case,nph,fraction,d['final']['time_s'],d['final']['remaining_mm'],flush=True)
    return d


def compare(a,b,kind):
    full=not (a['scope_bracket_s'] or b['scope_bracket_s']) and abs(a['final']['time_s']-b['final']['time_s'])<1e-8
    scope=bool(a['scope_bracket_s'] and b['scope_bracket_s'])
    peak={k:b['sampled_maxima'][k]['temperature_C']-a['sampled_maxima'][k]['temperature_C'] for k in a['sampled_maxima']} if full else None
    timing=b['scope_bracket_s'][1]/a['scope_bracket_s'][1]-1 if scope else None
    thickness=abs(b['final']['remaining_mm']-a['final']['remaining_mm'])
    target=max(.02,10*a['configuration']['geometry']['phenolic_thickness_m'])
    passed=thickness<=target and ((full and max(map(abs,peak.values()))<5) or (scope and abs(timing)<.05))
    return dict(case=a['case'],comparison=kind,coarse_cells=a['phenolic_cells'],fine_cells=b['phenolic_cells'],
        coarse_cutoff=a['removal_cutoff_fraction'],fine_cutoff=b['removal_cutoff_fraction'],
        scope_time_relative_change=timing,peak_differences_K=peak,remaining_difference_mm=thickness,
        remaining_target_mm=target,passed=passed,exhaustion_excluded=bool(a['exhaustion_bracket_s'] or b['exhaustion_bracket_s']))


def main():
    disks()
    with open(TMP/'tight_cutoff.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        records={};comparisons=[];references=[]
        # Investigate the sensitive CF stopping time first.
        for case in ['sustainer_cf','sustainer_al','booster_al','booster_cf']:
            for nph in [320,640]:
                for fraction in [.0001,.00001,.000001]:
                    d=run_one(case,nph,fraction);records[nph,fraction]=d
                    path=ROOT/'validation/radial'/f'{case}_cutoff_n{nph}_f{fraction:g}.json'
                    references.append(dict(case=case,cells=nph,fraction=fraction,
                        file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                    if fraction!=.0001:
                        previous=.0001 if fraction==.00001 else .00001
                        comparisons.append(compare(records[nph,previous],d,'cutoff only'))
                    if nph==640:comparisons.append(compare(records[320,fraction],d,'space and time at fixed cutoff'))
                    atomic(ROOT/'validation/removal_cutoff_resolution.json',dict(
                        complete=len(references)==24,independent_only=True,results=references,comparisons=comparisons,
                        qualification='Successive numerical cutoffs and joint mesh/time comparison. No native input is changed by this diagnostic. A tight-cutoff limit of these equations is not physical validation of the removal law.'))
        atomic(TMP/'tight_cutoff_progress.json',dict(utc=utc(),status='COMPLETE',native=False))


if __name__=='__main__':
    main()
