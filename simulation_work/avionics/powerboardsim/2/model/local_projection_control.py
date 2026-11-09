"""Stage the raised nylon pull with standard surface projection on its two PLA contact pairs."""
import json

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from stage_local_jobs import seal


def stage():
    parent = 'stand3_nylon_damage_cont_nominal_pin1_load8ref1'
    case = parent+'_project3'
    catalog = read(ROOT/'validation/common_pull_resolution.json')[parent]
    reference = ROOT/'validation/pull_pose_clearance/stand3_nylon_damage_cont_nominal_pin1.json'
    checked = read(reference)
    last = checked['precontact_poses'][-1]
    assert last['CAD_overlap_mm3']>0 and all(level['active_patch_intersects'] for level in last['meshed_geometry'])
    incoming = ROOT/'.runtime/inputs'/parent
    verified(incoming/'local_job.json',catalog['spec_sha256'])
    spec = read(incoming/'local_job.json')
    assert spec['case']==parent and spec['source']=='damage_cont_nominal'
    assert spec.pop('common_load_parent')==checked['case']
    dest = incoming.with_name(case)
    dest.mkdir(exist_ok=True)
    for name, sha in dict(spec['files']).items():
        verified(incoming/name,sha)
        data = (incoming/name).read_bytes()
        if name=='model.inp':
            assert b'KEYOPT,862,4,' not in data.upper()
            end = b'\r\n' if b'\r\n' in data else b'\n'
            old = b'ET,862,CONTA174'+end
            new = old+b'KEYOPT,862,4,3'+end
            assert data.count(old)==1
            data = data.replace(old,new)
            assert data.replace(new,old)==(incoming/name).read_bytes()
        spec['files'][name] = seal(dest/name,data)
    spec.update(case=case,detection_parent=parent)
    sha = seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode())
    write_json(ROOT/'validation/pull_detection_control.json',{case:dict(parent=parent,spec_sha256=sha,
               input_sha256=spec['files']['model.inp'],parent_spec_sha256=catalog['spec_sha256'],
               parent_input_sha256=catalog['input_sha256'],term_displacement_mm=spec['displacement_mm'],
               CAD_comparison_sha256=digest(reference),contact_element_type=862,real_pairs=[861,862],
               changed_option='KEYOPT(4) from default 0 to 3, standard surface projection',
               scope='Same nickel mesh, cell targets, PLA mesh, screws, prescribed travel, output and solver controls. '
                     'Compare first carried load with nominal detection and independently placed surfaces.')})
    return case


if __name__=='__main__':
    print(stage())
