"""Compare independent mesh and time refinements of both prescribed-backing MAPDL windows."""
import json
from pathlib import Path

import numpy as np

from audit_native_cf_tail import JOBS, sources
from continuous_heating_campaign import digest
from ops import ROOT, TMP, atomic, disks
from prepare_native_cf_tail import AUDIT, PACKAGE, PLAN


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def series(job):
    config, _ = sources(job)
    run = TMP/'runs'/('cf_tail_r3_'+job)
    audit_path = ROOT/'validation'/('native_cf_terminal_window_'+job+'.json')
    audit = read(audit_path)
    terminal = read(run/'guest_terminal.json')
    intent = read(run/'intent.json')
    deck_sha = config['deck_sha256']
    check(audit['passed'] and terminal['job'] == config['job'] == intent['case'] == job and
          terminal['exit_code'] == 0 and terminal['nonce'] == intent['nonce'] == read(run/'guest_launch.json')['nonce'],
          'Incorrect native job or launch identity')
    check(audit['comparison_sha256'] == digest(PACKAGE/(job+'.json')) and
          audit['terminal_sha256'] == digest(run/'guest_terminal.json') and
          terminal['guest_input_sha256'].lower() == intent['deck_sha256'] == deck_sha ==
          digest(PACKAGE/(job+'.inp')) == digest(run/(job+'.inp')), 'Native input or receipt differs')
    for name in [job+'.out','tail_steps.txt','tail_field.txt']:
        check(digest(run/name) == audit['files'][name] == terminal['guest_sha256'][name].lower(),
              'Native export hash differs: '+name)
    steps = np.loadtxt(run/'tail_steps.txt')
    count, ring, nodes = audit['increment_count'], config['ringsize'], config['nodes']
    check(steps.shape == (count,8) and np.array_equal(steps[:,0],np.arange(1,count+1)), 'Step count differs')
    # Each terminal field was independently checked for completeness and node order
    # in the primary audit. Recover the area-weighted temperature of the hot ring.
    field = np.loadtxt(run/'tail_field.txt', usecols=3).reshape(count,nodes)
    axial = np.ones(config['geometry']['axial_divisions']+1)
    angular = np.ones(config['geometry']['angular_divisions']+1)
    axial[[0,-1]] = angular[[0,-1]] = .5
    weights = np.outer(angular,axial).ravel()
    check(len(weights) == ring, 'Hot-face ring has the wrong number of nodes')
    radius, outer = config['radius_m']
    history = np.column_stack((
        np.r_[0.,steps[:,1]],
        1000.*(outer-np.r_[radius,steps[:,5]]),
        np.r_[config['initial_nodal_C'][0],field[:,:ring]@(weights/weights.sum())]))
    check(np.isfinite(history).all() and np.all(np.diff(history[:,0])>0) and
          np.all(np.diff(history[:,1])<0) and abs(history[-1,1])<1e-7 and
          history[-1,0] == audit['remaining_time_s'], 'Discontinuous history or missing exhaustion')
    summary = dict(job=job, n=config['n'], dt_s=config['dt'], steps=count, duration_s=history[-1,0],
                   evidence_sha256=digest(audit_path), max_field_error_K=audit['max_all_node_error_K'],
                   absolute_energy_error_fraction=audit['absolute_energy_error_fraction'],
                   max_mass_relative=audit['max_mass_relative'])
    return config, history, summary


def compare(a,b):
    # The maximum absolute difference between two piecewise linear functions
    # is attained at a knot of either curve. Compare only their common domain.
    stop = min(a[-1,0],b[-1,0])
    t = np.union1d(a[a[:,0]<=stop,0], b[b[:,0]<=stop,0])
    check(t[0] == a[0,0] == b[0,0] == 0. and t[-1] == stop and stop>0, 'Incomplete common interval')
    delta = [np.interp(t,b[:,0],b[:,col])-np.interp(t,a[:,0],a[:,col]) for col in (1,2)]
    overlap=max(a[-2,0],b[-2,0])<=stop
    return dict(common_interval_s=[0.,stop], knots=len(t), event_delta_s=b[-1,0]-a[-1,0],
                last_step_brackets_overlap=bool(overlap),
                event_relative=abs(b[-1,0]-a[-1,0])/b[-1,0],
                max_thickness_delta_mm=max(abs(delta[0])),max_hot_face_delta_K=max(abs(delta[1])))


def main():
    disks()
    audit = read(AUDIT)
    check(digest(AUDIT) == read(PACKAGE/'manifest.json')['audit_sha256'] and
          digest(PLAN) == audit['plan_sha256'], 'Independent donor audit or settings changed')
    groups = {}
    for case in ('sustainer_cf','booster_cf'):
        rows = [series(job) for job in JOBS if job.startswith('tail'+case[0])]
        config, ref, _ = rows[-1]
        item = next(i for i in read(PLAN)['cases'] if i['case']==case and i['variant']=='fine')
        donor = ROOT/'validation/cf_backing_cases'/(item['tag']+'.json')
        check(digest(donor) == audit['records'][item['tag']]['sha256'] == config['donor_sha256'], 'Wrong starting profile')
        check([(r[0]['n'],r[0]['dt']) for r in rows]==[(20,.01),(40,.01),(40,.005)],
              'Refinement does not separate mesh and time')
        for c, _, _ in rows:
            check(c['case']==case and all(c[k]==config[k] for k in
                  ('donor_sha256','radius_m','start_s','backing_trace','independent_full_event_s')), 'Inconsistent donor history')
        pairs = {label:compare(a[1],b[1]) for label,a,b in zip(('mesh','time'),rows,rows[1:])}
        thickness_limit = max(.02,.01*ref[0,1])
        check(all(p['last_step_brackets_overlap'] and p['event_relative']<.05 and p['max_thickness_delta_mm']<=thickness_limit
                  for p in pairs.values()), 'Native window refinement exceeds event/thickness target')
        groups[case] = dict(start_s=config['start_s'], initial_mm=ref[0,1],
                            independent_event_s=config['independent_full_event_s'],
                            donor_sha256=config['donor_sha256'], thickness_limit_mm=thickness_limit,
                            jobs=[r[2] for r in rows], pairs=pairs,
                            # Downsample only the published graph. All comparisons above use every knot.
                            history=ref[np.unique(np.linspace(0,len(ref)-1,151,dtype=int))].tolist())
    atomic(ROOT/'validation/native_cf_window_refinement.json',dict(
        passed=True, scope='Native near-pure-char end windows with prescribed CF backing. Time zero is the donor handoff.',
        source_sha256=digest(Path(__file__)), manifest_sha256=digest(PACKAGE/'manifest.json'),
        history_columns=['elapsed_s','remaining_mm','hot_C'], cases=groups))


if __name__=='__main__':
    main()
