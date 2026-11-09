"""Verify the reduced native history and write phase-resolved clip coordinates."""
import argparse
import json
import re
from pathlib import Path

import numpy as np

from seeded_motion import FS,FRAMES,integrate,participation
from stage_motion import ROOT,REFERENCE,sha


def full_history(path,frequencies,listing,axis):
    modes = len(frequencies)
    with path.open() as stream:
        header = [stream.readline().strip() for _ in range(9)]
    if header[4].split()!=['Norm:','MASS'] or int(header[5].split(':')[-1])!=modes:
        raise ValueError('MCF uses a different mode count or normalization')
    if not np.array_equal(np.fromstring(header[6].split(':')[1],sep=' '),np.arange(1,modes+1)):
        raise ValueError('Modal coordinate columns are out of order')
    mcf_freq=np.fromstring(header[7].split(':')[1],sep=' ')
    if not np.allclose(mcf_freq,frequencies,rtol=1e-6,atol=0):
        raise ValueError('MCF frequencies differ from the parent native basis')
    data=np.loadtxt(path,skiprows=9)
    if data.shape!=(9*FS+1,modes+1) or not np.isfinite(data).all():
        raise ValueError('Unexpected native time history')
    gamma=participation(listing,axis)
    t,expected,input_rms=integrate(frequencies,gamma,axis,slice(None))
    if np.max(np.abs(data[:,0]-t))>5.1e-7 or np.linalg.norm(data[0,1:])>1e-13:
        raise ValueError('Native sampling times or initial state differ')
    relative_l2=float(np.linalg.norm(data[:,1:]-expected)/np.linalg.norm(expected))
    if relative_l2>=.005:
        raise ValueError(f'Native and independent modal histories differ by {relative_l2:.4%}')
    return data[:,1:],dict(axis=axis,modes=modes,samples=len(t),duration_s=float(t[-1]),sampling_Hz=FS,
                           input_stationary_rms_g=input_rms,full_history_relative_L2=relative_l2)


