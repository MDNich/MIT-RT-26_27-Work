"""Continue the independent comparison after reproducing an output-time roundoff failure."""
import argparse
import fcntl
import importlib.util
import os
from pathlib import Path
import signal

from audit_moving_surface import compare
from backing_film_campaign import MATERIALS, parents, read
from check_whole_event_intervals import WORK as NODAL_WORK
from compare_matched_event_intervals import PLAN as PARENT, WORK as PRIOR
from compare_native_whole_exposures import compare_history
from continuous_heating_campaign import digest
from moving_surface_campaign import SHARED, stop_signal
from ops import ROOT, TMP, StorageLimitError, atomic, disks, stop_runs, utc

PACKAGE = ROOT/'configs/matched_event_recovery'
PLAN = PACKAGE/'manifest.json'
WORK = TMP/'matched_event_recovery'
OUT = ROOT/'validation/matched_event_recovery.json'
NODAL = ROOT/'validation/whole_event_interval_refinement.json'
FAILED = 'wall2ba_fv_n320_us2500'


def output_step(now, target, maximum):
    """Reach the output station without a tiny separate thermal solution."""
    remaining = target-now
    if not remaining > 0 or not maximum > 0:
        raise ValueError('Expected a future station and positive step')
    if maximum < remaining < 1.05*maximum:
        return remaining/2
    return min(maximum, remaining)


def prepare():
    if PACKAGE.exists():
        raise FileExistsError(PACKAGE)
    parent = read(PARENT)
    assert all(digest(ROOT/name) == value for name,value in parent['sources'].items())
    records, checkpoints = {}, {}
    for path in sorted((PRIOR/'cases').glob('*.json')):
        row = read(path)
        assert row['plan_sha256'] == digest(PARENT) and row['status'] == 'SURROGATE_EXHAUSTION'
        cp = PRIOR/(row['tag']+'_checkpoint.json')
        assert row['checkpoint_sha256'] == digest(cp) and path.stem == row['tag']
        records[row['tag']] = digest(path)
        checkpoints[row['tag']] = digest(cp)
    cp = PRIOR/(FAILED+'_checkpoint.json')
    assert read(cp)['plan_sha256'] == digest(PARENT) and FAILED not in records and len(records)==7
    checkpoints[FAILED] = digest(cp)
    # Preserve the exact prior drivers and apply one change to output scheduling.
    # Store ordinary Python sources so both the executed code and diff are inspectable.
    PACKAGE.mkdir()
    drivers = {}
    for material, module in MATERIALS.items():
        source = Path(module.__file__).read_text()
        old_time = 'old' if material == 'al' else 's.time'
        original = f"min(item['dt'],target-{old_time})"
        assert source.count(original) == 1
        source = source.replace(original, f"output_step({old_time},target,item['dt'])")
        source = source.replace('import argparse','from recover_matched_intervals import output_step\nimport argparse',1)
        destination = PACKAGE/(material+'_driver.py')
        destination.write_text(source)
        drivers[material] = digest(destination)
    atomic(PLAN,dict(parent_sha256=digest(PARENT),runner_sha256=digest(__file__),
                     nodal_sha256=digest(NODAL),drivers=drivers,parent_records=records,
                     parent_checkpoints=checkpoints,restart_tag=FAILED,restart_time_s=read(cp)['state']['time'],
                     failed_time_s=141.99999999989996,failed_requested_dt_s=1.000444171950221e-10,
                     rejected_energy_residual_J_per_rad_m=-4.4530598263501655e-6,
                     change='Half the remaining interval if it is between 1 and 1.05 maximum steps. Keep every thermal, mass and energy tolerance.'))


