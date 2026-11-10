"""Seal the 1.250 mm native Balius fit to its own case IDs and the original bare Workbench inputs."""
import json

import numpy as np

from case_fit import ROOT
from check_case_mesh import check
from extend_board import board_feet, build
from film_identity import digest, verified, write_json
from mesh_case import make
from stage_local_jobs import seal

STEP = ROOT/'geometry/candidates/Balius-native-verification.STEP'
AUDIT = ROOT/'validation/snug125'
MESH = ROOT/'.runtime/mesh/snug125'
INPUTS = ROOT/'.runtime/inputs'
SPACING = 1.25
# Native STEP outer tab planes, in order (-X,-Y), (-X,+Y), (+X,-Y), (+X,+Y).
BEARINGS = (44, 38, 42, 40)
THICKNESS = 6.35
STEP_HASH = '43016e8435a85fc9ad33346ae11c0051102591c85a1fcee5ddd5658f75ca98ef'


def input_record(case):
    main=json.loads((AUDIT/'global_inputs.json').read_text())
    if case in main:return main[case]
    if case=='snug125_aluminium_mesh15_static':
        return json.loads((AUDIT/'aluminium_refinement_inputs.json').read_text())[case]
    if case=='snug125_aluminium_out2_static':
        return json.loads((AUDIT/'aluminium_force_repeat_input.json').read_text())
    if case=='snug125_aluminium_project3_static':
        return json.loads((AUDIT/'aluminium_projection_input.json').read_text())
    if case=='snug125_nylon_tol001_static':
        entry=json.loads((AUDIT/'force_tolerance_input.json').read_text())
        assert entry['case']==case
        return entry
    return json.loads((AUDIT/'contact_refinement_inputs.json').read_text())[case]


def stage():
    verified(STEP,STEP_HASH)
    identity=json.loads((ROOT/'validation/alternate_case_fit.json').read_text())
    gaps=identity['Balius_native']['shortest_gaps_mm']['1.25']
    assert all(v>0 for v in gaps.values()) and .0029 < gaps['19'] < .003
    bare=json.loads((ROOT/'validation/bare_inputs.json').read_text())
    case_specs={}
    for size in (2,3):
        mesh=MESH/f'case_{size}.npz'
        if not mesh.exists():
            make(size,step=STEP,mesh_dir=MESH,audit_dir=AUDIT)
        shape=json.loads((AUDIT/f'mesh_{size}.json').read_text())
        assert shape['step_sha256']==STEP_HASH
        volume=check(mesh,audit_dir=AUDIT)
        write_json(AUDIT/f'volume_{size}.json',volume)
        arrays=np.load(mesh)
        for tag,(sx,sz) in zip(BEARINGS,[(-1,-1),(-1,1),(1,-1),(1,1)],strict=True):
            points=arrays['points'][np.unique(arrays[str(tag)])]
            assert np.allclose(points[:,1],-3.65,atol=.0001,rtol=0)
            assert (points[:,0]*sx>20).all() and (points[:,2]*sz>45).all()
        for material in ('nylon','aluminium') if size==2 else ('nylon',):
            branch=f'snug125_{material}'+('_mesh3' if size==3 else '')
            for subject in ('static','refined','original') if size==2 else ('static',):
                reference=INPUTS/f'bare_{subject}'/'model.inp'
                verified(reference,bare[f'bare_{subject}']['staged_sha256'])
                data=reference.read_bytes();anchor=b'/gst,on,on'
                assert data.lower().count(anchor)==1
                pos=data.lower().index(anchor)
                addition,mounts=build(mesh,board_feet(data),material,SPACING,bearing_faces=BEARINGS,tab_thickness_mm=THICKNESS)
                assert all(abs(v['grip_mm']-(SPACING+THICKNESS))<.001 for v in mounts)
                # Pinball is the dimensional contact-search neighbourhood. Keep the registered nodes fixed.
                end='CM,CASECONTACT,ELEM\r\nALLSEL,ALL\r\nFINISH'
                assert addition.count(end)==1
                addition=addition.replace(end,'CM,CASECONTACT,ELEM\r\nALLSEL,ALL\r\nRMODIF,853,6,-0.0006\r\n/GOPR\r\nCNCHECK,DETAIL,853,853\r\nFINISH')
                case=branch+'_'+subject;folder=INPUTS/case;folder.mkdir(exist_ok=True)
                case_specs[case]=dict(input_sha256=seal(folder/'model.inp',data[:pos]+addition.encode()+data[pos:]),
                    step_sha256=STEP_HASH,mesh_sha256=digest(mesh),size_mm=size,tab_spacing_mm=SPACING,
                    tab_thickness_mm=THICKNESS,material=material,bearing_face_ids=BEARINGS,
                    bare_model_sha256=bare[f'bare_{subject}']['staged_sha256'],supports=mounts,parent='')
    for material in ('nylon','aluminium'):
        prefix=f'snug125_{material}'
        for subject in ('basis','modal20'):
            reference=INPUTS/f'bare_{subject}'/'model.inp'
            verified(reference,bare[f'bare_{subject}']['staged_sha256'])
            case=prefix+'_'+subject;folder=INPUTS/case;folder.mkdir(exist_ok=True)
            case_specs[case]=dict(input_sha256=seal(folder/'model.inp',reference.read_bytes()),
                step_sha256=STEP_HASH,tab_spacing_mm=SPACING,parent=prefix+'_static')
    write_json(AUDIT/'global_inputs.json',case_specs)


if __name__=='__main__':
    stage()
