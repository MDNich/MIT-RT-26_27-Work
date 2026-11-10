"""Check the full refined local fixture under native shape checking before releasing its pull."""
import argparse
import re
import numpy as np
from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from stage_local_jobs import seal
from stage_snug_fit import AUDIT,INPUTS,MESH

def fixture(coarse):
    suffix='m3' if coarse else 'm15'
    mesh='3' if coarse else '1.5'
    label='3' if coarse else '15'
    case='snug125_nylon_lateral_friction_locked_pin1_'+suffix
    row=read(AUDIT/f'local_inputs_{suffix}.json')[case]
    return case,row,mesh,ROOT/'.runtime'/f'snug_local_mesh{label}_shape_v1'


def preflight(coarse=False):
    case,spec,_,trial=fixture(coarse)
    path=INPUTS/case/'model.inp'
    verified(path,spec['input_sha256'])
    model=path.read_text()
    assert model.count('SAVE,model,db')==1
    prefix=model.split('SAVE,model,db')[0]
    assert not re.search(r'(?im)^\s*solve\s*$',prefix)
    assert 'SHPP,OFF' not in prefix.upper() and 'SHPP,WARN' not in prefix.upper()
    cards=['ALLSEL,ALL','SHPP,ON','CHECK']
    for name,kind in [('caps',850),('beams',851),('seats',854),('targets',861),('faces',862)]:
        cards+=['ALLSEL,ALL',f'ESEL,S,TYPE,,{kind}',f'*GET,{name},ELEM,0,COUNT']
    cards+=['ALLSEL,ALL','*CFOPEN,inventory,csv','*VWRITE', "('tetrahedra,beams,seats,targets,contacts')",
            '*VWRITE,caps,beams,seats,targets,faces',"(F10.0,4(',',F10.0))",'*CFCLOS',
            '/COM,SNUG_REFINED_FIXTURE_SHAPE_CHECK','FINISH','/EXIT,NOSAVE']
    trial.mkdir(exist_ok=True)
    seal(trial/'pre.inp',(prefix+'\n'.join(cards)+'\n').encode())


def audit(coarse=False):
    from audit_local import table
    case,spec,size,trial=fixture(coarse)
    assert (trial/'pre.inp').is_file()
    preflight(coarse)  # Compare the sealed preflight deck with its current source bytes.
    assert int((trial/'exit.txt').read_text(encoding='utf-16'))==0
    log=(trial/'pre.out').read_text(errors='replace')
    assert 'SNUG_REFINED_FIXTURE_SHAPE_CHECK' in log and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    values=table(trial/'inventory.csv')[0]
    with np.load(MESH/'fixture_targets_0005.npz') as skin,np.load(MESH/f'case_{size}.npz') as mesh:
        target=sum(len(skin[str(k)]) for k in [4,15,19,1,6,9,10,11,20])+2
        # ESURF selects full exterior faces lying in each of the two registered contact components.
        all_faces=np.vstack([mesh[t] for t in mesh if t.isdigit()])
        count=0
        for tags in ([10,11,12,13],[*range(5,46),50,51,52,53]):
            nodes=np.unique(np.concatenate([mesh[str(tag)].ravel() for tag in tags]))
            count+=np.count_nonzero(np.isin(all_faces,nodes).all(axis=1))
        expected=dict(tetrahedra=len(mesh['tets']),beams=4,seats=4,targets=target,contacts=int(count))
    assert all(int(values[name])==n for name,n in expected.items()),(values,expected)
    if coarse:
        checksum=spec['input_sha256']
        coverage=read(AUDIT/'local_rigid_side_clearance_m3.json')
        assert coverage['cases'][case]['input_sha256']==checksum
        write_json(AUDIT/'local_mesh3_preflight.json',
                   dict(case=case,step_sha256=coverage['case_STEP_sha256'],sealed_pull_input_sha256=checksum,
                        preflight_input_sha256=digest(trial/'pre.inp'),native_listing_sha256=digest(trial/'pre.out'),
                        native_inventory_sha256=digest(trial/'inventory.csv'),native_counts=expected,
                        scope='Native preprocessing of the 3 mm directional control with shape checks enabled.'))
        return
    parts={}
    for name in read(AUDIT/'local_inputs.json'):
        rec=ROOT/'.runtime/receipts/nov08_01'/name
        if not (rec/'preparation_failure_files.json').is_file():continue
        proof=read(rec/'preparation_failure_files.json')
        assert proof['case']==name and read(rec/'status.json')['phase']=='failed'
        for file in ('pull.err','solve.out','inventory.txt'):verified(rec/file,proof[file])
        err=(rec/'pull.err').read_text(errors='replace')
        assert 'EN command cannot store element 1206035' in err
        parts[name]=dict(solve_sha256=proof['solve.out'],native_error_sha256=proof['pull.err'])
    assert len(parts)==4
    write_json(AUDIT/'local_mesh15_preflight.json',dict(case=case,step_sha256=read(AUDIT/'mesh_1.5.json')['step_sha256'],
              sealed_pull_input_sha256=spec['input_sha256'],preflight_input_sha256=digest(trial/'pre.inp'),
              native_listing_sha256=digest(trial/'pre.out'),native_inventory_sha256=digest(trial/'inventory.csv'),
              native_counts=expected,earlier_mesh_rejections=parts,
              scope='Native preprocessing with the full 10-node CONNECTIVITY in each SOLID187 record and default '
                    'shape checking enabled. All sources use the registered 1.250 mm geometry. '
                    'The rejected 2 mm local attempts produced no equilibrium.'))
    print(expected,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',nargs='?',choices=('audit',))
    p.add_argument('--audit',action='store_true')
    p.add_argument('--coarse',action='store_true')
    args=p.parse_args()
    if args.audit or args.action=='audit':audit(args.coarse)
    else:preflight(args.coarse)
