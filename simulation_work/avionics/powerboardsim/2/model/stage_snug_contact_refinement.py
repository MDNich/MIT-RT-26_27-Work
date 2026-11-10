"""Stage matched 2.0 and 1.5 mm preload contact-force readbacks following mesh-sensitive peak pressure."""
import re

import numpy as np

from audit_local import ROOT,read
from extend_board import NODE,board_feet,build
from film_identity import digest,verified,write_json
from mesh_case import make
from check_case_mesh import check
from snug_surface_check import run as audit_initial_skin
from stage_local_jobs import seal
from stage_snug_fit import AUDIT,INPUTS,MESH,STEP,SPACING,STEP_HASH,THICKNESS,BEARINGS


def stage():
    parent='snug125_nylon_static'
    reference=read(AUDIT/'global_inputs.json')[parent]
    verified(STEP,STEP_HASH)
    original=INPUTS/parent/'model.inp';verified(original,reference['input_sha256'])
    baseline=INPUTS/'bare_static/model.inp';verified(baseline,reference['bare_model_sha256'])
    data=baseline.read_bytes();anchor=b'/gst,on,on';assert data.lower().count(anchor)==1
    pos=data.lower().index(anchor);feet=board_feet(data)
    dest={}
    for name,size,node_start in [('out2',2,NODE),('mesh15',1.5,2100001)]:
        case=f'snug125_nylon_{name}_static';path=MESH/f'case_{size}.npz'
        if not path.exists():
            make(size,step=STEP,mesh_dir=MESH,audit_dir=AUDIT)
        checked=check(path,audit_dir=AUDIT)
        quality=read(AUDIT/f'mesh_{size}.json');assert quality['step_sha256']==STEP_HASH
        with np.load(path) as mesh:
            ids=node_start+np.arange(len(mesh['points']))
            assert not np.any((ids>=950001)&(ids<=950008)) and ids[0]>700000
            for tag,(sx,sz) in zip(BEARINGS,[(-1,-1),(-1,1),(1,-1),(1,1)],strict=True):
                pts=mesh['points'][np.unique(mesh[str(tag)])]
                assert np.allclose(pts[:,1],-3.65,rtol=0,atol=1e-4)
                assert (sx*pts[:,0]>20).all() and (sz*pts[:,2]>45).all()
        addition,mounts=build(path,feet,'nylon',SPACING,bearing_faces=BEARINGS,tab_thickness_mm=THICKNESS,case_node_start=node_start)
        for a,b in zip(mounts,reference['supports'],strict=True):
            for key in ('grip_mm','case_center_mm','board_center_mm','screw_axis_mm'):assert np.allclose(a[key],b[key],atol=1e-7,rtol=0)
        end='CM,CASECONTACT,ELEM\r\nALLSEL,ALL\r\nFINISH';assert addition.count(end)==1
        addition=addition.replace(end,end.replace('FINISH','RMODIF,853,6,-0.0006\r\n/GOPR\r\nCNCHECK,DETAIL,853,853\r\nFINISH'))
        model=data[:pos]+addition.encode()+data[pos:]
        if size==2:assert model==original.read_bytes()
        key=b'outres,cont,all,\r\n';assert model.count(key)==2
        extra=b'outres,misc,all,CASECONTACT\r\n';assert extra not in model
        augmented=model.replace(key,key+extra);assert augmented.replace(extra,b'')==model
        out=INPUTS/case;out.mkdir(exist_ok=True)
        closure='cell_surface_closure.json'
        if size==1.5:
            closure='cell_surface_closure_1p5.json'
            if not (AUDIT/closure).is_file():audit_initial_skin((size,),closure)
        proof=read(AUDIT/closure)
        assert proof['mesh_sha256'][str(size)]==digest(path)
        post=(ROOT/'model/contact_post.inp').read_bytes()
        cut=b'finish\n/exit,nosave';assert post.count(cut)==1
        force_post=post.replace(cut,(ROOT/'model/snug_force_readback.inp').read_bytes()+cut)
        dest[case]=dict(post_sha256=seal(out/'snug_force_post.inp',force_post),input_sha256=seal(out/'model.inp',augmented),step_sha256=STEP_HASH,mesh_sha256=digest(path),
                        size_mm=size,tab_spacing_mm=SPACING,tab_thickness_mm=THICKNESS,material='nylon',bearing_face_ids=BEARINGS,
                        bare_model_sha256=reference['bare_model_sha256'],supports=mounts,parent='',case_node_start=node_start,
                        surface_closure_file=closure,reference_case=parent,reference_input_sha256=reference['input_sha256'],
                        solid_volume_error=checked['relative_volume_error'],extra_output='MISC for CASECONTACT at every saved state')
    write_json(AUDIT/'contact_refinement_inputs.json',dest)


