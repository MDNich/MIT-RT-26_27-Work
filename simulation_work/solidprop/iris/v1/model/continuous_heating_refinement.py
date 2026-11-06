"""Frozen fixed-mesh/time and joint refinements of continuous scouts.

Uses the verified campaign checkpoint runner unchanged; never runs alongside
the scout worker. Even converged surrogate exhaustion is not physical validation.
"""
import argparse
import copy
import fcntl
import json
import signal
from pathlib import Path
import continuous_heating_campaign as campaign
from ops import ROOT, atomic, disks, host_check, utc

PLAN=ROOT/'configs/continuous_heating_refinement.json'


def hashes():
    return {**campaign.source_hashes(),
            str(Path(__file__).relative_to(ROOT)):campaign.digest(__file__)}


def prepare():
    disks()
    assert not PLAN.exists(), 'Inspect existing immutable refinement plan instead of regenerating'
    base=json.loads(campaign.PLAN.read_text())
    cases=[]
    # Put the sustainer Al triplet first, then all other fixed-step/joint pairs.
    for item in base['cases']:
        for name,n,dt in [('time_half_n160',160,.00078125),('joint_n320',320,.00078125)]:
            x=copy.deepcopy(item);cfg=x['configuration']
            x['tag']=f"{x['case']}_continuous_{name}"
            cfg.update(macro_dt_s=dt)
            cfg['geometry'].update(phenolic_radial_rows=n,aluminium_radial_rows=n//4)
            cfg['expected_elements']=(n+n//4)*cfg['geometry']['faces_per_row']
            cfg['expected_nodes']=(n+n//4+1)*(cfg['geometry']['angular_divisions']+1)*(cfg['geometry']['axial_divisions']+1)
            cfg['provenance']['continuous_refinement']='Fresh independent diagnostic; fixed-mesh half step or doubled mesh at the same smaller step. No physical law or cutoff change.'
            cases.append(x)
    sources=hashes();archived={}
    for name,sha in sources.items():
        p=ROOT/name;dest=ROOT/'validation/source_archive'/f'{p.stem}_{sha}{p.suffix}'
        if dest.exists():assert campaign.digest(dest)==sha
        else:dest.write_bytes(p.read_bytes())
        archived[name]=str(dest.relative_to(ROOT))
    plan={**base,'created_utc':utc(),'status':'PREPARED_NOT_DISPATCHED','cases':cases,
          'source_hashes':sources,'archived_sources':archived,
          'scout_plan_sha256':campaign.digest(campaign.PLAN),
          'qualification':'Isolated fixed-mesh time check followed by fixed-step spatial check of new continuous diagnostics. Native ANSYS and physical material validation remain separate.'}
    atomic(PLAN,plan);print(PLAN)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);args=p.parse_args()
    if args.action=='prepare':prepare();return
    disks();plan=json.loads(PLAN.read_text());assert hashes()==plan['source_hashes']
    completed=campaign.WORK/'complete.json'
    assert completed.exists() and json.loads(completed.read_text())['plan_sha256']==plan['scout_plan_sha256']
    with (campaign.WORK/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,campaign.stop_signal)
        try:
            for item in plan['cases']:
                campaign.run_case(item,plan,campaign.digest(PLAN))
                if campaign.STOP:return
        except Exception as exc:
            try:host_check()
            except RuntimeError:pass
            else:atomic(campaign.WORK/'refinement_error.json',dict(checked_utc=utc(),error=repr(exc)))
            raise
        atomic(campaign.WORK/'refinement_complete.json',dict(checked_utc=utc(),plan_sha256=campaign.digest(PLAN),eligible_for_motor_lifetime=False))


if __name__=='__main__':main()
