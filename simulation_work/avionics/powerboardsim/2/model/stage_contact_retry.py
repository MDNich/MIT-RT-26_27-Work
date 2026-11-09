"""Seal raised, local successor fixtures after checking the unloaded contact formulation."""
import json
from pathlib import Path

from contact_search_check import parse
from stage_local_jobs import ROOT,digest,seal


def stage():
    proof=parse('stand3_nylon_lateral_friction_locked')
    for pid in (861,862):
        stable=[r for r in proof['checks'] if r['real']==pid and r['request_mm']]
        assert len(stable)==3 and all(.14<r['min_gap_mm']<.23 and r['actual_pinball_mm']==r['request_mm'] and r['max_penetration_mm'] is None for r in stable)
        assert len({r['min_gap_mm'] for r in stable})==1
    base_manifest=json.loads((ROOT/'validation/local_jobs.json').read_text())
    eligible={}
    for base,entry in base_manifest.items():
        if not base.startswith('stand3_') or base.endswith('_pin1'):continue
        case=base+'_pin1'
        previous=ROOT/'.runtime/inputs'/base
        source=json.loads((previous/'local_job.json').read_text())
        dest=ROOT/'.runtime/inputs'/case
        dest.mkdir(exist_ok=True)
        files={}
        for filename,expected in source['files'].items():
            data=(previous/filename).read_bytes()
            assert digest(data)==expected
            if filename=='model.inp':
                tag=b'SAVE,model,db'
                assert data.count(tag)==1
                data=data.replace(tag,b'RMODIF,861,6,-1\nRMODIF,862,6,-1\n'+tag)
            if filename=='moving.inp':
                tag=b'finish\n/exit,nosave'
                assert data.count(tag)==1
                data=data.replace(tag,(ROOT/'model/local_pair_readback.inp').read_bytes()+tag)
            files[filename]=seal(dest/filename,data)
        spec={**source,'case':case,'files':files,'source_attempt':base,'absolute_search_mm':1.}
        spec_sha=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode())
        eligible[case]=dict(source=entry['source'],spec_sha256=spec_sha,input_sha256=files['model.inp'],
                            previous_input_sha256=entry['input_sha256'],search_preflight_sha256=proof['listing_sha256'])
    (ROOT/'validation/local_contact_retries.json').write_text(json.dumps(eligible,indent=2)+'\n')


if __name__=='__main__':stage()
