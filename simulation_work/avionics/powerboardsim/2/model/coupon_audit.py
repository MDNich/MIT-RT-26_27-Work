"""Check the nickel unit-square tensile coupons against their native equilibria and uniaxial kinematics."""
import argparse
import re
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json


REFERENCES = ('coupon_nominal_v4', 'coupon_uniform', 'coupon_unsym')
OUTPUT = ROOT / 'validation/coupon_reference'
FIELDS = ('ux_mm', 'fx_N', 'uy_mm', 'sx_MPa', 'eppl', 'damage')


def check_states(history, solve, post):
    completed = re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED\.', solve)
    header = 'SET   TIME/FREQ    LOAD STEP   SUBSTEP  CUMULATIVE'
    block = post.split(header, 1)[1].strip().split('\n\n', 1)[0]
    sets = np.array([[float(s) for s in line.split()] for line in block.splitlines()])
    assert sets.shape[1] == 5 and np.array_equal(sets[:, 0], np.arange(1, len(sets) + 1))
    valid = sets[sets[:, 3] != 999999]
    assert np.array_equal(valid[:, 2:4], np.array(completed, dtype=int))
    assert np.array_equal(history['set'], valid[:, 0])
    assert np.allclose(history['time'], valid[:, 1], rtol=0, atol=6e-8)
    assert np.all(np.diff(history['time']) > 0)
    return len(sets) - len(valid)


def coupon_law(history, config, deck):
    # The unit-square coupon is pulled 1 mm in X over one load step. Its free width and
    # thickness have equal transverse stretches in homogeneous isotropic uniaxial tension.
    assert 'SECDATA,.15,1,0,7' in deck and 'MP,EX,1,205000' in deck and config['damage_cap'] == .9999
    assert all(card in deck for card in ('N,1,0,0,0', 'N,2,1,0,0', 'N,3,1,1,0', 'N,4,0,1,0'))
    assert np.allclose(history['ux_mm'], history['time'] * config['displacement_mm'] / config['end_time'], atol=2e-9, rtol=0)
    damage = history['damage']
    assert np.all(np.diff(damage) >= -1e-5) and damage.min() >= -1e-8 and damage.max() <= 1.000001
    assert np.all(1 + history['uy_mm'] > 0)
    area = .15 * (1 + history['uy_mm'])**2
    force_error = np.max(abs(area * history['sx_MPa'] - history['fx_N']))
    peak = np.argmax(history['fx_N'])
    effective_stress = history['sx_MPa'] / np.maximum(1 - damage, 1 - config['damage_cap'])
    strain_error = np.max(abs(np.log1p(history['ux_mm']) - effective_stress / 205000 - history['eppl']))
    assert strain_error < 1e-4 and force_error < max(1e-5, 1e-4 * history['fx_N'][peak])
    softening = (damage > .02) & (damage < .9)
    intercept_strain = None
    if np.count_nonzero(softening) >= 3:
        slope, intercept = np.polyfit(history['eppl'][softening], damage[softening], 1)
        assert slope > 0
        intercept_strain = float(-intercept / slope)
    results = dict(converged_states=len(history), peak_reaction_N=float(history['fx_N'][peak]),
                   travel_at_peak_mm=float(history['ux_mm'][peak]), last_travel_mm=float(history['ux_mm'][-1]),
                   last_equivalent_plastic_strain=float(history['eppl'][-1]), last_section_damage=float(damage[-1]),
                   max_log_strain_residual=float(strain_error), max_current_area_force_residual_N=float(force_error),
                   softening_fit_intercept_strain=intercept_strain, imposed_initiation_strain=config['eps0'])
    crossings = np.flatnonzero(damage > 1e-4)
    results['first_damage_above_1e_4'] = None
    if len(crossings):
        k = int(crossings[0])
        results['first_damage_above_1e_4'] = [dict(native_set=int(h['set']), travel_mm=float(h['ux_mm']),
                                                   reaction_N=float(h['fx_N']), equivalent_plastic_strain=float(h['eppl']))
                                             for h in history[max(0, k-1):k+1]]
    return results


