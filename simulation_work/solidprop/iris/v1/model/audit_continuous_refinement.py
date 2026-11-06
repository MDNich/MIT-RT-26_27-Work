"""Compare terminal independent finite-row records under matched configurations."""
import copy
import json

import numpy as np

from continuous_heating_campaign import PLAN, WORK, OUT, decode_state, digest
from continuous_heating_refinement import PLAN as REFINE_PLAN
from ops import ROOT, atomic, disks, utc
from radial_model import RadialModel


def physical_configuration(cfg):
    # Remove only known discretization and provenance fields. All other
    # parameters, including removal threshold and heating, must match exactly.
    value = copy.deepcopy(cfg)
    for key in ('expected_nodes', 'expected_elements', 'macro_dt_s'):
        del value[key]
    for key in ('phenolic_radial_rows', 'aluminium_radial_rows'):
        del value['geometry'][key]
    value['provenance'].pop('continuous_refinement', None)
    return value


def read_record(item, sources, plan_sha):
    path = OUT/(item['tag']+'.json')
    checkpoint = WORK/(item['tag']+'_checkpoint.json')
    r = json.loads(path.read_text())
    cp = json.loads(checkpoint.read_text())
    state = decode_state(cp['state'])
    assert r['source_hashes'] == sources and r['configuration'] == item['configuration']
    assert r['plan_sha256'] == cp['plan_sha256'] == plan_sha and r['tag'] == item['tag']
    assert r['status'] == 'MODEL_EXHAUSTION_UNVALIDATED' and r['post_scope_continuation']
    assert not r['eligible_for_motor_lifetime'] and not r['numerical_convergence_established']
    assert r['energy_balance_passed'] and r['mass_balance_passed']
    assert r['max_energy_relative_error'] < 1e-6 and r['max_mass_relative_error'] < 1e-8
    model = RadialModel(r['configuration'])
    h = r['history']
    assert cp['history'] == h and r['final'] == h[-1] == model.summary(state)
    assert h[0] == model.summary(model.initial()) and h[-1]['remaining_mm'] == 0.
    t = np.array([x['time_s'] for x in h])
    assert np.all(np.diff(t)>0)
    rows = np.array([x['layer'] for x in h])
    assert np.all((np.diff(rows)==0) | (np.diff(rows)==1))
    assert rows[-1] == state.layer == model.np and cp['model']['steps'] == r['steps']
    thickness = 1000. * (model.r[model.np] - model.r[rows])
    assert np.allclose(thickness, [x['remaining_mm'] for x in h], rtol=0, atol=1e-12)
    event, flag = r['model_exhaustion_bracket_s'], r['property_limit_bracket_s']
    assert cp['model']['event_bracket'] == event and cp['model']['property_bracket'] == flag
    assert 0 < flag[0] < flag[1] < event[0] < event[1] == state.time
    assert event[1]-event[0] <= r['configuration']['macro_dt_s']+1e-10
    candidates = [x for x in h if x['case_property_range_exceeded']]
    assert candidates[0]['time_s'] == flag[1]
    for x in h:
        assert np.all(np.isfinite(list(x.values()))) and x['solid_remaining_kg_per_rad_m'] >= -1e-12
    initial = h[0]['solid_remaining_kg_per_rad_m']
    residual = abs(initial-state.gas_total-state.char_total-state.eject_total)/initial
    assert residual < 1e-10
    evidence = dict(record_sha256=digest(path), checkpoint_sha256=digest(checkpoint), steps=r['steps'],
                    model_exhaustion_bracket_s=event, property_limit_bracket_s=flag,
                    cumulative_mass_relative_residual=residual, max_step_equation_energy_residual=r['max_energy_relative_error'])
    return r, evidence


