"""Compare the independent finite-volume and nodal estimates at identical refinement levels."""
import argparse
import fcntl
import signal
from pathlib import Path

from audit_moving_surface import compare
from backing_film_campaign import MATERIALS, inputs, parents, read
from check_whole_event_intervals import JOBS, PACKAGE, WORK as SECTOR
from compare_native_whole_exposures import compare_history
from continuous_heating_campaign import digest
from moving_surface_campaign import SHARED, stop_signal
from ops import ROOT, TMP, StorageLimitError, atomic, disks, stop_runs, utc

PLAN = ROOT/'configs/matched_event_intervals.json'
WORK = TMP/'matched_event_intervals'
OUT = ROOT/'validation/matched_event_intervals.json'


def prepare():
    disks()
    if PLAN.exists():
        raise FileExistsError(PLAN)
    sources=inputs()
    for name in ('compare_matched_event_intervals','compare_native_whole_exposures','check_whole_event_intervals','audit_moving_surface'):
        path=ROOT/f'model/{name}.py'
        sources[str(path.relative_to(ROOT))]=digest(path)
    atomic(PLAN,dict(sources=sources,archive_sha256=digest(PACKAGE/'controller.zip'),jobs=list(JOBS),
        levels=[[320,.005],[320,.0025],[640,.0025]],horizon_s=220.,
        profile_times_s=[0.,1.,7.,30.,60.,90.,120.,150.],
        purpose='Isolate temporal then radial error in each independent method at the same n, nc and maximum step. Preserve raw final-interval separation and reported common-history differences. No native dispatch.'))


def run():
    disks()
    plan=read(PLAN)
    signature=digest(PLAN)
    assert all(digest(ROOT/name)==value for name,value in plan['sources'].items())
    assert digest(PACKAGE/'controller.zip')==plan['archive_sha256']
    nodal_path=ROOT/'validation/whole_event_interval_refinement.json'
    if not (SECTOR/'complete.json').exists():
        raise RuntimeError('Wait for the independent nodal refinement to finish')
    assert read(SECTOR/'complete.json')['sha256']==digest(nodal_path)
    nodal=read(nodal_path)
    assert nodal['source_sha256']==digest(ROOT/'model/check_whole_event_intervals.py') and not nodal['native']
    if (WORK/'complete.json').exists():
        done=read(WORK/'complete.json')
        assert done['audit_sha256']==digest(OUT) and done['plan_sha256']==signature
        return
    refs=parents()
    data=WORK/'cases'
    data.mkdir(parents=True,exist_ok=True)
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,stop_signal)
    cases={}
    for job in plan['jobs']:
        settings=read(PACKAGE/(job+'_settings.json'))
        case=settings['case']
        ref=refs[case]
        module=MATERIALS[settings['configuration']['case_material']]
        prior=nodal['cases'][job]
        assert prior['case']==case
        rows=[]
        previous=None
        for n,dt in plan['levels']:
            disks()
            tag=f'{job}_fv_n{n}_us{round(dt*1e6)}'
            item=dict(ref,tag=tag,n=n,nc=n//4,dt=dt)
            if not module.run_case(item,plan,signature,WORK,data):
                return
            fv_path=data/(tag+'.json')
            fv=read(fv_path)
            assert fv['tag']==tag and fv['plan_sha256']==signature
            assert fv['checkpoint_sha256']==digest(WORK/(tag+'_checkpoint.json'))
            assert fv['status']=='SURROGATE_EXHAUSTION' and not fv['eligible_for_motor_lifetime']
            assert fv['stats']['max_mass_relative_error']<1e-8 and fv['stats']['max_energy_relative_error']<1e-6
            fe_spec=next(r for r in prior['runs'] if (r['n'],r['dt_s'])==(n,dt))
            fe_path=SECTOR/f'{job}_n{n}_us{round(dt*1e6)}.json'
            assert digest(fe_path)==fe_spec['record_sha256']
            fe=read(fe_path)['result']
            ef,ev=fe['stats']['events']['exhaustion'],fv['event_bracket_s']
            gap=max(0.,max(ef[0],ev[0])-min(ef[1],ev[1]))
            metrics=compare_history(fe['stats']['samples'],fv['history'])
            row=dict(n=n,nc=n//4,dt_s=dt,FV_interval_s=ev,FE_interval_s=ef,
                end_FE_minus_FV_s=ef[1]-ev[1],raw_interval_gap_s=gap,intervals_overlap=gap==0.,
                common_stations=metrics,FV_sha256=digest(fv_path),FE_sha256=digest(fe_path),
                FV_residuals=fv['stats'])
            if previous is not None:
                row['FV_refinement_from_preceding_level']=compare(previous,fv)
            else:
                row['FV_refinement_from_preceding_level']=None
            rows.append(row)
            previous=fv
            print(job,n,dt,'finite volume',ev,'nodal FE',ef,'gap',gap,flush=True)
        cases[case]=rows
    atomic(OUT,dict(plan_sha256=signature,nodal_study_sha256=digest(nodal_path),
                    native=False,eligible_for_motor_lifetime=False,cases=cases))
    atomic(WORK/'complete.json',dict(utc=utc(),audit_sha256=digest(OUT),plan_sha256=signature))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    args=parser.parse_args()
    try:
        if args.action=='prepare':
            prepare()
        else:
            with (SHARED/'worker.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                run()
    except StorageLimitError as error:
        stop_runs(str(error))
        raise
