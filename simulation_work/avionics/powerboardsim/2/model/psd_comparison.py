"""Compare the complete set of seventeen original Mechanical random-response maxima."""
import csv
import json
import re
from pathlib import Path
import numpy as np
from film_identity import ROOT,digest,verified,write_json

def published_values(axis,scopes):
    values={}
    for scope,prefix in [('assembly',''),('pcb','PCB ')]:
        record=scopes[scope]
        for i,component in enumerate('XYZ'):
            values[f'{prefix}RMS displacement {component} - base {axis}']=(record['directional_rms_u_mm'][i]*.001,'m')
            values[f'{prefix}RMS absolute acceleration {component} - base {axis}']=(record['absolute_acceleration_rms_g'][i]*9.806,'m sec^-1 sec^-1')
        label='PCB' if prefix else 'all bodies'
        values['RMS equivalent stress - '+label]=(record['equivalent_stress_rms_Pa'],'Pa')
    for i,component in enumerate('XYZ'):
        values['RMS PCB normal strain '+component]=(scopes['pcb']['normal_elastic_strain_rms'][i],'m m^-1')
    return values

def check_october(case,axis,fields):
    folder=ROOT/'validation/october_psd_reference'
    source=json.loads((folder/'sources.json').read_text())[axis]
    path=folder/source['file'];verified(path,source['sha256'])
    values=published_values(axis,fields['scopes'])
    with path.open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
    assert len(rows)==len(values)==17 and set(values)=={r['name'] for r in rows}
    output=[]
    for row in rows:
        new,unit=values[row['name']]
        match=re.fullmatch(r'(\S+) \[(.+)\]',row['maximum'])
        assert match and match[2]==unit and row['scale']=='Sigma1'
        old=float(match[1])
        output.append(dict(metric=row['name'],unit=unit,reference=old,rerun=new,relative_error=abs(new/old-1)))
    worst=max(r['relative_error'] for r in output)
    assert worst<.001, (case,worst)
    return dict(reference_sha256=source['sha256'],metric_count=17,worst_relative_error=worst,comparisons=output)

def summary(variant,axis):
    from study_cases import native_case
    def load(key):
        p=ROOT/'validation/global'/(key+'.json')
        item=json.loads(p.read_text());assert item['case']==key
        return item,p
    bare,bp=load(native_case('bare','psd_'+axis))
    cased,cp=load(native_case(variant,'psd_'+axis))
    assert bare['campaign']==cased['campaign'] and bare['october_native_comparison']['metric_count']==17
    def vals(doc):return published_values(axis,doc['native_psd_fields']['scopes'])
    left,right=vals(bare),vals(cased)
    metrics={}
    for key,(a,u) in left.items():
        b,v=right[key];assert u==v
        metrics[key]=dict(unit=u,bare=a,cased=b,cased_over_bare=b/a)
    result=dict(variant=variant,base=axis,bare_sha256=bare['rst_sha256'],case_sha256=cased['rst_sha256'],
                bare_evidence_sha256=digest(bp),case_evidence_sha256=digest(cp),metrics=metrics,
                scope='Native statistical response about each installed state, under the same stored excitation and damping.')
    write_json(ROOT/'validation/psd_comparisons'/f'{variant}_{axis}.json',result)
    return result