def stage_modal_control():
    """Repeat the nominal frequency extraction using the accepted fine preload restart."""
    parent = 'snug125_nylon_mesh15_static'
    case = 'snug125_nylon_mesh15_basis'
    fine = read(AUDIT/'contact_refinement_inputs.json')[parent]
    reference = read(AUDIT/'global_inputs.json')['snug125_nylon_basis']
    assert fine['step_sha256']==reference['step_sha256']==STEP_HASH and fine['size_mm']==1.5
    assert fine['tab_spacing_mm']==reference['tab_spacing_mm']==SPACING
    verified(INPUTS/parent/'model.inp',fine['input_sha256'])
    nominal = INPUTS/'snug125_nylon_basis/model.inp'
    verified(nominal,reference['input_sha256'])
    folder = INPUTS/case
    folder.mkdir(exist_ok=True)
    rec = dict(case=case,parent=parent,reference='snug125_nylon_basis',
               input_sha256=seal(folder/'model.inp',nominal.read_bytes()),
               parent_input_sha256=fine['input_sha256'],step_sha256=STEP_HASH,
               mesh_sha256=fine['mesh_sha256'],tab_spacing_mm=SPACING,size_mm=1.5)
    write_json(AUDIT/'modal_refinement_input.json',rec)


def stage_force_tolerance():
    """Keep both load steps and contact readback byte-identical except for the force criterion."""
    source = 'snug125_nylon_out2_static'
    case = 'snug125_nylon_tol001_static'
    nominal = read(AUDIT/'contact_refinement_inputs.json')[source]
    baseline = read(AUDIT/(source+'_residuals.json'))
    assert baseline['input_sha256']==nominal['input_sha256']
    source_dir = INPUTS/source
    deck_path = source_dir/'model.inp'
    post = source_dir/'snug_force_post.inp'
    verified(deck_path, nominal['input_sha256'])
    verified(post, nominal['post_sha256'])
    original = deck_path.read_bytes()
    solve = b'\r\nsolve\r\n'
    command = b'CNVTOL,F,1,0.01,2\r\n'
    assert original.count(solve)==2 and b'cnvtol,' not in original.lower()
    updated = original.replace(solve,b'\r\n'+command+solve[2:])
    assert updated.count(command)==2 and updated.replace(command,b'')==original
    folder = INPUTS/case
    folder.mkdir(exist_ok=True)
    entry = dict(nominal,case=case,reference_case=source,reference_input_sha256=nominal['input_sha256'],
                 input_sha256=seal(folder/'model.inp',updated),post_sha256=seal(folder/post.name,post.read_bytes()),
                 reference_residual_audit_sha256=digest(AUDIT/(source+'_residuals.json')),
                 absolute_force_criterion_N=0.01,force_reference_N=1.0,force_tolerance=0.01,
                 force_norm='L2',load_steps=[1,2],
                 command_reference='https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_cmd/Hlp_C_CNVTOL.html')
    write_json(AUDIT/'force_tolerance_input.json',entry)


def stage_aluminium_refinement():
    """Transfer the verified three screw-material card differences to the 1.5 mm model."""
    main=read(AUDIT/'global_inputs.json')
    base='snug125_aluminium_static'
    source='snug125_nylon_mesh15_static'
    fine=read(AUDIT/'contact_refinement_inputs.json')[source]
    decks=[]
    for name,spec in [('snug125_nylon_static',main['snug125_nylon_static']),(base,main[base]),(source,fine)]:
        path=INPUTS/name/'model.inp'
        verified(path,spec['input_sha256'])
        assert spec['step_sha256']==STEP_HASH and spec['tab_spacing_mm']==SPACING
        decks.append(path.read_bytes())
    nylon,aluminium,refined=decks
    changes=[]
    for prop in (b'EX',b'PRXY',b'DENS'):
        pattern=rb'^MP,'+prop+rb',851,[^\r\n]+\r?$'
        before,=re.findall(pattern,nylon,re.M)
        after,=re.findall(pattern,aluminium,re.M)
        assert before!=after and nylon.count(before)==refined.count(before)==1
        nylon=nylon.replace(before,after)
        refined=refined.replace(before,after)
        changes.append(dict(reference=before.decode().strip(),replacement=after.decode().strip()))
    assert nylon==aluminium
    case='snug125_aluminium_mesh15_static'
    directory=INPUTS/case
    directory.mkdir(exist_ok=True)
    post=INPUTS/source/'snug_force_post.inp'
    verified(post,fine['post_sha256'])
    spec=dict(fine,case=case,material='aluminium',reference_case=base,
              reference_input_sha256=main[base]['input_sha256'],nylon_fine_input_sha256=fine['input_sha256'],
              screw_card_changes=changes,input_sha256=seal(directory/'model.inp',refined),
              post_sha256=seal(directory/post.name,post.read_bytes()))
    basis='snug125_aluminium_mesh15_basis'
    ref='snug125_aluminium_basis'
    verified(INPUTS/ref/'model.inp',main[ref]['input_sha256'])
    directory=INPUTS/basis;directory.mkdir(exist_ok=True)
    modal=dict(read(AUDIT/'modal_refinement_input.json'),case=basis,parent=case,reference=ref,
               input_sha256=seal(directory/'model.inp',(INPUTS/ref/'model.inp').read_bytes()),
               parent_input_sha256=spec['input_sha256'])
    write_json(AUDIT/'aluminium_refinement_inputs.json',{case:spec,basis:modal})


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modal-only',action='store_true')
    parser.add_argument('--force-tolerance-only',action='store_true')
    parser.add_argument('--aluminium-only',action='store_true')
    args=parser.parse_args()
    if args.aluminium_only:stage_aluminium_refinement()
    elif args.force_tolerance_only:
        stage_force_tolerance()
    else:
        if not args.modal_only:stage()
        stage_modal_control()
