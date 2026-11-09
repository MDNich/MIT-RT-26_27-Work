"""Build paired native contact controls at the outer pocket reached in the signed base-Z history."""
import argparse
import re

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from contact_patch import coords_at, make_static, nodal_field, subset
from dpf_readback import export
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FRAMES, FS
from stage_local_jobs import seal
from stage_snug_fit import AUDIT, INPUTS


def fields(variant,campaign,radius):
    locator=read(AUDIT/'snug125_nylon_seeded_contact.json')
    selected=locator['axes']['Z']['samples'][0]
    # Fix the same physical region and excitation time for the two screw materials.
    site=next(r for r in selected['gaps'] if r['body']==4 and r['subdivision']==3)
    assert site['material']==176 and site['intersects'] and site['minimum_signed_target_vertex_gap_mm']<0
    center=.001*np.array(site['target_vertex_xyz_mm'])
    selected_frame=selected['frame_one_based']-1
    sample=int(FRAMES[selected_frame])
    assert selected['time_s']==sample/FS and radius in (9,15)
    evidence=read(AUDIT/(variant+'_seeded_contact.json'))
    basis,_,modes=source(variant+'_basis',campaign)
    static,folder,original=source(variant+'_static',campaign)
    assert evidence['native_basis_sha256']==basis['rst_sha256'] and evidence['pose_check']['parent_RST_sha256']==static['rst_sha256']
    target=evidence['axes']['Z']['samples'][0]
    assert target['frame_one_based']==selected_frame+1 and target['time_s']==sample/FS
    grid=modes.quadgrid
    mat=grid.cell_data['ansys_material_type'];solid=grid.cell_data['ansys_elem_type_num']==187
    axial_span=grid.extract_cells(solid & (mat==176)).bounds[2:4]
    # The right cell and the washers are excluded. All six washer surfaces are clear in the parent at this station.
    for row in target['gaps']:
        if row['body'] not in (4,19,15):assert not row['intersects']
    right=grid.extract_cells(solid & (mat==187))
    assert right.bounds[0]-center[0]>radius*.001
    bodies={m:subset(grid,m,center,radius*.001,axial_span) for m in (850,176,191)}
    groups={m:np.unique(np.concatenate([n for _,n in mesh[0]])) for m,mesh in bodies.items()}
    nodes=np.unique(np.concatenate(list(groups.values())))
    deck=folder/'model.inp'
    ledger=read(ROOT/'.runtime/receipts'/campaign/static['case']/'archived.json')
    verified(deck,next(r['sha256'] for r in ledger['files'] if r['name']=='model.inp'))
    text=deck.read_text()
    for material in (176,191):
        for prop,expected in [('EX',2e11),('NUXY',.3),('DENS',2200)]:
            match=re.search(rf'(?im)^MP,{prop},{material},([^,\s]+)',text)
            assert match and float(match[1])==expected
    xyz=coords_at(original,nodes)
    k=original.nsets
    stem=export(static['case'],campaign,[k])/f'set_{k:04d}'
    locked=nodal_field(stem,nodes)
    assert np.max(abs(xyz+locked-coords_at(modes,nodes)))<1e-9
    basis_fields=field_files(basis['case'],campaign,basis['rst_sha256'],modes.nsets)
    phi=displacement_basis(modes,nodes,basis_fields)
    clip=ROOT/'.runtime/post'/campaign/(variant+'_motion_Z')/'independent/coordinates.npz'
    verified(clip,evidence['axes']['Z']['clip_sha256'])
    with np.load(clip) as f:
        assert f['time_s'][selected_frame]==sample/FS and np.array_equal(f['frequencies_Hz'],modes.time_values)
        amplitude=np.einsum('i,ijk->jk',f['coordinates'][selected_frame],phi)
    driven=np.unique(np.concatenate([bodies[850][2],groups[176],groups[191]]))
    return dict(bodies=bodies,nodes=nodes,xyz=xyz,locked=locked,amplitude=amplitude,driven=driven,groups=groups,
                native_basis=basis['rst_sha256'],native_static=static['rst_sha256'],sample=sample,center=center,
                axial_span=axial_span)


def stage(variant,campaign):
    cases={}
    for radius in (9,15):
        state=fields(variant,campaign,radius)
        for contact in (False,True):
            label='contact' if contact else 'free'
            name=f'patch_{variant}_Z_span{radius}_{label}_v1'
            directory=INPUTS/name
            directory.mkdir(exist_ok=True)
            deck=make_static(state,contact)
            marker=b'neqit,60\n'
            assert deck.count(marker)==1
            deck=deck.replace(marker,marker+b'cnvtol,f,,1e-5,2,.01\n')
            branches={str(m):dict(tetrahedra=len(b[0]),exterior_faces=len(b[1]),cut_nodes=len(b[2]))
                      for m,b in state['bodies'].items()}
            cases[name]=dict(case=name,variant=variant,campaign=campaign,radius_mm=radius,contact=contact,
                input_sha256=seal(directory/'model.inp',deck),parent_modal_sha256=state['native_basis'],
                parent_static_sha256=state['native_static'],center_xyz_mm=(1000*state['center']).tolist(),
                cell_span_y_mm=(1000*np.array(state['axial_span'])).tolist(),forced_sample_s=state['sample']/FS,
                material_sets=branches,nodes=len(state['nodes']),driven_nodes=len(state['driven']),
                free_reference=f'patch_{variant}_Z_span{radius}_free_v1',units='m, N, Pa',
                parent_sample_audit_sha256=digest(AUDIT/(variant+'_seeded_contact.json')),
                loading='Quasistatic signed boundary path from lock to base-Z film frame 353 and back. The '
                        'PLA interior equilibrates while the cut boundary and both selected cell bodies follow '
                        'the parent solution. The local calculation omits global feedback and time-dependent inertia.')
    write_json(AUDIT/(variant+'_patch_inputs.json'),cases)
    print(variant,len(cases),'sealed local controls')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=('snug125_nylon','snug125_aluminium'))
    p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args()
    stage(args.variant,args.campaign)
