"""Bracket the first outer-cell skin intersections on the locked-contact base-Z startup trajectory."""
import argparse

import numpy as np

from audit_local import ROOT,read
from basis_comparison import field_files
from case_stress import source
from curved_cell_contact import contact_solids,sampled_clearance
from early_cell_clearance import outer_faces,subdivision_weights
from film_cell_contact import series,surface_fields
from film_cell_timestep import refined_coordinates
from film_identity import digest,verified,write_json
from seeded_motion import FS,participation
from snug_shell_drive_sampling import native_startup
from stage_snug_fit import AUDIT


def first_overlap(rest,modes,q):
    weights=subdivision_weights()
    states,count,_=series(rest,modes,q,weights,stop_at_first=True)
    first=len(states)-1 if states[-1]=='intersecting' else None
    assert first is not None or len(states)==len(q)
    unknown=[j for j,state in enumerate(states) if state=='unresolved']
    lo=min(unknown+[first if first is not None else len(q)])-1
    assert lo>=0
    audit=np.unique(np.r_[np.linspace(0,lo,min(9,lo+1),dtype=int),np.arange(max(0,lo-2),len(states))]).astype(int)
    reference,_,_=series(rest,modes,q[audit],weights)
    assert reference==[states[i] for i in audit]
    return dict(last_contiguous_clear_sample=int(lo),first_intersecting_sample=first,
                first_intersection_time_interval_ms=None if first is None else [1000*lo/FS,1000*first/FS],
                unresolved_samples=unknown,candidate_face_pairs=count,certified_by_block=0,
                individually_classified=len(states),individual_control_samples=audit.tolist())


def control():
    from early_cell_clearance import bezier
    tri=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]],[[1.3,.1,-1.],[1.3,.1,1.],[1.3,.6,0.]]])
    mid=(tri[:,[0,1,2]]+tri[:,[1,2,0]])*.5
    faces=bezier(np.concatenate([tri,mid],axis=1))
    rest=[p[None] for p in faces]
    modes=[np.zeros_like(r[None]) for r in rest]
    modes[1][:,:,:,0]=-1.
    trace=np.zeros((32,1));trace[11]=1.
    a=first_overlap(rest,modes,trace)
    assert a['first_intersecting_sample']==11 and a['last_contiguous_clear_sample']==10
    assert first_overlap(rest,modes,trace*0.)['first_intersecting_sample'] is None


def run(variant,campaign,method):
    control()
    replay_path=AUDIT/(variant.replace('_mesh15','')+'_replay_window.json')
    horizon=read(replay_path)['replay_last_sample']
    basis=variant+'_basis'
    proof,folder,rst=source(basis,campaign)
    samples=np.arange(horizon+1)
    motion=read(ROOT/'validation/independent_motion'/(variant+'_motion_Z.json'))
    assert motion['basis_rst_sha256']==proof['rst_sha256'] and motion['campaign']==campaign
    if method=='native':
        q,checks=native_startup(motion,campaign,rst.time_values,samples)
    else:
        load=ROOT/'.runtime/motion_loads/Z.txt'
        log=folder/'solve.out'
        verified(log,motion['modal_listing_sha256']);verified(load,motion['input_sha256'])
        forcing=np.loadtxt(load,skiprows=1,max_rows=len(samples))
        assert np.allclose(forcing[:,0],samples/FS,rtol=0,atol=5.1e-13)
        q,checks=refined_coordinates('linear_input_exact',forcing[:,1],samples,rst.time_values,
                                     participation(log.read_text(errors='replace'),'Z'))
    cover,cells=contact_solids(rst)
    solids=[cover]+[cells.extract_cells(cells.cell_data['ansys_material_type']==mat) for mat in (176,187)]
    shapes=[outer_faces(rst,[mat]) for mat in (850,176,187)]
    ids,xyz,phi,rest,modes=surface_fields(rst,shapes,solids,field_files(basis,campaign,proof['rst_sha256'],rst.nsets))
    rows={}
    for i,cell in enumerate(('left','right'),1):
        result=first_overlap([rest[0],rest[i]],[modes[0],modes[i]],q)
        print(variant,method,cell,result['first_intersection_time_interval_ms'],flush=True)
        first=result['first_intersecting_sample']
        if first is not None:
            # Independent VTK reconstructions check the geometry close to the first overlap. Their
            # triangulation can miss a shallow intersection, so retain each mesh's own classification.
            selected=[result['last_contiguous_clear_sample'],first,min(first+8,horizon)]
            witness=[]
            for k in selected:
                moved=xyz+(q[k]@phi.reshape(len(phi),-1)).reshape(xyz.shape)
                gaps=sampled_clearance([solids[0],solids[i]],ids,moved*.001,(2,3))
                witness.append(dict(sample=k,subdivisions=gaps))
            result['reconstructed_skin_checks']=witness
        rows[cell]=result
    write_json(AUDIT/(variant+'_outer_onset_Z_'+method+'.json'),dict(variant=variant,campaign=campaign,
        method=method,base_axis='Z',basis_rst_sha256=proof['rst_sha256'],input_sha256=motion['input_sha256'],
        window_sha256=digest(replay_path),samples=len(q),sample_rate_Hz=FS,quadratic_face_counts=list(map(len,shapes)),
        checks=checks,cells=rows,scope='Registered outer cells and full quadratic case exterior on the fixed-contact '
              'trajectory. Hull separation is checked for every earlier native sampling station. The first crossing is '
              'a geometric prediction. Actual contact reactions and rebound require nonlinear dynamics.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=('snug125_nylon','snug125_aluminium','snug125_nylon_mesh15','snug125_aluminium_mesh15'))
    parser.add_argument('--campaign',default='nov08_01')
    parser.add_argument('--method',choices=('exact','native'),default='native')
    args=parser.parse_args()
    run(args.variant,args.campaign,args.method)
