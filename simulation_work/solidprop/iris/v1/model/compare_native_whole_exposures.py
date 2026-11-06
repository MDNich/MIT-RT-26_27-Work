"""Compare only accepted ambient-to-exhaustion MAPDL runs with the independent FV scenarios."""
import argparse
import json
from pathlib import Path

import numpy as np

from audit_liner_energy import analyze
from audit_sector_endpoint import sha
from ops import ROOT, TMP, atomic, disks
from prepare_sector_endpoint import PACKAGE


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def compare_history(native, reference):
    # At exhaustion the native first node becomes the casing interface.
    # Use normal half-second output stations strictly before both events.
    nt=np.array([p['time_s'] for p in native])
    rt=np.array([p['time_s'] for p in reference])
    assert np.all(np.diff(nt)>0) and np.all(np.diff(rt)>0)
    stop=min(nt[-1],rt[-1])
    grid=.5*np.arange(1,int(np.ceil(2*stop)))
    assert len(grid) and len(nt)>=len(grid) and np.allclose(nt[:len(grid)],grid,rtol=0,atol=1e-8)
    result={}
    for a,b in [('remaining_mm','remaining_mm'),('hot_C','face_C'),('interface_C','interface_C'),('outer_C','outer_C')]:
        other=np.interp(grid,rt,[p[b] for p in reference])
        delta=np.array([p[a] for p in native[:len(grid)]])-other
        j=int(np.argmax(abs(delta)))
        result[a]=dict(max_abs=float(abs(delta[j])),signed_at_max=float(delta[j]),time_at_max_s=float(grid[j]))
    return dict(first_s=grid[0],last_s=grid[-1],stations=len(grid),differences=result)


def case(job):
    evidence=ROOT/'validation'/('native_sector_r2_'+job+'.json')
    receipt=read(evidence)
    assert receipt['passed'] and receipt['role']=='whole' and receipt['native_interval_start_s']==0
    run=TMP/'runs'/('sector_'+job)
    terminal=run/'sector_terminal.json'
    settings=PACKAGE/(job+'_settings.json')
    assert sha(terminal)==receipt['files']['sector_terminal.json'] and sha(settings)==receipt['settings_sha256']
    assert sha(run/'guest_terminal.json')==receipt['terminal_sha256'] and sha(PACKAGE/'controller.zip')==receipt['archive_sha256']
    data=read(terminal)
    assert data['settings']==read(settings) and 'donor_record' not in data['settings']
    assert data['record']['state']['virgin']==[] and data['native_blocks']==receipt['native_blocks']
    name=receipt['case']
    cf=name.endswith('_cf')
    model='cf' if cf else 'aluminium'
    tag=name+('_reacting_fine' if cf else '_phase_n640_ms20_mK500')
    fv_path=ROOT/f'validation/{model}_backing_cases'/(tag+'.json')
    fv_proof=read(ROOT/f'validation/{model}_backing_audit.json')['records'][tag]
    assert sha(fv_path)==fv_proof['sha256' if cf else 'record_sha256']
    fv=read(fv_path)
    assert fv['eligible_for_motor_lifetime'] is False
    history=data['record']['stats']['samples']
    e=data['record']['stats']['events']
    native_end=receipt['terminal_s']
    fv_end=fv['events']['exhaustion'][1]
    other_limit='backing_1000_C' if cf else 'all_liquid'
    assert receipt['events']==e and e['exhaustion'][1]==history[-1]['time_s']==native_end
    assert e[other_limit][1]<native_end and abs(history[-1]['remaining_mm'])<1e-9
    assert sha(ROOT/'model/audit_sector_endpoint.py')==receipt['auditor_sha256']
    energy=analyze(fv,data['settings'],data['record'])
    live=[s for s in history if s['remaining_mm']>0]
    peak=max(live,key=lambda s:s['hot_C'])
    detail=compare_history(history,fv['history'])
    n_interval=e['exhaustion']
    f_interval=fv['events']['exhaustion']
    gap=max(0.,max(n_interval[0],f_interval[0])-min(n_interval[1],f_interval[1]))
    original=fv['history'][0]['remaining_mm']
    limits=dict(event_relative=.01,thickness_mm=max(.02,.01*original))
    numerical_agreement=(abs(native_end/fv_end-1)<limits['event_relative'] and
                         detail['differences']['remaining_mm']['max_abs']<=limits['thickness_mm'])
    return dict(case=name,job=job,initial_mm=original,native_blocks=receipt['native_blocks'],
                native_end_s=native_end,independent_end_s=fv_end,native_minus_independent_s=native_end-fv_end,
                preceding_casing_event=other_limit,casing_event_bracket_s=e[other_limit],
                native_event_bracket_s=n_interval,independent_event_bracket_s=f_interval,
                event_intervals_overlap=gap==0.,event_interval_gap_s=gap,
                native_events=e,peak_sampled_live_face_C=peak['hot_C'],peak_sample_time_s=peak['time_s'],
                heat_dose_MJ_m2=dict(native=energy['FE']['film_MJ_m2'],finite_volume=energy['FV']['film_MJ_m2']),
                native_char_percent=energy['FE']['char_percent'],
                species_and_reaction_error=energy['max_mass_or_chemical_energy_fractional_error'],
                native_balance_errors=receipt['balances'],native_max_block_error_K=receipt['max_field_error_K'],
                common_times=detail,limits=limits,meets_event_and_thickness_targets=bool(numerical_agreement),
                native_evidence_sha256=sha(evidence),fv_sha256=sha(fv_path),history=history)


def main():
    disks()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accepted-only',action='store_true',help='Write a partial comparison using completed native audits.')
    args=parser.parse_args()
    jobs=('wall2sa','wall2sc','wall2ba','wall2bc')
    accepted=[j for j in jobs if (ROOT/f'validation/native_sector_r2_{j}.json').is_file()]
    if not accepted or (not args.accepted_only and len(accepted)!=len(jobs)):
        raise SystemExit(f'Accepted whole-exposure runs: {len(accepted)}/{len(jobs)}')
    out=ROOT/'validation/native_whole_exposure_comparison.json'
    if out.exists() and not set(read(out)['accepted_jobs']).issubset(accepted):
        raise ValueError('Previously accepted case is missing')
    results=[case(job) for job in accepted]
    atomic(out,dict(
        complete_four_cases=len(accepted)==len(jobs),accepted_jobs=accepted,
        pending_jobs=[job for job in jobs if job not in accepted],
        eligible_for_motor_lifetime=False,source_sha256=sha(Path(__file__)),
        energy_auditor_sha256=sha(ROOT/'model/audit_liner_energy.py'),cases=results,
        accepted_cases_meet_event_and_thickness_targets=all(r['meets_event_and_thickness_targets'] for r in results),
        scope='Native and independent times from first gas exposure under continuous nominal heating, with surrogate backing beyond its material limits.'))


if __name__=='__main__':
    main()
