"""Attach verified board-seat result extraction to the two checked local flush runs."""
import json
from audit_local import ROOT,read
from film_identity import verified,write_json
from local_board_seats import PILOTS,TRIAL
from stage_local_jobs import seal

def stage():
    accepted=read(ROOT/'validation/local_seat_preflight.json')
    plans=read(ROOT/'validation/local_seat_inputs.json')
    assert accepted['input_sha256']==plans['preflight_sha256']
    receipt={}
    for case,model_hash in plans['models'].items():
        previous=case.replace('_seatfaces1','_approach1')
        base=ROOT/'.runtime/inputs'/previous
        old=read(base/'local_job.json')
        dest=ROOT/'.runtime/inputs'/case;dest.mkdir(exist_ok=True)
        model=ROOT/'.runtime'/TRIAL/(case+'.inp');verified(model,model_hash)
        for n in ['moving.inp','local_post.inp']:verified(base/n,old['files'][n])
        moving=(base/'moving.inp').read_text()
        original='*DO,IP,861,864'
        assert moving.count(original)==1
        moving=moving.replace(original,'*DO,PBI,1,8\n    IP=860+PBI\n    *IF,PBI,GT,4,THEN\n      IP=875+PBI\n    *ENDIF')
        original='*ELSE\n      ESEL,S,TYPE,,864'
        assert moving.count(original)==1
        moving=moving.replace(original,'*ELSEIF,IP,GE,880,THEN\n      ESEL,S,TYPE,,858\n    '+original)
        files=dict(old['files'])
        files['model.inp']=seal(dest/'model.inp',model.read_bytes())
        files['moving.inp']=seal(dest/'moving.inp',moving.encode())
        files['local_post.inp']=seal(dest/'local_post.inp',(base/'local_post.inp').read_bytes())
        spec=dict(old,case=case,files=files,seat_pilots=list(PILOTS),seat_preflight_sha256=accepted['listing_sha256'])
        sha=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode())
        receipt[case]=dict(source=old['source'],spec_sha256=sha,input_sha256=files['model.inp'],
                           preflight_sha256=accepted['listing_sha256'])
    write_json(ROOT/'validation/local_seat_jobs.json',receipt)
if __name__=='__main__':stage()
