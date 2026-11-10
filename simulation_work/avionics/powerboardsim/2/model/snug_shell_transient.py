"""Drive the entire snug shell through bolt lock, rest and the original base-Z startup waveform."""
import argparse

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from contact_transient import data_file, load_array, tables
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FS
from snug_shell_drive_sampling import native_startup
from stage_local_jobs import seal
from stage_snug_fit import AUDIT, INPUTS

START = 2.125  # Hold the lock displacements with inertia off before enabling time integration.


def histories(variant, campaign, *, pilot, stride):
    registry = AUDIT / (variant + '_shell_inputs_v2.json')
    cases = read(registry)
    parent = cases['shell_' + variant + '_contact_v2']
    prior = read(AUDIT / (variant + '_shell_drive_native.json'))
    assert prior['registry_sha256'] == digest(registry) and prior['drive_field_sha256'] == parent['drive_field_sha256']
    basis, _, rst = source(parent['basis_case'], campaign)
    assert basis['rst_sha256'] == parent['basis_rst_sha256'] == prior['basis_rst_sha256']
    cache = ROOT / '.runtime/shell_fixture' / campaign / variant / 'parent_fields.npz'
    verified(cache, parent['drive_field_sha256'])
    with np.load(cache) as saved:
        nodes = saved['driven']
        ix = np.searchsorted(saved['nodes'], nodes)
        assert np.array_equal(saved['nodes'][ix], nodes)
        lock_times = np.array(parent['preload_times'])
        nlock = len(lock_times)
        assert np.array_equal(saved['t'][1:nlock+1], lock_times)
        preload = saved['u'][1:nlock+1, ix]
        assert np.array_equal(preload[-1], saved['u'][-1, ix]) and lock_times[-1] < START
    fields = field_files(parent['basis_case'], campaign, basis['rst_sha256'], rst.nsets)
    modes = displacement_basis(rst, nodes, fields)
    shape = np.concatenate([preload, modes]).transpose(1, 2, 0)
    motion = read(ROOT / 'validation/independent_motion' / (variant + '_motion_Z.json'))
    last = 64 if pilot else prior['samples'] - 1
    assert last % stride == 0 and stride in (2, 4)
    samples = np.arange(0, last + 1, stride)
    q, proof = native_startup(motion, campaign, rst.time_values, samples)
    assert proof['native_mcf_sha256'] == prior['native_mcf_sha256'] and np.max(abs(q[0])) < 1e-14
    t = np.r_[0., lock_times, START + samples / FS]
    coefs = np.zeros((len(t), shape.shape[-1]))
    coefs[1:nlock+1, :nlock] = np.eye(nlock)
    coefs[nlock+1:, nlock-1] = 1.
    coefs[nlock+1:, nlock:] = q
    signed = ROOT / '.runtime/motion_loads/Z.txt'
    verified(signed, motion['input_sha256'])
    load = np.loadtxt(signed, skiprows=1, max_rows=last+1)
    assert np.allclose(load[:, 0], np.arange(last+1) / FS, rtol=0, atol=5.1e-13) and load[0, 1] == 0.
    acc_time = np.r_[0., START + np.arange(last+1) / FS]
    acc = np.r_[0., load[:, 1]]
    return cases, prior, nodes, shape, t, coefs, acc_time, acc, rst.time_values, motion['input_sha256']


