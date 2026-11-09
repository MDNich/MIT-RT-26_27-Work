"""Stage matched 2.0 and 1.5 mm preload contact-force readbacks following mesh-sensitive peak pressure."""
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


if __name__=='__main__':stage()
