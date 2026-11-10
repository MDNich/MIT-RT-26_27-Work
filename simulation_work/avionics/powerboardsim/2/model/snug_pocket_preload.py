"""Check the measured lock force and when the fixed middle-pocket tangent exceeds its compressive reserve."""
import argparse

import numpy as np
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS

from audit_local import ROOT,read
from case_stress import source
from dpf_readback import export
from film_cell_timestep import refined_coordinates
from film_identity import digest,verified,write_json
from seeded_motion import FS,integrate,participation
from stage_snug_fit import AUDIT


def normal_controls(points):
    """Quadratic Bernstein controls for the oriented area vector of a six-node triangle."""
    bary=np.vstack((np.eye(3),[[.5,.5,0],[0,.5,.5],[.5,0,.5]]))
    derivatives=np.array([[-1.,-1.],[1.,0.],[0.,1.]])
    values=[]
    for p in bary:
        grad=np.vstack([(4*p[i]-1)*derivatives[i] for i in range(3)]+
                       [4*(p[a]*derivatives[b]+p[b]*derivatives[a]) for a,b in [(0,1),(1,2),(2,0)]])
        jac=points.T@grad
        values.append(np.cross(jac[:,0],jac[:,1]))
    controls=np.array(values)
    for j,(a,b) in enumerate([(0,1),(1,2),(2,0)],3):
        controls[j]=2*controls[j]-.5*(controls[a]+controls[b])
    return controls


def repeat(base,repeat,campaign):
    proofs=[read(AUDIT/(name+'_static_contacts.json')) for name in (base,repeat)]
    assert proofs[0]['case_mesh_sha256']==proofs[1]['case_mesh_sha256']
    assert proofs[0]['contact_history']==proofs[1]['contact_history']
    states=[read(AUDIT/(name+'_static_installed.json')) for name in (base,repeat)]
    for key in ('locked_bolt_forces_N','contact_history'):
        assert states[0][key]==states[1][key]
    folders=[export(name+'_static',campaign,list(range(1,9))) for name in (base,repeat)]
    errors=[]
    for k in range(1,9):
        stems=[f/f'set_{k:04d}' for f in folders]
        node,other=[np.fromfile(p.with_suffix('.ids'),'<i4') for p in stems]
        u,v=[np.fromfile(p.with_suffix('.u'),'<f8').reshape(-1,3) for p in stems]
        order,compare=np.argsort(node),np.argsort(other)
        assert np.array_equal(node[order],other[compare])
        errors.append(float(np.max(np.linalg.norm(u[order]-v[compare],axis=1))))
    assert max(errors)<1e-9
    return proofs,errors


def bracket(projected,level,sign):
    crossed=np.flatnonzero(sign*projected>level)
    assert len(crossed) and crossed[0]>0
    k=int(crossed[0])
    assert sign*projected[k-1]<=level<sign*projected[k]
    return dict(sample=k,time_bracket_s=[(k-1)/FS,k/FS],
                signed_increments_N=projected[[k-1,k]].tolist())


def patch_geometry(rst,static,elems,direction,vector):
    order=np.argsort(rst.mesh.enum);where=order[np.searchsorted(rst.mesh.enum[order],elems)]
    assert np.array_equal(rst.mesh.enum[where],elems)
    lower=[]
    for j in where:
        face=rst.mesh.elem[j][10:18]
        assert face[2]==face[3]==face[6]
        face=face[[0,1,2,4,5,7]]
        xyz=rst.mesh.nodes[np.searchsorted(rst.mesh.nnum,face)]
        controls=normal_controls(xyz)
        lower.append(float((controls@direction).min()/np.linalg.norm(controls,axis=1).max()))
    # Common open hemisphere, including the full curved faces, makes this scalar constraint necessary.
    assert min(lower)>.95
    order=np.argsort(static._eeqv);sel=order[np.searchsorted(static._eeqv[order],elems)]
    ptr,_,off=static._element_solution_header(static.nsets-1)
    records=static._cfile.read_element_data(ptr[sel],ELEMENT_INDEX_TABLE_KEYS.index('EMN'),off)
    face_forces=np.array([v[42:45] for v in records],dtype=float)
    assert np.all(face_forces@direction>0) and np.allclose(face_forces.sum(0),vector,atol=1e-7)
    return lower,face_forces