def stage(variant, campaign, *, pilot, stride):
    phase = 'pilot' if pilot else 'startup'
    cases, prior, nodes, shapes, t, coefs, at, acc, freq, load_sha = histories(
        variant, campaign, pilot=pilot, stride=stride)
    last = round((t[-1] - START) * FS)
    # Both refinements save the same physical stations. The pair tracker records every converged step.
    full = np.unique(np.r_[np.arange(16, last+1, 16), last])
    reactions = np.arange(4, last+1, 4)
    low, high = float(freq[0]), 2000.
    omega = 2*np.pi*np.array([low, high])
    beta = .04/omega.sum()
    alpha = beta*omega.prod()
    book = {}
    for kind in ('free', 'contact'):
        parent = cases[f'shell_{variant}_{kind}_v2']
        static = INPUTS / parent['case'] / 'model.inp'
        verified(static, parent['files']['model.inp'])
        marker = '*dim,pbt,array,'
        text = static.read_text()
        assert text.count(marker) == 1
        prefix = text.split(marker)[0]
        assert 'PBPORTS' in prefix and 'solve\n' not in prefix.lower()
        case = f'shellwave_{variant}_{kind}_{phase}_s{stride}'
        dest = INPUTS / case
        dest.mkdir(exist_ok=True)
        commands, files = tables(dest, nodes, t, coefs, shapes, acc, acceleration_time=at)
        for label, indices in [('pbfull', full), ('pbrf', reactions)]:
            files[label+'.dat'] = data_file(dest, label, START + indices / FS)
            commands.extend(load_array(label, (len(indices),), label))
        contact = kind == 'contact'
        lines = [prefix.rstrip(), *commands, 'finish','/solu','antype,trans','trnopt,full','timint,off',
                 'tintp,0','nlgeom,on','nropt,full','kbc,0','autots,on','neqit,60','cnvtol,f,,1e-5,2,.01',
                 'outres,all,none','outres,nsol,last','outres,rsol,last']
        if contact:
            lines += ['cncheck,detail,853,853','outres,cont,last,CASECONTACT','outres,misc,last,CASECONTACT']
            for name, label in [('pbfx','CFNX'),('pbfy','CFNY'),('pbfz','CFNZ'),('pbclosed','ELCN'),
                                ('pbpress','PRES'),('pbpen','PENE')]:
                lines.append(f'nlhist,pair,{name},cont,{label},853')
        lines += [f'd,PBPORTS,u{axis},%cut{axis}%' for axis in 'xyz']
        lines += ['/gopr']
        for when in parent['preload_times']:
            lines += [f'time,{when:.16g}','nsubst,2,200,1','solve']
        lines += [f'time,{START}','nsubst,2,2,2','solve','timint,on','acel,0,0,%baseacc%',
                  f'alphad,{alpha:.16g}', f'betad,{beta:.16g}', 'outres,all,none',
                  'outres,nsol,%pbfull%','outres,rsol,%pbrf%']
        if contact:
            lines += ['outres,cont,%pbfull%,CASECONTACT','outres,misc,%pbfull%,CASECONTACT']
        lines += [f'time,{t[-1]:.16g}',f'deltim,{stride/FS:.16g},{stride/FS/16:.16g},{stride/FS:.16g},off',
                  'solve','finish','/post1','set,last','/com,PB_SNUG_TRANSIENT_COMPLETE','finish','/exit,nosave']
        files['model.inp'] = seal(dest/'model.inp', ('\n'.join(lines)+'\n').encode())
        book[case] = dict(case=case, variant=variant, campaign=campaign, phase=phase, contact=contact, stride=stride,
            static_fixture=parent['case'], static_fixture_sha256=parent['files']['model.inp'], step_sha256=parent['step_sha256'],
            spacing_mm=parent['spacing_mm'], basis_rst_sha256=prior['basis_rst_sha256'], static_rst_sha256=parent['static_rst_sha256'],
            native_mcf_sha256=prior['native_mcf_sha256'], acceleration_sha256=load_sha, preload_times=parent['preload_times'],
            drive_field_sha256=prior['drive_field_sha256'], startup_time=START, sample_rate_Hz=FS,
            final_sample=last, drive_nodes=len(nodes), modal_shapes=len(freq), displacement_table_knots=len(t),
            acceleration_table_knots=len(at), full_output_samples=full.tolist(), reaction_output_stride=4,
            damping_reference_Hz=[low, high], rayleigh_alpha_per_s=alpha, rayleigh_beta_s=beta, files=files,
            scope='Intact shell with prescribed cell, hardware and bearing motions from the native locked-contact modes. '
                  'The shell can deform, detach and recontact. The parent board receives no feedback.')
    write_json(AUDIT / f'{variant}_shellwave_{phase}_s{stride}.json', book)
    print(variant, phase, stride, len(nodes), 'driven nodes;', last, 'original sample intervals', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('snug125_nylon','snug125_aluminium'))
    parser.add_argument('--campaign', default='nov08_01')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--stride', type=int, choices=(2,4), default=4)
    args = parser.parse_args()
    stage(args.variant, args.campaign, pilot=not args.full, stride=args.stride)
