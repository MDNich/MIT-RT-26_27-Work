"""Recover a coupled moving-wall integration from its on-disk accepted state."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from continuous_heating_campaign import digest
from moving_surface_campaign import run_case, PARENT
from ops import ROOT, TMP, atomic, disks, utc


def main():
    disks()
    item = json.loads(PARENT.read_text())['cases'][1]
    cfg = item['configuration']
    g = cfg['geometry']
    g.update(phenolic_thickness_m=.00016,phenolic_outer_radius_m=g['inner_radius_m']+.00016,
             outer_radius_m=g['inner_radius_m']+.00016+g['aluminium_thickness_m'])
    cfg.update(initial_temperature_C=350.,case_property_limit_C=351.)
    item.update(tag='synthetic_checkpoint_wall',n=18,nc=8,dt=.04)
    plan = dict(horizon_s=40.,profile_times_s=[0.,1.,2.,7.],cases=[item])
    tag = item['tag']
    with TemporaryDirectory(dir=TMP) as temporary:
        d = Path(temporary)
        atomic(d/'fixture_plan.json',plan)
        sha = digest(d/'fixture_plan.json')
        assert run_case(item,plan,sha,d/'full',d/'reference')
        assert not run_case(item,plan,sha,d/'split',d/'resumed',stop_after=100)
        middle = json.loads((d/'split'/f'{tag}_checkpoint.json').read_text())
        assert 0<len(middle['state']['virgin'])<18 and middle['scope_bracket_s']
        assert run_case(item,plan,sha,d/'split',d/'resumed')
        final = json.loads((d/'resumed'/f'{tag}.json').read_text())
        assert final['event_bracket_s'] and final['profiles'][-1]['liner_edges_m']==[g['phenolic_outer_radius_m']]
        assert digest(d/'resumed'/f'{tag}.json')==digest(d/'reference'/f'{tag}.json')
        assert digest(d/'split'/f'{tag}_checkpoint.json')==digest(d/'full'/f'{tag}_checkpoint.json')
    atomic(ROOT/'validation/moving_surface_checkpoint_verification.json',dict(checked_utc=utc(),passed=True,
           worker_sha256=digest(ROOT/'model/moving_surface_campaign.py'),test_sha256=digest(__file__),
           fixture_plan_sha256=sha,checkpoint_accepted_steps=100,remaining_cells_at_pause=len(middle['state']['virgin']),
           post_scope_at_pause=True,terminal_checkpoint_byte_equal=True,terminal_record_byte_equal=True,
           scope='Synthetic verification of the independent coupled restart, profiles, shared times and event ledger.'))
    print('Coupled checkpoint and full result are byte-identical after restart.')


if __name__=='__main__':
    main()
