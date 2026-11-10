"""Stage short forward pulls with moment-free tab bearings and compare the two attachment assumptions."""
import hashlib
import json
import re

from audit_local import ROOT,read
from compare_pull import series
from film_identity import digest,verified,write_json
from rocking_bearing import COPIES,PILOTS,joint_post,release_tab_rotations,control_deck
from snug_directional_result import paired,first_bracket
from stage_local_jobs import seal
from stage_snug_fit import AUDIT,INPUTS

REGISTRY=AUDIT/'local_bearing_inputs.json'
CONTROL=ROOT/'validation/spherical_bearing_control.json'
SHORT='TIME,2.25\nNSUBST,25,1000,5\nD,2481,UX,0.125'
FULL='TIME,3\nNSUBST,100,4000,20\nD,2481,UX,0.5'


def stage():
    baseline=read(AUDIT/'local_inputs_m15.json')
    control=read(CONTROL)
    assert hashlib.sha256(control_deck()).hexdigest()==control['input_sha256']
    for filename,key in [('control.out','listing_sha256'),('bearing_control.csv','table_sha256')]:
        verified(ROOT/'.runtime/spherical_bearing_control_v1'/filename,control[key])
    manifest={}
    for material in ('nylon','aluminium'):
        parent='snug125_'+material+'_lateral_friction_locked_pin1_m15'
        case=parent.replace('_pin1_m15','_rock125_m15')
        path=INPUTS/parent;meta=baseline[parent]
        verified(path/'local_job.json',meta['spec_sha256'])
        job=read(path/'local_job.json')
        assert job['case']==parent and job['cores']==4 and job['job']=='pull'
        for name,sha in job['files'].items():verified(path/name,sha)
        original=(path/'model.inp').read_text()
        modified,matrix=release_tab_rotations(original)
        assert modified.count(FULL)==1
        deck=modified.replace(FULL,SHORT)
        # Strip the joint definitions and restore just the four original CERIG sets. Verify
        # the remaining geometry, nickel, contacts, loads, convergence and postprocessing byte-for-byte.
        start=deck.index('! Only the four tab bearing rotations are released.')
        finish=deck.index('SAVE,model,db',start)
        recovered=deck[:start]+deck[finish:]
        tied_free=original
        for a,b in zip(PILOTS,COPIES,strict=True):
            pattern=rf'(?im)^CERIG,{a},(\d+),UXYZ\n'
            original_nodes=re.findall(pattern,original)
            freed_nodes=re.findall(rf'(?im)^CERIG,{b},(\d+),UXYZ\n',deck[start:finish])
            assert len(original_nodes)>3 and original_nodes==freed_nodes
            tied_free=re.sub(pattern,'',tied_free)
        assert recovered.replace(SHORT,FULL)==tied_free
        out=INPUTS/case;out.mkdir(exist_ok=True)
        files={'model.inp':seal(out/'model.inp',deck.encode()),
               'local_post.inp':seal(out/'local_post.inp',(path/'local_post.inp').read_bytes())}
        moving=(path/'moving.inp').read_text();end='finish\n/exit,nosave'
        assert moving.count(end)==1
        files['moving.inp']=seal(out/'moving.inp',moving.replace(end,joint_post()+end).encode())
        fresh=dict(job,case=case,files=files,rigid_reference=parent,bearing_pilots=list(COPIES),
                   bearing_control_sha256=control['input_sha256'],snug_bearing_control=True,
                   joints=matrix,end_time=2.25,displacement_mm=.125)
        fresh.pop('supersedes',None);fresh.pop('previous_input_sha256',None)
        spec_sha=seal(out/'local_job.json',(json.dumps(fresh,indent=2)+'\n').encode())
        manifest[case]=dict(case=case,parent=parent,bare_reference=meta['bare_reference'],spec_sha256=spec_sha,
                        input_sha256=files['model.inp'],parent_input_sha256=meta['input_sha256'],
                        joint_control_sha256=digest(CONTROL),coupled_nodes=[r['coupled_PLA_nodes'] for r in matrix.values()],
                        mesh_sha256=meta['mesh_sha256'],target_sha256=meta['target_sha256'],
                        travel_limit_mm=.125,loading_rate_mm_per_unit_time=.5,
                        scope='Rigid footprint retains translation coupling to the screw and spacer at the tab. '
                              'The four spherical joints release moments there. The matched 1.5 mm parent uses tied rotations.')
    write_json(REGISTRY,manifest)


def compare(case,verdict):
    spec=read(REGISTRY)[case];parent=spec['parent'];bare=spec['bare_reference']
    registry=read(AUDIT/'local_inputs_m15.json')[parent]
    assert registry['input_sha256']==spec['parent_input_sha256'] and registry['bare_reference']==bare
    proof=read(verdict);joints=ROOT/'validation/bearing_joints'/(case+'.json')
    ledger=read(ROOT/'.runtime/receipts'/proof['campaign']/case/'archived.json')
    sha={r['name']:r['sha256'] for r in ledger['files']}
    assert sha['model.inp']==spec['input_sha256'] and sha['pull.rst']==proof['rst_sha256']
    assert sha['local_job.json']==spec['spec_sha256']
    assert proof['joint_check_sha256']==digest(joints) and read(joints)['rst_sha256']==proof['rst_sha256']
    mate,=[p for d in ('local','partial_local') if (p:=ROOT/'validation'/d/(parent+'.json')).is_file()]
    parent_proof=read(mate)
    parent_ledger=read(ROOT/'.runtime/receipts'/parent_proof['campaign']/parent/'archived.json')
    tied_sha={r['name']:r['sha256'] for r in parent_ledger['files']}
    assert tied_sha['model.inp']==spec['parent_input_sha256'] and tied_sha['pull.rst']==parent_proof['rst_sha256']
    paths={};summary={}
    for label,name,v in [('tied',parent,mate),('rocking',case,verdict)]:
        result=paired(name,bare,v)
        _,rows=series(name,proof_path=v)
        summary[label]=result
        paths[label]=rows[:result['supported_pull_stations']]
        assert all(a['ux_mm']<b['ux_mm'] for a,b in zip(paths[label],paths[label][1:]))
    shared=None
    if all(paths.values()):
        x=min(rows[-1]['ux_mm'] for rows in paths.values())
        if x>1e-8:
            shared={key:first_bracket(rows,'ux_mm',x,1) for key,rows in paths.items()}
            assert all(shared.values())
    write_json(AUDIT/f'{case}_comparison.json',dict(case=case,parent=parent,registry_sha256=digest(REGISTRY),
               joint_check_sha256=digest(joints),input_sha256=spec['input_sha256'],models=summary,
               last_shared_travel=shared,scope='Matched forward pull: nominal rotation ties and released tab moments. '
               'Each branch stops at its first printed-material or contact-penetration screen.'))


if __name__=='__main__':
    stage()
