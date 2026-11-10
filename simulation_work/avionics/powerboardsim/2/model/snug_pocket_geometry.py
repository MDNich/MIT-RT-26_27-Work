"""Check the intact shell and each cell at the first positive and negative preload-sized force excursions."""
import numpy as np

from audit_local import ROOT,read
from basis_comparison import field_files
from case_stress import source
from early_cell_clearance import bezier,outer_faces,subdivision_weights
from film_cell_contact import plane_control,series
from film_identity import digest,verified,write_json
from motion_surface import displacement_basis
from seeded_motion import FS,integrate,participation
from stage_snug_fit import AUDIT


def face_key(face):
    """Permutation-independent corner/edge identity for a six-node quadratic triangle."""
    return tuple(sorted((min(face[i],face[j]),max(face[i],face[j]),face[m])
                        for i,j,m in ((0,1,3),(1,2,4),(2,0,5))))


def run(campaign='nov08_01',*,fine=False):
    branch='snug125_nylon_mesh15' if fine else 'snug125_nylon'
    case=branch+'_basis'
    prefix='nylon_mesh15' if fine else 'nylon'
    reserve=AUDIT/(prefix+'_pocket_preload.json')
    evidence=read(reserve);basis,folder,rst=source(case,campaign)
    assert evidence['modal_rst_sha256']==basis['rst_sha256']
    installed=read(AUDIT/(branch+'_static_contacts.json'))
    faces=np.array(installed['contact_history'][-1]['loaded_case_faces'][0]['element_ids'])
    order=np.argsort(rst.mesh.enum);idx=order[np.searchsorted(rst.mesh.enum[order],faces)]
    assert np.array_equal(rst.mesh.enum[idx],faces)
    original_patch=np.stack([rst.mesh.elem[i][10:18][[0,1,2,4,5,7]] for i in idx])
    surfaces=[outer_faces(rst,[m]) for m in [850,176,191,187]]
    if fine:
        exterior={face_key(face):i for i,face in enumerate(surfaces[0])}
        subset=[exterior[face_key(face)] for face in original_patch]
        assert len(set(subset))==len(subset) and len(exterior)==len(surfaces[0])
    ids=np.unique(np.concatenate([s.ravel() for s in surfaces]))
    where=np.searchsorted(rst.mesh.nnum,ids);assert np.array_equal(rst.mesh.nnum[where],ids)
    xyz=rst.mesh.nodes[where]*1000
    phi=1000*displacement_basis(rst,ids,field_files(case,campaign,basis['rst_sha256'],rst.nsets))
    # A common translational frame keeps the broad-phase bounding boxes narrow.
    phi-=phi[:,np.searchsorted(ids,np.unique(surfaces[2])),:].mean(axis=1,keepdims=True)
    connectivity=[np.searchsorted(ids,s) for s in [*surfaces,original_patch]]
    rest=[bezier(xyz[f]) for f in connectivity]
    modes=[bezier(phi[:,f,:]) for f in connectivity]
    transform=subdivision_weights();plane_control(transform)
    log=folder/'solve.out'
    modal_log_sha=(evidence['modal_listing_sha256'] if fine else
                   read(ROOT/'validation/cell_force'/(branch+'.json'))['modal_listing_sha256'])
    verified(log,modal_log_sha)
    out={}
    for axis in 'XYZ':
        trial=evidence['axes'][axis]['integrations']['independent']
        samples=[0,trial['positive']['sample'],trial['negative']['sample']]
        if fine:
            peak=read(AUDIT/(branch+'_'+axis+'_PLA_independent.json'))
            assert peak['native_basis_sha256']==basis['rst_sha256'] and peak['coordinate_source_sha256']==modal_log_sha
            samples.append(peak['scopes']['all']['layer_tension_MPa']['sample'])
        samples=np.array(samples)
        t,q,_=integrate(rst.time_values,participation(log.read_text(errors='replace'),axis),axis,samples)
        states={}
        for left,right,name in [(0,1,'left'),(0,2,'middle'),(0,3,'right'),(4,2,'installed_faces_to_middle')]:
            values,n,depth=series([rest[left],rest[right]],[modes[left],modes[right]],q,transform)
            states[name]=dict(states=values,candidate_pairs=n,intersecting_refinement_depths=depth)
        if fine:
            whole=states['middle']['states']
            patch=states['installed_faces_to_middle']['states']
            checked=[]
            for broad,local in zip(whole,patch,strict=True):
                if local=='intersecting':
                    # One physical face on the shell is a sufficient positive witness.
                    assert broad!='separated'
                    checked.append('intersecting')
                else:
                    checked.append(broad)
            states['middle']['whole_surface_search']=whole
            states['middle']['states']=checked
            states['middle']['witness_exterior_triangle_indices']=subset
        assert [states[m]['states'][0] for m in ('left','middle','right')]==['separated','intersecting','separated']
        out[axis]=dict(samples=samples.tolist(),time_s=t.tolist(),geometry=states)
        print(axis,{m:s['states'] for m,s in states.items()},flush=True)
    write_json(AUDIT/(prefix+'_pocket_excursion_geometry.json'),dict(variant=branch,campaign=campaign,
        force_audit_sha256=digest(reserve),native_basis_sha256=basis['rst_sha256'],axes=out,
        order=('Bolt lock, first positive preload-sized force increment, first negative increment, peak through-layer tension.'
               if fine else 'Bolt lock, first positive preload-sized force increment, first negative increment.'),
        scope='At each selected instant every exterior quadratic PLA and cell face is tested. '
              'Separated classifications use disjoint Bernstein control hulls; intersections persist at '
              'two successive triangle refinements. The originally active PLA faces are also tested '
              'against the middle cell. The linear path cannot determine the adjusted nonlinear load distribution.'))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fine',action='store_true')
    args=parser.parse_args()
    run(fine=args.fine)
