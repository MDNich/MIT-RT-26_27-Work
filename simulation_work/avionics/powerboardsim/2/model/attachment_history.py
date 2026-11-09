"""Recover simultaneous three-component loads at each cell bond in the original nine-second records."""
import argparse
import numpy as np

from audit_local import ROOT, read
from audit_motion import native_series
from film_identity import digest, verified, write_json
from seeded_motion import FRAMES, FS, integrate, participation


BRANCHES = ('bare', 'stand3_nylon', 'stand3_aluminium')


def common_startup_end(campaign):
    crossings = []
    for branch in BRANCHES:
        motion = read(ROOT/'validation/motion'/f'{branch}_motion_X.json')
        assert motion['campaign']==campaign and motion['branch']==branch
        crossings.append(motion['nickel_trial_crossing']['time_bracket_s'][0])
    return int(min(crossings) * FS)


def peak(force, labels, other_end):
    lengths = np.linalg.norm(force, axis=2)
    station, bond = np.unravel_index(lengths.argmax(), lengths.shape)
    other = other_end[bond]
    return dict(**labels[bond], sample=int(station), time_s=station/FS, magnitude_N=float(lengths[station,bond]),
                components_N=force[station,bond].tolist(), other_end_components_N=force[station, other].tolist(),
                summed_cell_components_N=(force[station,bond]+force[station,other]).tolist())


def calculate(branch,campaign):
    base = ROOT/'validation'
    basis_path = base/'global'/f'{branch}_basis.json'
    basis = read(basis_path)
    source_path = base/'cell_attachment'/f'{branch}.json'
    source = read(source_path)
    assert source['branch']==branch and source['campaign']==basis['campaign']==campaign
    assert source['modal_rst_sha256']==basis['rst_sha256']
    cell_path=base/'cell_force'/f'{branch}.json'
    verified(cell_path,source['cell_inertia_record_sha256'])
    cells=read(cell_path)
    order=sorted(cells['geometry'],key=lambda k:cells['geometry'][k]['centroid_mm'][0])
    archive=ROOT/'.runtime/archive'/campaign
    modal_file=ROOT/'.runtime/post'/campaign/f'{branch}_basis'/'attachment_modes.npz'
    verified(modal_file,source['shape_force_sha256'])
    with np.load(modal_file) as shapes:
        frequencies=shapes['frequency_Hz']
        pairs=shapes['pairs'].tolist()
        modes=shapes['force']
    assert modes.shape==(6,3,len(frequencies)) and np.array_equal(frequencies,basis['frequencies_Hz'])
    log=archive/f'{branch}_basis'/'solve.out'
    verified(log,cells['modal_listing_sha256'])
    listing=log.read_text(errors='replace')
    results={}
    startup=common_startup_end(campaign)
    for axis in 'XYZ':
        name=f'{branch}_motion_{axis}'
        motion_path=base/'motion'/(name+'.json')
        motion=read(motion_path)
        assert motion['campaign']==campaign and motion['axis']==axis and motion['basis_rst_sha256']==basis['rst_sha256']
        verified(archive/name/'file.mcf',motion['mcf_sha256'])
        q=native_series(archive/name/'file.mcf',frequencies)
        transfer=modes.reshape(18,-1).T
        force=(q @ transfer).reshape(-1,6,3)
        labels=[None]*6
        other_end=[None]*6
        for field,position in zip(order,('left','centre','right'),strict=True):
            ends=source['spectrum'][axis]['cells'][field]['ends']
            assert ends[0]['face_y_mm']<ends[1]['face_y_mm']
            for index,end in enumerate(ends):
                j=pairs.index(end['pair'])
                other_end[j]=pairs.index(ends[1-index]['pair'])
                labels[j]=dict(cell=position, end=('low Y','high Y')[index], pair=end['pair'])
        clip=motion['attachment_forces_from_native_coordinates']
        assert clip['force_shape_sha256']==source['shape_force_sha256']
        targets=np.array([clip['peak_abs_XYZ_N_by_bond'][str(n)] for n in pairs])
        assert np.allclose(abs(force[FRAMES]).max(0),targets,atol=1e-10,rtol=1e-11)
        _,independent,_=integrate(frequencies,participation(listing,axis),axis,slice(None))
        independent_force=(independent@transfer).reshape(-1,6,3)
        del independent
        difference=force-independent_force
        relative=float(np.linalg.norm(difference)/np.linalg.norm(independent_force))
        assert relative<.0005
        cutoff=np.searchsorted(frequencies,3500,side='right')
        reduced=(q[:,:cutoff] @ transfer[:cutoff]).reshape(-1,6,3)
        full_peak=peak(force,labels,other_end)
        short_peak=peak(reduced,labels,other_end)
        result=dict(native_audit_sha256=digest(motion_path),mcf_sha256=motion['mcf_sha256'],samples=len(force),
                    maximum=full_peak, peak_at_3500_Hz=short_peak, modes_at_3500_Hz=int(cutoff),
                    relative_force_L2_vs_independent=relative, max_component_difference_N=float(np.abs(difference).max()))
        if axis=='X':
            result['startup_peak']=peak(force[:startup+1],labels,other_end)
            result['startup_end_s']=startup/FS
            if branch!='bare':
                gap_path=base/'nickel_vibration'/f'{branch}_X_clearance.json'
                gap=read(gap_path)
                assert gap['campaign']==campaign and gap['basis_rst']==basis['rst_sha256']
                assert gap['last_sample']>=startup and gap['certified_remaining_cell_clearance_lower_mm']>0
                result['independent_startup_clearance_sha256']=digest(gap_path)
        results[axis]=result
        print(branch,axis,full_peak['magnitude_N'],full_peak['cell'],full_peak['end'],flush=True)
        del force,q,reduced,difference,independent_force
    write_json(base/'cell_attachment'/f'{branch}_native_history.json',dict(branch=branch,campaign=campaign,
               shape_source_sha256=digest(source_path),basis_sha256=digest(basis_path),axes=results,
               scope='Peak Euclidean magnitude of the extra dynamic force on a single bonded cell end, using all '
                     'three components at the same native time station. The elastic model holds the preloaded contact '
                     'state fixed. The base-X startup window ends at the last common sample before any nickel stress '
                     'reaches the local pull model yield reference. Peak forces apply to these waveforms and ideal bonds.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args()
    for branch in BRANCHES:
        calculate(branch,args.campaign)
