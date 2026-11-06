"""Exercise the frozen independent runner's real disk checkpoint and resume paths.

All mutable paths are a temporary verification fixture with new geometry.
The operating campaign, its workers, locks and checkpoints are never opened.
"""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import continuous_heating_campaign as runner
from ops import ROOT, TMP, atomic, disks, utc


def fixture_run(directory, item, plan, sha, interrupt):
    work, out = directory/'work', directory/'out'
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=True)
    with patch.multiple(runner, WORK=work, OUT=out, STOP=False):
        if interrupt:
            original = runner.RadialModel.step
            def request_checkpoint(model, state, dt):
                result = original(model, state, dt)
                if result is not None and result.layer >= 2:
                    runner.STOP = True
                return result
            with patch.object(runner.RadialModel, 'step', request_checkpoint):
                runner.run_case(item,plan,sha)
        else:
            runner.run_case(item,plan,sha)
    return work, out


def main():
    disks()
    plan = json.loads(runner.PLAN.read_text())
    item = copy.deepcopy(plan['cases'][0])
    cfg = item['configuration']
    g = cfg['geometry']
    # A 0.08 mm synthetic coupon keeps this integration test short.
    g['phenolic_thickness_m'] = .00008
    case_thickness = g['outer_radius_m']-g['phenolic_outer_radius_m']
    g['phenolic_outer_radius_m'] = g['inner_radius_m']+g['phenolic_thickness_m']
    g['outer_radius_m'] = g['phenolic_outer_radius_m']+case_thickness
    g.update(phenolic_radial_rows=16,aluminium_radial_rows=4)
    cfg.update(end_time_s=30.,macro_dt_s=.0015625,case_property_limit_C=22.01,
               expected_elements=20*g['faces_per_row'],
               expected_nodes=21*(g['angular_divisions']+1)*(g['axial_divisions']+1))
    item.update(tag='checkpoint_coupon',case='synthetic_coupon')
    plan.update(cases=[item],milestone_times_s=[.5, 2., 4., 8., 15., 30.])
    sha = hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    with TemporaryDirectory(prefix='checkpoint_test_',dir=TMP) as temp:
        root = Path(temp)
        uninterrupted, out0 = fixture_run(root/'reference',item,plan,sha,False)
        resumed, out1 = fixture_run(root/'split',item,plan,sha,True)
        stop = json.loads((resumed/'status.json').read_text())
        assert stop['status'] == 'PAUSED_BY_SIGNAL' and stop['layer'] == 2
        assert stop['property_limit_bracket_s'] and not (out1/'checkpoint_coupon.json').exists()
        fixture_run(root/'split',item,plan,sha,False)
        a,b = [json.loads((d/'checkpoint_coupon.json').read_text()) for d in (out0,out1)]
        for record in (a,b):
            record.pop('checked_utc')
        assert a == b and a['status'] == 'MODEL_EXHAUSTION_UNVALIDATED'
        reference_sha, resumed_sha = [runner.digest(d/'checkpoint_coupon_checkpoint.json') for d in (uninterrupted,resumed)]
        assert reference_sha == resumed_sha
    atomic(ROOT/'validation/continuous_checkpoint_verification.json',dict(checked_utc=utc(),passed=True,
           runner_sha256=runner.digest(runner.__file__),reference_model_sha256=runner.digest(ROOT/'model/radial_model.py'),
           test_sha256=runner.digest(__file__),fixture_plan_sha256=sha,paused_time_s=stop['time_s'],
           paused_rows=stop['layer'],terminal_checkpoint_sha256=reference_sha,
           full_record_equal_excluding_timestamp=True,terminal_checkpoint_byte_equal=True,
           qualification='Synthetic thin coupon verification of restart after row removal and property flag, '
                         'including retained histories and final event. Fixture times are not motor data.'))
    print('Terminal histories, event brackets and serialized state match.')


if __name__ == '__main__':
    main()