def compare(first, second):
    a, b = first['history'], second['history']
    ta, tb = [x['time_s'] for x in a], [x['time_s'] for x in b]
    stop = min(ta[-1], tb[-1])
    ticks = np.arange(0., stop, .5)
    # Thickness is piecewise constant and every row event is stored; no
    # interpolation across a row loss. Also check its entire common history.
    changes = np.unique(np.r_[ta, tb, stop])
    def differences(query):
        def sample(h, t):
            idx = np.searchsorted(t, query, side='right')-1
            return np.array([x['remaining_mm'] for x in h])[idx]
        return abs(sample(a, ta)-sample(b, tb))
    tick_diff = differences(ticks)
    common = changes[changes <= stop]
    full_diff = differences(common)
    gate = max(.02, .01*a[0]['remaining_mm'])
    ba, bb = first['model_exhaustion_bracket_s'], second['model_exhaustion_bracket_s']
    pct = 100.*abs(bb[1]-ba[1])/bb[1]
    diagnostics = {}
    for field in ('hot_C','interface_C','outer_C'):
        # Sampled temperatures are continuous interpolants across saved output.
        # They cannot resolve within-step or instantaneous row-handoff peaks.
        z = abs(np.interp(ticks, ta, [x[field] for x in a]) - np.interp(ticks, tb, [x[field] for x in b]))
        diagnostics[field] = dict(max_abs_K=float(max(z)), at_s=float(ticks[np.argmax(z)]))
    return dict(event_change_s=bb[1]-ba[1], event_abs_percent_finer=pct, event_change_under_5_percent=pct<5.,
                event_brackets_overlap=max(ba[0],bb[0]) <= min(ba[1],bb[1]), thickness_threshold_mm=gate,
                half_second_max_thickness_difference_mm=float(max(tick_diff)),
                half_second_max_at_s=float(ticks[np.argmax(tick_diff)]),
                half_second_thickness_pass=bool(max(tick_diff)<=gate+1e-12),
                entire_common_max_thickness_difference_mm=float(max(full_diff)),
                entire_common_max_at_s=float(common[np.argmax(full_diff)]),
                entire_common_thickness_pass=bool(max(full_diff)<=gate+1e-12),
                sampled_temperature_differences=diagnostics)


def main():
    disks()
    plans = {}
    records = {}
    evidence = {}
    for path, receipt_name in [(PLAN,'complete.json'),(REFINE_PLAN,'refinement_complete.json')]:
        sha = digest(path)
        plan = json.loads(path.read_text())
        assert json.loads((WORK/receipt_name).read_text())['plan_sha256'] == sha
        for name, archive in plan['archived_sources'].items():
            assert digest(ROOT/archive) == digest(ROOT/name) == plan['source_hashes'][name]
        plans[path.name] = sha
        for item in plan['cases']:
            r, e = read_record(item, plan['source_hashes'], sha)
            records[item['tag']], evidence[item['tag']] = r, e
    assert plan['scout_plan_sha256'] == plans[PLAN.name]
    comparisons = {}
    for case in ('sustainer_al','sustainer_cf','booster_al','booster_cf'):
        trio = [records[f'{case}_continuous_{suffix}'] for suffix in ['scout_n160','time_half_n160','joint_n320']]
        c0,c1,c2 = [r['configuration'] for r in trio]
        assert physical_configuration(c0) == physical_configuration(c1) == physical_configuration(c2)
        assert c0['macro_dt_s'] == 2*c1['macro_dt_s'] == 2*c2['macro_dt_s']
        for key, n in [('phenolic_radial_rows',160),('aluminium_radial_rows',40)]:
            assert [x['geometry'][key] for x in (c0,c1,c2)] == [n,n,2*n]
        comparisons[case] = dict(fixed_mesh_time=compare(*trio[:2]),fixed_step_mesh=compare(*trio[1:]))
    out = dict(checked_utc=utc(), records_audited=True, plans=plans,
               audit_source_sha256=digest(__file__), records=evidence, comparisons=comparisons,
               eligible_for_motor_lifetime=False, numerical_convergence_established=False,
               qualification='Two step ceilings and two meshes in the inherited finite-row independent surrogate. '
                  'Every exhaustion event follows a casing property flag. Native event and material validation remain open. '
                  'Discrete mass and equation-energy audits do not validate open-system enthalpy.')
    atomic(ROOT/'validation/continuous_heating_refinement_audit.json',out)
    print(json.dumps(comparisons,indent=2))


if __name__ == '__main__':
    main()