def excursions(branch,rst,log,projected_shapes,preload):
    results={}
    for axis in 'XYZ':
        gamma=participation(log.read_text(errors='replace'),axis)
        samples=np.arange(round(.1*FS)+1)
        t,q,_=integrate(rst.time_values,gamma,axis,samples)
        motion=read(ROOT/'validation/independent_motion'/(branch+'_motion_'+axis+'.json'))
        assert motion['modal_listing_sha256']==digest(log) and motion['case']==branch+'_motion_'+axis
        load=ROOT/'.runtime/motion_loads'/(axis+'.txt');verified(load,motion['input_sha256'])
        forcing=np.loadtxt(load,skiprows=1,max_rows=len(samples))
        assert np.allclose(t,forcing[:,0],rtol=0,atol=5.1e-13)
        exact,ctrl=refined_coordinates('linear_input_exact',forcing[:,1],samples,rst.time_values,gamma)
        records={}
        for method,coords in [('independent',q),('exact',exact)]:
            projection=coords@projected_shapes
            positive=bracket(projection,preload,1)
            negative=bracket(projection,preload,-1)
            records[method]=dict(positive=positive,negative=negative,
                                 sign_independent_latest_sample=max(positive['sample'],negative['sample']),
                                 peak_abs_projection_0p1s_N=float(abs(projection).max()))
        cutoffs={}
        for hz in (2000,3000,3500,4000):
            keep=rst.time_values<=hz
            projection=q[:,keep]@projected_shapes[keep]
            positive=bracket(projection,preload,1);negative=bracket(projection,preload,-1)
            cutoffs[hz]=dict(modes=int(keep.sum()),positive_sample=positive['sample'],
                             negative_sample=negative['sample'],peak_abs_projection_0p1s_N=float(abs(projection).max()))
        results[axis]=dict(integrations=records,verification=ctrl,modal_cutoff_Hz=cutoffs,
                          excitation_sha256=motion['input_sha256'])
    return results


def run(campaign,*,fine=False,material='nylon'):
    base='snug125_'+material
    branch=base+'_mesh15' if fine else base
    repeated=branch if fine else base+'_out2'
    details={}
    repeat_details={}
    if fine:
        measured=read(AUDIT/(branch+'_static_contacts.json'))
        original=measured
    else:
        (original,measured),delta=repeat(branch,repeated,campaign)
        repeat_details['all_station_displacement_repeat_max_m']=delta
    force=measured['resultant_force_check']
    vector=np.array(force[-1]['force_xyz_N'])
    preload=np.linalg.norm(vector)
    assert preload>0
    direction=vector/preload
    p,_,static=source(repeated+'_static',campaign)
    modal,folder,rst=source(branch+'_basis',campaign)
    parent=read(ROOT/'.runtime/receipts'/campaign/modal['case']/'status.json')['parent']
    assert p['rst_sha256']==measured['rst_sha256'] and original['case']==parent
    assert original['rst_sha256']==read(ROOT/'validation/global'/(parent+'.json'))['rst_sha256']
    active,=original['contact_history'][-1]['loaded_case_faces']
    assert active['STEP_face']==17
    elems=active['element_ids']
    lower,face_forces=patch_geometry(rst,static,elems,direction,vector)
    mass=read(ROOT/'validation/cell_force'/(base+'.json'))
    if fine:
        from cell_attachment_force import modal_transfer
        _,_,_,_,_,_,off_patch,opposition,pocket=modal_transfer(rst,mass['geometry'],elems)
        shapes=pocket['cell']
        details.update(active_contact_elements=elems,cell_pocket_shapes_N=shapes.tolist(),
                       pla_pocket_shapes_N=pocket['case'].tolist(),maximum_off_patch_ratio=off_patch,
                       maximum_bond_opposition_ratio=opposition,
                       maximum_two_side_relative_residual=pocket['max_two_side_residual_relative_to_interface_forces'])
    else:
        attachment=read(ROOT/'validation/cell_attachment'/(branch+'.json'))
        assert attachment['modal_rst_sha256']==modal['rst_sha256'] and attachment['middle_pocket']['active_contact_elements']==elems
        modes=ROOT/'.runtime/post'/campaign/(branch+'_basis')/'attachment_modes.npz'
        verified(modes,attachment['shape_force_sha256'])
        with np.load(modes) as saved:
            assert np.array_equal(saved['frequency_Hz'],rst.time_values)
            shapes=saved['middle_cell_pocket_force']
        details['modes_sha256']=attachment['shape_force_sha256']
    log=folder/'solve.out'
    ledger=read(ROOT/'.runtime/receipts'/campaign/modal['case']/'archived.json')
    verified(log,next(r['sha256'] for r in ledger['files'] if r['name']=='solve.out'))
    if fine:
        details['modal_listing_sha256']=digest(log)
    results=excursions(branch,rst,log,direction@shapes,preload)
    data=dict(variant=branch,campaign=campaign,native_force_rst_sha256=p['rst_sha256'],
              reference_static_rst_sha256=original['rst_sha256'],modal_rst_sha256=modal['rst_sha256'],
              **repeat_details,force_history=force,final_force_xyz_N=vector.tolist(),normal_axis=direction.tolist(),
              face_min_normal_cosine_bounds=lower,locked_face_forces_N=face_forces.tolist(),
              **details,axes=results,
              scope='The installed frictionless faces have co-oriented normals. Their total compressive '
                    'projection is nonnegative. The signed modal transfer is checked in both polarities, so '
                    'once both have exceeded the preload at least one would require a tensile total reaction '
                    'on the frozen patch. This is an upper bound on fixed-contact consistency, not an actual '
                    'opening time or the force following redistribution.')
    output=material+('_mesh15' if fine else '')+'_pocket_preload.json'
    write_json(AUDIT/output,data)
    print('lock N',preload,'minimum cosine',min(lower),'latest ms',
          {a:1000*r['integrations']['independent']['sign_independent_latest_sample']/FS for a,r in results.items()})


