"""Regression checks for both signs of a one-interval removal mismatch."""
import copy
import hashlib
import json

from compare_native_pulses import identical_row_schedule
from ops import ROOT, atomic, disks, utc


def main():
    disks()
    event = dict(rows_scheduled=1, scheduled_time_s=3.48125,
                 independent_scheduled_time_s=3.48125)
    same = [dict(native_rows_scheduled=1, independent_rows_scheduled=1)]
    assert identical_row_schedule(same, [event], {1: 3.48125})
    assert identical_row_schedule([], [], {})
    for shift in [-.003125, .003125]:
        changed = copy.deepcopy(event)
        changed['independent_scheduled_time_s'] += shift
        # Equal sampled layer counts deliberately reproduce the formerly
        # missed case: the independent event preceded the native event.
        assert not identical_row_schedule(same, [changed], {1: changed['independent_scheduled_time_s']})
    assert not identical_row_schedule(same, [event], {1: 3.48125, 2: 6.54})
    absent = dict(event, independent_scheduled_time_s=None)
    assert not identical_row_schedule(same, [absent], {})
    assert not identical_row_schedule([dict(native_rows_scheduled=1, independent_rows_scheduled=2)], [event], {1: 3.48125})
    reviewed = []
    for path in sorted((ROOT/'validation').glob('native_pulse_comparison_*.json')):
        result = json.loads(path.read_text())
        if not result.get('comparison_passed'):
            continue
        events = result.get('removal_events', [])
        reference = {e['rows_scheduled']: e['independent_scheduled_time_s'] for e in events}
        assert identical_row_schedule(result['comparisons'], events, reference), path
        reviewed.append(dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             maximum_absolute_event_time_difference_s=max(
                                 [abs(e['scheduled_time_difference_s']) for e in events], default=0)))
    atomic(ROOT/'validation/comparison_event_gate_regression.json', dict(
        checked_utc=utc(), passed=True, revision='event_times_and_event_sets_v2',
        regression='Reject both one-interval timing signs despite matching sampled layer counts; reject missing/additional events.',
        prior_passing_comparisons=reviewed,
        qualification='Retrospective check covers all event times present in each saved comparison and its sampled layer counts. It does not reconstruct unsaved independent events; future comparisons also require exact equality of full event sets. No existing accepted result required withdrawal.'))
    print('Bidirectional event gate passed; prior passing comparisons checked:', len(reviewed))


if __name__ == '__main__':
    main()
