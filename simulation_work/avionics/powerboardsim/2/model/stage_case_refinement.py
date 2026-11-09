"""Seal a 2 mm printed-case mesh check for raised nylon under the same X-axis excitation."""
import numpy as np

from audit_local import ROOT,read
from check_case_mesh import check
from extend_board import board_feet,build
from film_identity import digest,verified,write_json
from stage_local_jobs import seal


def stage():
    rt=ROOT/'.runtime';branch='stand3_nylon_mesh2'
    seed=rt/'inputs/bare_static/model.inp'
    original=read(ROOT/'validation/bare_inputs.json')
    verified(seed,original['bare_static']['staged_sha256'])
    data=seed.read_bytes();key=b'/gst,on,on';assert data.lower().count(key)==1
    idx=data.lower().index(key)
    feet=board_feet(data);checked=read(ROOT/'validation/cased_inputs.json')['stand3_nylon_static']
    out={}
    for size in (3,2):
        mesh=rt/f'mesh/case_{size}.npz'
        quality=check(mesh);shape=read(ROOT/f'validation/mesh_{size}.json')
        assert shape['step_sha256']==read(ROOT/'validation/mesh_3.json')['step_sha256']
        assert quality['solids']==shape['tetrahedra'] and quality['minimum_det_probe_mm3']>0
        attachment,supports=build(mesh,feet,'nylon',3.)
        deck=data[:idx]+attachment.encode()+data[idx:]
        if size==3:
            reference=rt/'inputs/stand3_nylon_static/model.inp'
            verified(reference,checked['staged_sha256']);assert deck==reference.read_bytes()
            coarse=supports
        else:
            for a,b in zip(coarse,supports,strict=True):
                for prop in ('screw_axis_mm','case_center_mm','board_center_mm'):assert a[prop]==b[prop]
                assert a['bearing_nodes'][0]==b['bearing_nodes'][0]
                assert abs(a['grip_mm']-b['grip_mm'])<.01
            case=branch+'_static'
            folder=rt/'inputs'/case;folder.mkdir(exist_ok=True)
            out[case]=dict(input_sha256=seal(folder/'model.inp',deck),parent=None,
                mesh_file_sha256=digest(mesh),solid_count=quality['solids'],supports=supports,
                coarse_input_sha256=checked['staged_sha256'])
    case=branch+'_basis'
    basis=rt/'inputs/bare_basis/model.inp'
    verified(basis,original['bare_basis']['staged_sha256'])
    dest=rt/'inputs'/case;dest.mkdir(exist_ok=True)
    out[case]=dict(input_sha256=seal(dest/'model.inp',basis.read_bytes()),parent=branch+'_static')
    write_json(ROOT/'validation/case_refinement_inputs.json',dict(branch=branch,cases=out,
        reference_spectrum='stand3_nylon_psd_X_private1',
        scope='Same STEP, material axes, side clearance, seating, board mesh, support patches and mode extraction. The PLA tetrahedral mesh and sampling of its screw-bearing footprint change from 3 to 2 mm. Compare local layer-normal stress on both meshes and outside the rigid bearing.'))


if __name__=='__main__':stage()
