"""Checkpointed continuous-heating diagnostics, never relabelled native ANSYS.

Extends the current reference equations to identify exhaustion and the earlier
property-range crossing. Post-range states are mathematical continuations with
the explicitly retained casing surrogate. They are not physical predictions.
"""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
import signal
import time
from pathlib import Path

import numpy as np
from ops import ROOT, TMP, atomic, disks, host_check, utc
from radial_model import RadialModel, State

CASES = ['sustainer_al', 'sustainer_cf', 'booster_al', 'booster_cf']
PLAN = ROOT / 'configs/continuous_heating_campaign.json'
WORK = TMP / 'continuous_heating'
OUT = ROOT / 'validation/continuous_heating'
STOP = False


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    return {str(p.relative_to(ROOT)): digest(p) for p in
            [Path(__file__), ROOT / 'model/radial_model.py', ROOT / 'model/coupler.py']}


def prepare():
    disks()
    if PLAN.exists():
        raise RuntimeError('Existing campaign is immutable; inspect it, do not regenerate.')
    sources = source_hashes()
    archive = ROOT / 'validation/source_archive'
    archived = {}
    for name, sha in sources.items():
        p = ROOT / name
        dest = archive / f'{p.stem}_{sha}{p.suffix}'
        if dest.exists():
            assert digest(dest) == sha
        else:
            dest.write_bytes(p.read_bytes())
        archived[name] = str(dest.relative_to(ROOT))
    cases = []
    for case in CASES:
        source = ROOT / 'configs' / f'{case}_pulse7_midpoint_joint320_geom005_smp10.json'
        cfg = json.loads(source.read_text())
        cfg.update(end_time_s=960., macro_dt_s=.0015625,
                   stop_at_case_property_limit=False,
                   campaign_role='independent_continuous_heating_diagnostic')
        cfg['geometry'].update(phenolic_radial_rows=160, aluminium_radial_rows=40)
        cfg['expected_elements'] = 200 * cfg['geometry']['faces_per_row']
        cfg['expected_nodes'] = 201 * (cfg['geometry']['angular_divisions'] + 1) * (cfg['geometry']['axial_divisions'] + 1)
        cfg['heating'].pop('pulse_duration_s', None)
        cfg['provenance']['exposure'] = ('User November 5 authorizes duration choice. Continuous imposed heating; '
            'milestones 30/60/120/240/480/960 s, stopping on model exhaustion or 960 s. '
            'This is not an inferred propellant burn duration.')
        cfg['provenance']['continuous_parent'] = dict(file=str(source.relative_to(ROOT)), sha256=digest(source))
        cfg['provenance']['post_scope'] = ('Preserve and report first 150 C CF/300 C Al property-range crossing; '
            'subsequent temperatures/exhaustion use the unchanged extrapolated/clamped casing surrogate. '
            'No post-scope result is accepted as physical motor performance.')
        cases.append(dict(case=case, tag=f'{case}_continuous_scout_n160', configuration=cfg))
    plan = dict(created_utc=utc(), independent_only=True, status='PREPARED',
                source_hashes=sources, archived_sources=archived, cases=cases,
                milestone_times_s=[30, 60, 120, 240, 480, 960],
                stop_at_case_property_limit=False, record_first_property_crossing=True,
                numerical_convergence_established=False, eligible_for_motor_lifetime=False,
                qualification='New continuous-heating mathematical scouts, not accepted burnthrough predictions. '
                'Earlier rejected endurance results stay rejected. No ANSYS package is changed.')
    atomic(PLAN, plan)
    print(PLAN)


def encode_state(state):
    return {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in asdict(state).items()}


def decode_state(values):
    values = values.copy()
    for key in ['T', 'alpha', 'consumed']:
        values[key] = np.array(values[key], dtype=float)
    return State(**values)


def stop_signal(_signum, _frame):
    global STOP
    STOP = True


