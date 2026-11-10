"""Recover the six bond loads and the middle-pocket resultant through each full nine-second base motion."""
import argparse

import numpy as np

from attachment_history import peak
from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from seeded_motion import FRAMES, FS
from snug_pla_vibration import full_coordinates

BRANCHES = ('bare','snug125_nylon','snug125_aluminium')


def summarize(variant, campaign, method, axis):
    basis_path = ROOT/'validation/global'/f'{variant}_basis.json'
    basis = read(basis_path)
    archive = ROOT/'.runtime/archive'/campaign/basis['case']
    verified(archive/'file.rst',basis['rst_sha256'])
    source_path = ROOT/'validation/cell_attachment'/f'{variant}.json'
    source = read(source_path)
    assert source['modal_rst_sha256']==basis['rst_sha256'] and source['campaign']==basis['campaign']==campaign
    cell_path = ROOT/'validation/cell_force'/f'{variant}.json'
    verified(cell_path,source['cell_inertia_record_sha256'])
    cell = read(cell_path)
    post = ROOT/'.runtime/post'/campaign/basis['case']
    verified(post/'attachment_modes.npz',source['shape_force_sha256'])
    verified(post/'cell_mass_mean.npz',cell['mean_shapes_sha256'])
    with np.load(post/'attachment_modes.npz') as data, np.load(post/'cell_mass_mean.npz') as mass:
        freq = data['frequency_Hz']
        assert np.array_equal(freq,basis['frequencies_Hz']) and np.array_equal(freq,mass['frequencies_Hz'])
        pairs = data['pairs'].tolist()
        modes = data['force']
        has_pocket = variant != 'bare'
        assert ('middle_cell_pocket_force' in data)==has_pocket
        pocket_modes = data['middle_cell_pocket_force'] if has_pocket else np.zeros((3,len(freq)))
        body_ids = list(map(str,mass['materials']))
        inertial_modes = mass['mean'] * (2*np.pi*freq)**2
        inertial_modes *= np.array([cell['geometry'][body]['mass_kg'] for body in body_ids])[:,None,None]
    assert modes.shape==(6,3,len(freq))
    q, coordinate_sha, load_sha = full_coordinates(variant,campaign,method,axis,basis,archive,freq)
    assert len(q)==9*FS+1
    full = (q @ modes.reshape(18,-1).T).reshape(-1,6,3)
    pocket = q @ pocket_modes.T
    spectrum = source['spectrum'][axis]['cells']
    order = sorted(body_ids,key=lambda body:cell['geometry'][body]['centroid_mm'][0])
    labels, others = [None]*6, [None]*6
    checks = {}
    middle_peak = None
    for label,body in zip(('left','centre','right'),order,strict=True):
        low,high = spectrum[body]['ends']
        assert low['face_y_mm'] < high['face_y_mm']
        left,right = [pairs.index(end['pair']) for end in (low,high)]
        for j,other,end in ((left,right,'low Y'),(right,left,'high Y')):
            labels[j] = dict(cell=label,end=end,pair=pairs[j])
            others[j] = other
        summed = full[:,left]+full[:,right]
        if label=='centre':
            summed += pocket
            # Use a single native time index for all three simultaneous interface vectors.
            magnitude = np.linalg.norm(full[:,[left,right]],axis=2)
            station,j = np.unravel_index(magnitude.argmax(),magnitude.shape)
            bond = (left,right)[j]
            middle_peak = dict(**labels[bond],sample=int(station),time_s=station/FS,
                               bond_N=float(magnitude[station,j]),governing_bond_xyz_N=full[station,bond].tolist(),
                               opposite_bond_xyz_N=full[station,others[bond]].tolist(),
                               pocket_xyz_N=pocket[station].tolist(),all_interfaces_xyz_N=summed[station].tolist())
        reference = q @ inertial_modes[body_ids.index(body)].T
        residual = np.linalg.norm(summed-reference)/np.linalg.norm(reference)
        assert residual<.0005
        checks[body] = float(residual)
    largest = peak(full,labels,others)
    mask = freq <= 3500
    assert np.any(mask) and np.any(~mask)
    reduced = (q[:,mask] @ modes[:,:,mask].reshape(18,-1).T).reshape(-1,6,3)
    cutoff = peak(reduced,labels,others)
    p = np.linalg.norm(pocket,axis=1)
    pk = int(p.argmax())
    evidence = ROOT/'validation'/('motion' if method=='native' else 'independent_motion')/f'{variant}_motion_{axis}.json'
    if method=='native':
        clip = read(evidence)['attachment_forces_from_native_coordinates']
        expected = [clip['peak_abs_XYZ_N_by_bond'][str(pair)] for pair in pairs]
        assert np.allclose(abs(full[FRAMES]).max(0),expected,rtol=1e-10,atol=1e-9)
        if variant=='bare':
            control = read(ROOT/'validation/cell_attachment/bare_native_history.json')['axes'][axis]['maximum']
            assert control['pair']==largest['pair'] and control['sample']==largest['sample']
            assert abs(control['magnitude_N']-largest['magnitude_N'])<1e-7
    if method=='independent':
        for ends in spectrum.values():
            for end in ends['ends']:
                clip = abs(full[FRAMES,pairs.index(end['pair']),:]).max(0)
                assert np.allclose(clip,end['seeded_clip_peak_abs_XYZ_N'],atol=1e-9)
    return dict(variant=variant,axis=axis,method=method,campaign=campaign,samples=len(q),modes=len(freq),
                basis_rst_sha256=basis['rst_sha256'],attachment_audit_sha256=digest(source_path),
                motion_audit_sha256=digest(evidence),coordinate_source_sha256=coordinate_sha,load_sha256=load_sha,
                largest_bond=largest,middle_cell_at_its_largest_bond=middle_peak,
                pocket_maximum=dict(sample=pk,time_s=pk/FS,magnitude_N=float(p[pk]),components_N=pocket[pk].tolist()),
                largest_bond_3500Hz=cutoff,modes_3500Hz=int(mask.sum()),relative_interface_vs_modal_inertia_L2=checks,
                scope='Signed dynamic load increment at each intact cell-to-nickel bond. Each maximum combines the '
                      'three components at one time. The mounted models hold the installed contact tangent fixed '
                      'through the record. The pocket and both middle bonds together recover the modal cell resultant.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=(*BRANCHES,'snug125_nylon_mesh15','snug125_aluminium_mesh15'))
    parser.add_argument('--axes',default='XYZ',choices=('X','Y','Z','XYZ'))
    parser.add_argument('--method',choices=('independent','exact','native'),default='independent')
    parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args()
    for axis in args.axes:
        row=summarize(args.variant,args.campaign,args.method,axis)
        write_json(ROOT/'validation/snug125'/f'{args.variant}_{axis}_bond_{args.method}.json',row)
        print(args.variant,axis,args.method,row['largest_bond']['magnitude_N'],flush=True)
