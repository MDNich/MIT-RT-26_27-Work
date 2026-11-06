"""One-factor exposure and material assumptions for the verified independent wall."""
import argparse
import copy
import fcntl
import json
import os
import signal
import sys
from pathlib import Path

import moving_surface_campaign as campaign
from continuous_heating_campaign import digest
from ops import ROOT, TMP, atomic, disks, host_check, stop_runs, StorageLimitError, utc

PLAN = ROOT/'configs/moving_surface_sensitivities.json'
WORK = TMP/'moving_surface_sensitivities'
OUT = ROOT/'validation/moving_surface_sensitivities'
AUDIT = ROOT/'validation/moving_surface_campaign_audit.json'


def cases(case):
    for h in (500,2000):
        yield f'h{h}',{'heating':{'h0_W_m2_K':h}}
    for pressure in (600,1000):
        yield f'p{pressure}',{'char_law':{'pressure_nominal_psi':pressure,'pressure_Pa':pressure*6894.757293168}}
    for emissivity in (.1,.3):
        yield f'rad{round(emissivity*100)}',{'heating':{'hot_effective_emissivity':emissivity}}
    for cost in (17.5e6,70.e6):
        yield f'cost{cost/1e6:g}',{'char_law':{'effective_endothermic_cost_J_kg':cost}}
    # Local sensitivity of the nominal gas-to-initial-solid temperature difference.
    # These are derivative probes and carry no probability or measured uncertainty.
    for factor in (.9,1.1):
        yield f'gasdelta{int(factor*100)}',{'heating':{'gas_temperature_C':22.+factor*(2230.85-22.)}}
    if case.endswith('_cf'):
        yield 'alternate_cf',{'root':{'cf_radial_k':.3832,'cf_cp_constant_J_kg_K':886.},
                               'material':{'aluminium_density_kg_m3':1596.}}


def prepare():
    disks()
    if PLAN.exists(): raise FileExistsError('Existing sensitivities are immutable')
    verified=json.loads(AUDIT.read_text())
    assert verified['cases_checked']==20 and verified['plan_sha256']==digest(campaign.PLAN)
    for group in verified['comparisons'].values():
        for k in ('320_0.04_to_640_0.04','640_0.04_to_640_0.02'):
            p=group[k]
            assert p['event_under_5_percent'] and p['brackets_overlap'] and p['thickness_pass']
    base=json.loads(campaign.PLAN.read_text()); jobs=[]
    for item in base['cases']:
        if item['n']!=320: continue
        for name,overrides in cases(item['case']):
            job=copy.deepcopy(item)
            for section,change in overrides.items():
                target=job['configuration'] if section=='root' else job['configuration'][section]
                target.update(change)
            job.update(tag=f"{item['case']}_moving_sens_{name}",scenario=name,changes=overrides)
            jobs.append(job)
    atomic(PLAN,dict(cases=jobs,created_utc=utc(),parent_plan_sha256=digest(campaign.PLAN),
                     nominal_audit_sha256=digest(AUDIT),sources=campaign.sources(),worker_sha256=digest(__file__),
                     inherited_scenarios_sha256=digest(ROOT/'model/run_input_sensitivities.py'),
                     horizon_s=base['horizon_s'],profile_times_s=base['profile_times_s'],
                     qualification='One factor at a time, 320/80 cells and nominal 0.04 s step ceiling. '
                     'Pressure, film, hot-side radiation, char cost and alternative CF tuple follow earlier scenarios. '
                     'Gas temperature probes scale nominal gas-to-ambient temperature difference by 0.9 or 1.1. '
                     'Scenario extrema are not bounds on an actual firing. Audit and refine influential cases separately.'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run'])
    action=parser.parse_args().action
    if action=='prepare':
        prepare()
        return
    disks()
    p=json.loads(PLAN.read_text()); sha=digest(PLAN)
    assert p['sources']==campaign.sources() and p['worker_sha256']==digest(__file__)
    assert digest(AUDIT)==p['nominal_audit_sha256'] and digest(campaign.PLAN)==p['parent_plan_sha256']
    with (campaign.SHARED/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,campaign.stop_signal)
        atomic(WORK/'worker.json',dict(pid=os.getpid(),started_utc=utc(),plan_sha256=sha))
        try:
            for item in p['cases']:
                if not campaign.run_case(item,p,sha,WORK,OUT): return
        except StorageLimitError as exc:
            stop_runs(str(exc))
            raise
        except Exception as exc:
            host_check()
            atomic(WORK/'error.json',dict(tag=item['tag'],utc=utc(),error=repr(exc)))
            raise
        atomic(WORK/'complete.json',dict(utc=utc(),cases=len(p['cases']),plan_sha256=sha))


if __name__=='__main__': main()
