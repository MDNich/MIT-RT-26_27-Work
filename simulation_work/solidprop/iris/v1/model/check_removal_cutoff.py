"""Paired independent sensitivity to residual-solid row-removal tolerance."""
import fcntl
import hashlib
import json
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,disks,host_check,utc


def main():
    disks()
    with open(TMP/'removal_cutoff.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        source=(ROOT/'model/radial_model.py').read_bytes();sha=hashlib.sha256(source).hexdigest()
        results=[];comparisons=[]
        for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
            for nph,ncase,dt,post in [(160,40,.003125,.0625),(320,80,.0015625,.03125)]:
                paired={}
                for fraction in [.001,.0001,.01]:
                    host_check()
                    path=ROOT/'validation/radial'/f'{case}_cutoff_n{nph}_f{fraction:g}.json'
                    cfg=json.loads((ROOT/'configs'/f'{case}_pulse7_n80_midpoint_tight.json').read_text())
                    cfg['geometry'].update(phenolic_radial_rows=nph,aluminium_radial_rows=ncase)
                    cfg['numerics']['row_residual_mass_fraction']=fraction
                    cfg.update(macro_dt_s=dt,post_pulse_macro_dt_s=post,post_pulse_initial_dt_s=dt*5)
                    cfg_sha=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
                    if path.exists():
                        d=json.loads(path.read_text())
                        assert d['configuration_sha256']==cfg_sha and d['model_sha256']==sha
                    else:
                        atomic(TMP/'removal_cutoff_progress.json',dict(utc=utc(),case=case,cells=nph,
                            fraction=fraction,status='RUNNING',native=False))
                        m=RadialModel(cfg)
                        state,h,_=m.run(cfg['end_time_s'],dt=dt,post_dt=post,record_dt=.1,
                            targets=[7.],check=host_check,stop_at_property_limit=True)
                        peaks={k:max(h,key=lambda a:a[k]) for k in ['interface_C','outer_C']}
                        initial=cfg['material']['virgin_reference_density_kg_m3']*sum(m.vol[:nph])
                        d=dict(method='Independent radial finite elements, NOT ANSYS',case=case,
                            phenolic_cells=nph,case_cells=ncase,removal_cutoff_fraction=fraction,
                            configuration=cfg,configuration_sha256=cfg_sha,model_sha256=sha,
                            eligible_for_motor_lifetime=False,final=h[-1],
                            scope_bracket_s=m.property_bracket,exhaustion_bracket_s=m.event_bracket,
                            sampled_maxima={k:dict(temperature_C=v[k],time_s=v['time_s']) for k,v in peaks.items()},
                            expelled_residual_fraction_initial_mass=state.eject_total/initial,
                            max_energy_relative_error=m.max_energy_error,max_mass_relative_error=m.max_mass_error,
                            qualification='Numerical cutoff perturbation only; not a calibrated material law or physical error bound.')
                        atomic(path,d)
                    paired[fraction]=d
                    results.append(dict(case=case,phenolic_cells=nph,cutoff_fraction=fraction,
                        file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                    print(case,nph,fraction,d['final']['time_s'],flush=True)
                base=paired[.001]
                for fraction in [.0001,.01]:
                    d=paired[fraction]
                    full=not (base['scope_bracket_s'] or d['scope_bracket_s']) and abs(base['final']['time_s']-d['final']['time_s'])<1e-8
                    scope=bool(base['scope_bracket_s'] and d['scope_bracket_s'])
                    comparisons.append(dict(case=case,phenolic_cells=nph,cutoff_fraction=fraction,
                        peak_differences_K={k:d['sampled_maxima'][k]['temperature_C']-base['sampled_maxima'][k]['temperature_C'] for k in base['sampled_maxima']} if full else None,
                        scope_time_relative_change=d['scope_bracket_s'][1]/base['scope_bracket_s'][1]-1 if scope else None,
                        remaining_difference_mm=d['final']['remaining_mm']-base['final']['remaining_mm'],
                        expelled_residual_fraction_initial_mass=d['expelled_residual_fraction_initial_mass'],
                        both_complete=full,both_scope_limited=scope,
                        exhaustion_excluded=bool(base['exhaustion_bracket_s'] or d['exhaustion_bracket_s'])))
                atomic(ROOT/'validation/removal_cutoff_sensitivity.json',dict(
                    complete=len(results)==24,independent_only=True,results=results,comparisons=comparisons,
                    qualification='Paired changes from the 0.1 percent row-residual cutoff at fixed mesh/time settings. Does not replace separate mesh convergence of absolute case peaks or scope times.'))
        atomic(TMP/'removal_cutoff_progress.json',dict(utc=utc(),status='COMPLETE',native=False))


if __name__=='__main__':
    main()