def drivers(plan):
    modules = {}
    for material, fingerprint in plan['drivers'].items():
        path = PACKAGE/(material+'_driver.py')
        assert digest(path) == fingerprint
        spec = importlib.util.spec_from_file_location('recovered_'+material, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[material] = module
    return modules


def run():
    plan, parent = read(PLAN), read(PARENT)
    assert digest(__file__)==plan['runner_sha256'] and digest(PARENT)==plan['parent_sha256']
    assert all(digest(ROOT/name)==value for name,value in parent['sources'].items())
    assert digest(NODAL)==plan['nodal_sha256']==read(NODAL_WORK/'complete.json')['sha256']
    if (WORK/'complete.json').exists():
        assert read(WORK/'complete.json')['audit_sha256']==digest(OUT)
        return
    nodal = read(NODAL)
    refs = parents()
    revised = drivers(plan)
    case_dir = WORK/'cases'
    case_dir.mkdir(parents=True,exist_ok=True)
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,stop_signal)
    atomic(WORK/'worker.json',dict(pid=os.getpid(),utc=utc(),plan_sha256=digest(PLAN)))
    cp_name = FAILED+'_checkpoint.json'
    assert digest(PRIOR/cp_name)==plan['parent_checkpoints'][FAILED]
    if not (WORK/cp_name).exists():
        cp = read(PRIOR/cp_name)
        assert cp['state']['time']==plan['restart_time_s'] and cp['plan_sha256']==digest(PARENT)
        # The new checkpoint inherits every state, accumulated flux and history entry.
        atomic(WORK/cp_name,dict(cp,plan_sha256=digest(PLAN)))
    cases = {}
    for job in parent['jobs']:
        prior = nodal['cases'][job]
        case = prior['case']
        rows, previous = [], None
        for n,dt in parent['levels']:
            disks()
            tag = f'{job}_fv_n{n}_us{round(dt*1e6)}'
            if tag in plan['parent_records']:
                path = PRIOR/'cases'/(tag+'.json')
                cp_path = PRIOR/(tag+'_checkpoint.json')
                assert digest(path)==plan['parent_records'][tag] and digest(cp_path)==plan['parent_checkpoints'][tag]
                signature = digest(PARENT)
            else:
                ref = refs[case]
                item = dict(ref,tag=tag,n=n,nc=n//4,dt=dt)
                signature = digest(PLAN)
                if not revised[ref['configuration']['case_material']].run_case(item,parent,signature,WORK,case_dir):
                    return
                path = case_dir/(tag+'.json')
                cp_path = WORK/(tag+'_checkpoint.json')
            fv = read(path)
            assert fv['tag']==tag and fv['plan_sha256']==signature and fv['checkpoint_sha256']==digest(cp_path)
            assert fv['status']=='SURROGATE_EXHAUSTION' and not fv['eligible_for_motor_lifetime']
            assert fv['stats']['max_mass_relative_error']<1e-8 and fv['stats']['max_energy_relative_error']<1e-6
            fe_path = NODAL_WORK/f'{job}_n{n}_us{round(dt*1e6)}.json'
            summary = next(r for r in prior['runs'] if (r['n'],r['dt_s'])==(n,dt))
            assert digest(fe_path)==summary['record_sha256']
            fe = read(fe_path)['result']['stats']
            ef, ev = fe['events']['exhaustion'], fv['event_bracket_s']
            gap = max(0.,max(ef[0],ev[0])-min(ef[1],ev[1]))
            rows.append(dict(n=n,nc=n//4,dt_s=dt,FV_interval_s=ev,FE_interval_s=ef,
                end_FE_minus_FV_s=ef[1]-ev[1],raw_interval_gap_s=gap,intervals_overlap=gap==0.,
                common_stations=compare_history(fe['samples'],fv['history']),FV_sha256=digest(path),
                FV_plan_sha256=signature,FE_sha256=digest(fe_path),FV_residuals=fv['stats'],
                FV_refinement_from_preceding_level=compare(previous,fv) if previous else None))
            previous = fv
            print(tag,ev,ef,'gap',gap,flush=True)
        cases[case] = rows
    atomic(OUT,dict(plan_sha256=digest(PLAN),nodal_study_sha256=digest(NODAL),native=False,
                    eligible_for_motor_lifetime=False,cases=cases))
    atomic(WORK/'complete.json',dict(utc=utc(),plan_sha256=digest(PLAN),audit_sha256=digest(OUT)))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run'])
    try:
        disks()
        with (SHARED/'worker.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if parser.parse_args().action=='prepare':
                prepare()
            else:
                run()
    except StorageLimitError as error:
        stop_runs(str(error))
        raise