def references(archive):
    sources = read(ROOT / 'validation/local_inputs.json')
    result = {}
    OUTPUT.mkdir(exist_ok=True)
    for name in REFERENCES:
        spec = sources['damage_' + name]
        folder = archive / spec['source_path']
        for file in ('run.dat', 'config.json'):
            verified(folder / file, spec['files'][file])
        paths = ('run.out', 'diagnostic.out', 'accepted_history.csv', 'CONVERGED_STATES_AUDIT.json')
        hashes = {name: digest(folder / name) for name in paths}
        rows = table(folder / 'accepted_history.csv')
        diagnostic_sets = check_states(rows, (folder / 'run.out').read_text(), (folder / 'diagnostic.out').read_text())
        stats = coupon_law(rows, read(folder / 'config.json'), (folder / 'run.dat').read_text())
        prior = read(folder / 'CONVERGED_STATES_AUDIT.json')
        assert diagnostic_sets == 1 and prior['rows'] == len(rows)
        for new, old in [('last_section_damage', 'last_damage'), ('peak_reaction_N', 'peak_force_N'),
                         ('travel_at_peak_mm', 'peak_displacement_mm'), ('last_travel_mm', 'last_displacement_mm'),
                         ('last_equivalent_plastic_strain', 'last_peeq'), ('softening_fit_intercept_strain', 'onset_from_fit'),
                         ('max_log_strain_residual', 'max_log_strain_residual')]:
            assert np.isclose(stats[new], prior[old], rtol=1e-8, atol=1e-10)
        local = OUTPUT / (name + '.csv')
        local.write_bytes((folder / 'accepted_history.csv').read_bytes().replace(b'\r\n', b'\n'))
        result[name] = dict(**stats, excluded_diagnostic_sets=diagnostic_sets, run_input_sha256=spec['files']['run.dat'],
                            archive_files=hashes, local_history_sha256=digest(local))
    write_json(OUTPUT/'october.json', dict(cases=result, post_input_sha256=digest(ROOT/'model/coupon_post.inp'),
               scope='Archived homogeneous nickel shell tests. All three stopped short of their commanded 1 mm extension. '
                     'The prescribed law softens without element deletion. Peak coupon force applies only to this section.'))


def fresh(folder, spec, config, hashes):
    for name in ('model.inp', 'local_job.json', 'solve.out', 'coupon_post.inp', 'coupon_post.out', 'accepted_history.csv', 'tear.rst'):
        verified(folder / name, hashes[name])
    reference = read(OUTPUT / 'october.json')
    assert hashes['coupon_post.inp'] == reference['post_input_sha256']
    assert hashes['model.inp'] == read(ROOT/'validation/local_inputs.json')[spec['source']]['files']['run.dat']
    history = table(folder / 'accepted_history.csv')
    post = (folder / 'coupon_post.out').read_text(errors='replace')
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b', post)
    excluded = check_states(history, (folder / 'solve.out').read_text(errors='replace'), post)
    rst = reader.read_binary(str(folder / 'tear.rst'))
    ls = rst._resultheader['ls_table']
    valid = np.flatnonzero(ls[:, 1] != 999999)
    assert excluded == rst.nsets-len(valid) and np.array_equal(history['set'], valid+1)
    assert np.array_equal(rst.mesh.enum,[1]) and np.array_equal(rst.mesh.nnum,[1,2,3,4])
    assert np.allclose(history['time'], rst.time_values[valid], rtol=0, atol=1e-8)
    for k,h in zip(valid, history, strict=True):
        ids,u = rst.nodal_solution(int(k))
        assert np.array_equal(ids,[1,2,3,4]) and np.allclose(u[[1,2],0],h['ux_mm'],atol=2e-7,rtol=0)
        assert np.isclose(u[2,1],h['uy_mm'],atol=2e-7,rtol=0)
        rf,nodes,dofs = rst.nodal_reaction_forces(int(k))
        x = dofs==1
        right = rf[x & np.isin(nodes,[2,3])].sum()
        assert np.isclose(right,h['fx_N'],rtol=2e-6,atol=1e-5) and abs(rf[x].sum())<1e-4
    data = coupon_law(history, config, (folder/'model.inp').read_text())
    name=spec['source'].removeprefix('damage_')
    prior=reference['cases'].get(name)
    if prior:
        local=OUTPUT/(name+'.csv')
        verified(local,prior['local_history_sha256'])
        previous=table(local)
        assert hashes['model.inp']==prior['run_input_sha256']
        hi=min(previous['ux_mm'][-1],history['ux_mm'][-1])
        lo=max(previous['ux_mm'][0],history['ux_mm'][0])
        grid=np.union1d(previous['ux_mm'],history['ux_mm'])
        grid=grid[(grid>=lo)&(grid<=hi)]
        if len(grid):
            differences={}
            for field in FIELDS[1:]:
                a,b=[np.interp(grid,h['ux_mm'],h[field]) for h in (previous,history)]
                differences[field]=float(np.max(abs(a-b)))
            data['october_shared_travel']=dict(first_mm=float(grid[0]),last_mm=float(grid[-1]),stations=len(grid),
                 max_absolute_difference=differences,october_history_sha256=prior['local_history_sha256'])
    data.update(states=len(history),last_time=float(history['time'][-1]),last_ux_mm=data['last_travel_mm'],
                max_damage=float(history['damage'].max()),excluded_diagnostic_sets=excluded,
                converged_history_sha256=hashes['accepted_history.csv'],native_post_sha256=hashes['coupon_post.out'])
    reached=abs(data['last_time']-config['end_time'])<1e-7
    return data,reached


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('october_archive',type=Path)
    references(parser.parse_args().october_archive)