def audit(case,campaign):
    folder=ROOT/'.runtime/archive'/campaign/case
    receipt=ROOT/'.runtime/receipts'/campaign/case
    state=json.loads((receipt/'status.json').read_text('utf-8-sig'))
    spec=json.loads((folder/'motion_job.json').read_text())
    ledger=json.loads((receipt/'archived.json').read_text('utf-8-sig'))
    branch=spec['branch']
    basis=json.loads((ROOT/f'validation/global/{branch}_basis.json').read_text())
    assert spec['campaign']==campaign==ledger['campaign'] and spec['case']==case==ledger['case']
    assert spec['basis_rst_sha256']==basis['rst_sha256']
    assert state['phase']=='solver_complete' and state['exit']==0
    assert all((folder/f['name']).stat().st_size==f['bytes'] for f in ledger['files'])
    from film_identity import verified
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    assert state['case']==spec['case']==case and state['motion_kind']==spec['kind']
    assert state['input_sha256'].lower()==spec['files']['model.inp']==hashes['model.inp']
    for name,expected in spec['files'].items():
        assert expected==hashes[name]
        verified(folder/name,expected)
    for name in ['solve.out','motion_job.json',('combine.out' if spec['kind']=='enforced' else 'file.mcf')]:
        verified(folder/name,hashes[name])
    listing=(folder/'solve.out').read_text(errors='replace')
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing) and 'RUN COMPLETED' in listing
    evidence=dict(case=case,branch=branch,campaign=campaign,basis_rst_sha256=basis['rst_sha256'])
    evidence['source_hashes']={name:hashes[name] for name in ['model.inp','motion_job.json','solve.out']}
    if spec['kind']=='enforced':
        assert re.search(r'NUMBER OF STATIC SHAPES\s*=\s*3\b',listing)
        combined=(folder/'combine.out').read_text(errors='replace')
        assert 'RUN COMPLETED' in combined and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',combined)
        limits=re.search(r'^\s*MODE_RANGE=\s*([\d.E+-]+)\s+TO\s+([\d.E+-]+)',combined,re.M|re.I)
        assert limits and np.allclose([float(limits[1]),float(limits[2])],np.array(basis['frequencies_Hz'])[[0,-1]],rtol=1e-5)
        evidence['source_hashes']['combine.out']=hashes['combine.out']
        evidence['enforced_directions']=3
        evidence['smp_parent_sha256']={r['name']:r['sha256'] for r in ledger['files'] if r['name'].lower() in ('file.db','file.mode','file.full','file.mlv','file.enf')}
        assert {'file.db','file.mode','file.full','file.mlv'}.issubset({s.lower() for s in evidence['smp_parent_sha256']})
    else:
        axis=spec['axis']
        assert sha(folder/'acc.txt')==spec['acc_sha256']
        parent=(ROOT/f'.runtime/archive/{campaign}/{branch}_basis/solve.out').read_text(errors='replace')
        data,metrics=full_history(folder/'file.mcf',basis['frequencies_Hz'],parent,axis)
        if (ROOT/'validation/cell_force'/(branch+'.json')).is_file():
            from check_cell_force_history import repeat as check_cell_force
            evidence['cell_acceleration_from_native_coordinates']=check_cell_force(
                branch,campaign,axis,data,basis['rst_sha256'],parent)
        if (ROOT/'validation/cell_attachment'/(branch+'.json')).is_file():
            from cell_attachment_force import check_native_clip
            evidence['attachment_forces_from_native_coordinates']=check_native_clip(branch,campaign,axis,data)
        nickel_path=ROOT/'validation/nickel_vibration'/f'{branch}_{axis}.json'
        if nickel_path.is_file():
            from nickel_vibration import early_crossing
            from film_identity import verified
            nickel=json.loads(nickel_path.read_text())
            assert nickel['modal_rst']==basis['rst_sha256'] and nickel['campaign']==campaign
            cache=ROOT/'.runtime/post'/campaign/(branch+'_basis')/'nickel'
            verified(cache/'sources.json',nickel['signed_tensor_cache_sha256'])
            saved=json.loads((cache/'sources.json').read_text())
            assert saved['static_rst']==nickel['static_rst'] and saved['basis_rst']==nickel['modal_rst']
            for name,key in [('modes','modal_stresses_sha256'),('static','static_stresses_sha256')]:
                verified(cache/(name+'.npy'),saved[key])
            count=round(nickel['independently_evaluated_window_s'][1]*FS)+1
            _,cross=early_crossing(np.load(cache/'modes.npy',mmap_mode='r'),np.load(cache/'static.npy'),
                                   data[:count],nickel['trial_reference_yield_MPa']*1e6)
            reference=nickel['first_sample_above_reference']
            assert (cross is None)==(reference is None)
            if cross is not None:
                delta=cross['sample']-reference['sample']
                if abs(delta)>1:
                    raise ValueError('Native nickel stress screen differs from the independent history by more than one sample')
                evidence['nickel_trial_crossing']=dict(time_bracket_s=cross['time_bracket_s'],
                    native_minus_independent_samples=delta,trial_MPa=cross['trial_MPa'],
                    scope='Stored signed native stress tensors and native modal coordinates, including locked preload.')
        spectrum=branch+'_psd_'+axis+'_private1'
        layer=ROOT/'validation/pla_stress'/f'{spectrum}.json'
        if layer.is_file():
            from film_identity import verified
            record=json.loads(layer.read_text())
            assert record['basis_sha256']==basis['rst_sha256'] and record['campaign']==campaign
            modal_trace=ROOT/'.runtime/post'/campaign/spectrum/'PLA_critical_history.npz'
            verified(modal_trace,record['independent_signed_waveform']['cache_sha256'])
            with np.load(modal_trace) as trace:
                sigma=data@trace['modal_Z_Pa']*1e-6+float(trace['mean_MPa'])
                estimated=trace['signed_stress_MPa']
            assert sigma.shape==estimated.shape and np.isfinite(sigma).all()
            rel=float(np.linalg.norm(sigma-estimated)/np.linalg.norm(estimated))
            assert rel<.005,rel
            evidence['native_seeded_PLA_layer_stress']=dict(
                corner_node=record['fields']['ZZ']['node'],element=record['fields']['ZZ']['element'],
                peak_tension_MPa=float(sigma.max()),peak_time_s=float(np.argmax(sigma)/FS),
                peak_compression_MPa=float(sigma.min()),stationary_dynamic_RMS_MPa=float(np.std(sigma[FS:-1])),
                relative_difference_from_independent_time_history=rel,
                scope='Native modal coordinates times signed stresses at the corner of highest PSD response. Includes local tightening stress. Linearized contact.')
        path=ROOT/'.runtime/post'/campaign/case/'coordinates.npz'
        path.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(path,time_s=FRAMES/FS,coordinates=data[FRAMES],frequencies_Hz=basis['frequencies_Hz'])
        independent=ROOT/'validation/independent_motion'/(case+'.json')
        if independent.is_file():
            from film_identity import verified
            check=json.loads(independent.read_text())
            assert check['campaign']==campaign and check['basis_rst_sha256']==basis['rst_sha256']
            clip=path.parent/'independent/coordinates.npz'
            verified(clip,check['clip_sha256'])
            with np.load(clip) as prior:
                assert np.array_equal(prior['time_s'],FRAMES/FS)
                error=float(np.linalg.norm(prior['coordinates']-data[FRAMES])/np.linalg.norm(data[FRAMES]))
                assert error<.005
            evidence['independent_clip_check']=dict(clip_sha256=check['clip_sha256'],relative_L2=error)
        evidence.update(metrics,clip_samples=len(FRAMES),clip_sha256=sha(path),input_sha256=spec['acc_sha256'],
                        mcf_sha256=next(r['sha256'] for r in ledger['files'] if r['name']=='file.mcf'))
    dest=ROOT/'validation/motion';dest.mkdir(exist_ok=True)
    (dest/(case+'.json')).write_text(json.dumps(evidence,indent=2)+'\n')
    print('Verified',case,flush=True)


def reference(archive):
    parent=archive/'powerboardsim_v1_files/dp0/SYS-4/MECH/solve.out'
    f=np.loadtxt(REFERENCE.parent/'native/modal_basis/frequencies.csv',delimiter=',',skiprows=1)[:,-1]
    out=[]
    for axis in 'XYZ':
        raw=archive/f'outputs/random_motion_20261005_2143/transient_{axis}/file.mcf'
        data,metric=full_history(raw,f,parent.read_text(errors='replace'),axis)
        recorded=np.loadtxt(REFERENCE/f'inputs/modal_coordinates_{axis}_clip.csv',delimiter=',',skiprows=1)
        assert np.array_equal(data[FRAMES],recorded[:,1:])
        out.append(metric)
    (ROOT/'validation/native_motion_reader.json').write_text(json.dumps({'scope':'Three full October native MCF histories compared with independent modal integration', 'axes':out},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    p=parser.add_subparsers(dest='action',required=True)
    ref=p.add_parser('reference');ref.add_argument('archive',type=Path)
    case=p.add_parser('case');case.add_argument('name');case.add_argument('campaign')
    a=parser.parse_args()
    if a.action=='reference':reference(a.archive)
    else:audit(a.name,a.campaign)