def run_case(item, plan, plan_sha):
    disks()
    cfg, tag = item['configuration'], item['tag']
    result_path = OUT / f'{tag}.json'
    if result_path.exists():
        result = json.loads(result_path.read_text())
        assert result['plan_sha256'] == plan_sha
        print('Already recorded', tag, flush=True)
        return
    model = RadialModel(cfg)
    checkpoint = WORK / f'{tag}_checkpoint.json'
    attrs = ['steps', 'max_energy_error', 'max_mass_error', 'max_alpha_increment',
             'max_retained_fraction', 'event_bracket', 'property_bracket']
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text())
        assert saved['plan_sha256'] == plan_sha
        s, history = decode_state(saved['state']), saved['history']
        for key in attrs:
            setattr(model, key, saved['model'][key])
    else:
        s = model.initial()
        history = [model.summary(s)]
    last_write = time.monotonic()
    next_record = history[-1]['time_s'] + .5

    def save(status):
        host_check()
        atomic(checkpoint, dict(plan_sha256=plan_sha, state=encode_state(s), history=history,
                               model={k: getattr(model, k) for k in attrs}))
        atomic(WORK / 'status.json', dict(checked_utc=utc(), tag=tag, status=status,
            time_s=s.time, steps=model.steps, layer=s.layer, total_layers=model.np,
            property_limit_bracket_s=model.property_bracket,
            model_exhaustion_bracket_s=model.event_bracket,
            numerical_convergence_established=False, eligible_for_motor_lifetime=False,
            plan_sha256=plan_sha))

    save('RUNNING')
    while s.time < cfg['end_time_s'] - 1e-9 and s.layer < model.np:
        if model.steps % 200 == 0:
            host_check()
        if STOP:
            save('PAUSED_BY_SIGNAL')
            return
        dt = min(cfg['macro_dt_s'], cfg['end_time_s'] - s.time)
        # Land exactly on reporting milestones without restarting the solution.
        future = [t for t in plan['milestone_times_s'] if t > s.time + 1e-9]
        if future:
            dt = min(dt, future[0] - s.time)
        while True:
            new = model.step(s, dt)
            if new is not None:
                break
            dt /= 2
            if dt < 1e-6:
                save('NUMERICAL_FAILURE')
                raise RuntimeError(('Step convergence failed', tag, s.time))
        old = s
        s = new
        crossed = s.T[model.np] > cfg['case_property_limit_C']
        if crossed and model.property_bracket is None:
            model.property_bracket = [old.time, s.time]
        event = s.layer != old.layer
        milestone = any(abs(s.time - t) < 1e-8 for t in plan['milestone_times_s'])
        if s.time >= next_record - 1e-9 or event or milestone or (crossed and model.property_bracket[1] == s.time):
            history.append(model.summary(s))
            next_record = s.time + .5
        if time.monotonic() - last_write > 20:
            disks()
            save('RUNNING')
            print(tag, f'{s.time:.6f}s', 'rows', s.layer, 'scope', model.property_bracket, flush=True)
            last_write = time.monotonic()
    if history[-1]['time_s'] != s.time:
        history.append(model.summary(s))
    status = 'MODEL_EXHAUSTION_UNVALIDATED' if s.layer == model.np else 'HORIZON_WITHOUT_EXHAUSTION'
    save(status)
    atomic(result_path, dict(checked_utc=utc(), tag=tag, method='Independent radial FE; NOT ANSYS',
        plan_sha256=plan_sha, source_hashes=plan['source_hashes'], configuration=cfg,
        status=status, model_exhaustion_bracket_s=model.event_bracket,
        property_limit_bracket_s=model.property_bracket, post_scope_continuation=model.property_bracket is not None,
        eligible_for_motor_lifetime=False, numerical_convergence_established=False,
        energy_balance_passed=model.max_energy_error < 1e-6,
        mass_balance_passed=model.max_mass_error < 1e-8,
        max_energy_relative_error=model.max_energy_error, max_mass_relative_error=model.max_mass_error,
        final=history[-1], history=history, steps=model.steps,
        qualification='Conditional mathematical continuation of the inherited finite-row erosion closure. '
        'Numerical refinement, conservative moving-surface model and high-temperature material support remain required. '
        'An exhaustion event is not accepted physical motor burnthrough.'))
    print(tag, status, model.event_bracket, flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare', 'run'])
    args = p.parse_args()
    if args.action == 'prepare':
        prepare()
        return
    disks()
    WORK.mkdir(exist_ok=True)
    with (WORK / 'worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = json.loads(PLAN.read_text())
        assert source_hashes() == plan['source_hashes'], 'Campaign sources changed; do not mix versions'
        plan_sha = digest(PLAN)
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, stop_signal)
        try:
            for item in plan['cases']:
                run_case(item, plan, plan_sha)
                if STOP:
                    return
        except Exception as exc:
            # Preserve checkpoints; the global storage watcher owns any latched stop.
            try:
                host_check()
            except RuntimeError:
                pass
            else:
                atomic(WORK / 'worker_error.json', dict(checked_utc=utc(), error=repr(exc)))
            raise
        atomic(WORK / 'complete.json', dict(checked_utc=utc(), plan_sha256=plan_sha,
            independent_only=True, eligible_for_motor_lifetime=False))


if __name__ == '__main__':
    main()