def native_excursions(campaign,material):
    from snug_shell_drive_sampling import native_startup

    base='snug125_'+material
    record=AUDIT/(material+'_pocket_preload.json')
    reference=read(record)
    proof,_,rst=source(base+'_basis',campaign)
    assert reference['modal_rst_sha256']==proof['rst_sha256'] and reference['campaign']==campaign
    shapes=ROOT/'.runtime/post'/campaign/(base+'_basis')/'attachment_modes.npz'
    verified(shapes,reference['modes_sha256'])
    axis=np.array(reference['normal_axis'])
    preload=np.array(reference['final_force_xyz_N'])
    with np.load(shapes) as modes:
        assert np.array_equal(modes['frequency_Hz'],rst.time_values)
        projection=axis@modes['middle_cell_pocket_force']
    assert np.allclose(preload,axis*np.linalg.norm(preload)) and min(reference['face_min_normal_cosine_bounds'])>.95
    samples=np.arange(round(.1*FS)+1)
    rows={}
    for direction in 'XYZ':
        motion=read(ROOT/'validation/independent_motion'/(base+'_motion_'+direction+'.json'))
        assert motion['basis_rst_sha256']==proof['rst_sha256'] and motion['input_sha256']==reference['axes'][direction]['excitation_sha256']
        q,source_ids=native_startup(motion,campaign,rst.time_values,samples)
        force=q@projection
        signs={name:bracket(force,np.linalg.norm(preload),sign) for name,sign in [('positive',1),('negative',-1)]}
        latest=max(row['sample'] for row in signs.values())
        diffs={name:{key:row[key]['sample']-signs[key]['sample'] for key in signs}
               for name,row in reference['axes'][direction]['integrations'].items()}
        rows[direction]=dict(**source_ids,**signs,sign_independent_latest_sample=latest,
                             upper_bound_ms=1000*latest/FS,other_minus_native_sample=diffs,
                             peak_absolute_force_increment_0p1s_N=float(abs(force).max()))
    write_json(AUDIT/(material+'_pocket_preload_native.json'),
               dict(variant=base,campaign=campaign,native_basis_sha256=proof['rst_sha256'],
                    pocket_force_audit_sha256=digest(record),force_shape_sha256=reference['modes_sha256'],
                    preload_N=float(np.linalg.norm(preload)),axes=rows,scope=reference['scope']))
    print(material,'native signed-coordinate time bounds [ms]',{k:v['upper_bound_ms'] for k,v in rows.items()})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',default='nov08_01')
    parser.add_argument('--fine',action='store_true')
    parser.add_argument('--material',choices=('nylon','aluminium'),default='nylon')
    parser.add_argument('--native',action='store_true')
    args=parser.parse_args()
    if args.native and args.fine:parser.error('Only the nominal mesh has native coordinate histories')
    if args.native:native_excursions(args.campaign,args.material)
    else:run(args.campaign,fine=args.fine,material=args.material)
