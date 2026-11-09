"""Build new local fixtures with the native Balius mesh, its four bearing faces and resolved cell targets."""
import json
import numpy as np

from audit_local import read
from film_identity import digest, verified, write_json
from local_case_geometry import make,target_skin
from stage_local_jobs import seal
from stage_snug_fit import AUDIT,BEARINGS,INPUTS,MESH,ROOT,SPACING,STEP_HASH,THICKNESS


def stage():
    fixtures=('lateral_friction_locked','lateral_friction_locked_minus','lateral_friction_locked_fine','damage_cont_nominal')
    controls=read(ROOT/'validation/local_contact_retries.json')
    target=MESH/'fixture_targets_0005.npz'
    if not target.exists():
        target_skin(out=target,cell_resolution=(.0005,.016))
    mesh_path=MESH/'case_2.npz'
    mesh=np.load(mesh_path);skin=np.load(target)
    assert len(skin['points'])<200000
    # The 1 mm search stays unchanged. Finer target facets bound cylinder chord error below the central CAD gap.
    assert len(skin['4'])>2012
    specs={}
    for source in fixtures:
        pilot=read(ROOT/'.runtime/local_inputs'/source/'mesh.json')['pilot']
        for material in ('nylon','aluminium'):
            old=f'stand3_{material}_{source}_pin1';fresh=f'snug125_{material}_{source}_pin1'
            template=INPUTS/old;dest=INPUTS/fresh;dest.mkdir(exist_ok=True)
            verified(template/'local_job.json',controls[old]['spec_sha256'])
            data=read(template/'local_job.json');files={}
            for name,sha in data['files'].items():
                verified(template/name,sha)
                binary=(template/name).read_bytes()
                if name=='model.inp':
                    left=b'FINISH\n/PREP7\nALLSEL,ALL\nCSYS,0\nESYS,0\nET,850,SOLID187'
                    right=b'RMODIF,861,6,-1'
                    assert binary.count(left)==binary.count(right)==1
                    before,block=binary.split(left)
                    previous,after=block.split(right)
                    assert previous.rstrip().endswith(b'FINISH\n/PREP7')
                    attachment=make(mesh,skin,material,SPACING,pilot,bearing_faces=BEARINGS,tab_thickness_mm=THICKNESS,
                                    fixed_faces=[*range(5,46),50,51,52,53])
                    binary=before+attachment.encode()+right+after
                files[name]=seal(dest/name,binary)
            spec=dict(case=fresh,source=source,cased=True,coupon=False,job=data['job'],cores=data['cores'],
                      files=files,tab_standoff_mm=SPACING,step_sha256=STEP_HASH,absolute_search_mm=1.)
            specs[fresh]=dict(spec_sha256=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode()),
                        input_sha256=files['model.inp'],bare_reference='bare_'+source,template=old,
                        source=source,mesh_sha256=digest(mesh_path),target_sha256=digest(target),moving_target_faces=len(skin['4']))
    write_json(AUDIT/'local_inputs.json',specs)


if __name__=='__main__':stage()
