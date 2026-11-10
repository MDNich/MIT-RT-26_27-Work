"""Read bilinear nickel plastic strain on the top and bottom surfaces of each strip shell."""
import argparse
from pathlib import Path
import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from snug_local_checkpoint import CASE,CAMPAIGN
from stage_snug_fit import AUDIT


def fields(rst,k,mesh):
    elements=np.arange(1,len(mesh['elements'])+1)
    assert len(elements)==2304
    enum,rows,_=rst.element_solution_data(k,'EPL')
    idx=np.searchsorted(enum,elements);assert np.array_equal(enum[idx],elements)
    out=np.zeros((len(elements),2))
    available=np.array([i for i,j in enumerate(idx) if rows[j] is not None],dtype=int)
    if len(available):
        ii=idx[available]
        data=np.stack([rows[j] for j in ii]).reshape(len(ii),3,4,7)
        assert np.isfinite(data).all()
        # The closed top/bottom POST1 controls below identify this storage order.
        out[available]=data[:,:2,:,6].mean(axis=2,dtype=float)
    assert np.all(out>=0)
    if not np.any(out):
        ids,nonlinear,_=rst.element_solution_data(k,'ENL')
        jj=np.searchsorted(ids,elements);assert np.array_equal(ids[jj],elements)
        cumulative=np.stack([nonlinear[j] for j in jj]).reshape(len(elements),3,4,10)[:,:,:,3]
        assert np.isfinite(cumulative).all() and np.max(abs(cumulative))<1.e-12
    return out


def extract(folder,filename,mesh):
    rst=reader.read_binary(str(folder/filename))
    elem=rst.mesh.elem
    by_id={int(e[8]):e for e in elem if e[8]<=2304}
    assert len(by_id)==len(mesh['elements'])==2304
    for j,nodes in enumerate(mesh['elements'],1):assert np.array_equal(by_id[j][10:14],nodes)
    out=[];last=None
    for k in range(rst.nsets):
        last=fields(rst,k,mesh)
        i,j=np.unravel_index(np.argmax(last),last.shape)
        out.append(dict(native_set=k+1,peak=float(last[i,j]),element=int(i+1) if last[i,j]>0 else None,
                        face=('bottom','top')[j] if last[i,j]>0 else None))
    return out,last


def closed(case,mesh):
    folder=ROOT/'.runtime/archive'/CAMPAIGN/case
    ledger=read(ROOT/'.runtime/receipts'/CAMPAIGN/case/'archived.json')
    sha={r['name']:r['sha256'] for r in ledger['files']}
    proof=read(ROOT/'validation/local'/(case+'.json'))
    assert proof['case']==case and proof['source']=='lateral_friction_locked' and proof['full_requested_path']
    assert proof['rst_sha256']==sha['pull.rst']
    for name in ['pull.rst','history.csv','element_top.csv','element_bottom.csv']:verified(folder/name,sha[name])
    rows,last=extract(folder,'pull.rst',mesh);post=table(folder/'history.csv')
    assert np.array_equal(post['set'],[r['native_set'] for r in rows])
    a=np.max(abs(post['max_eppl']-[r['peak'] for r in rows]))
    error=0.
    for i,face in enumerate(('bottom','top')):
        f=table(folder/('element_'+face+'.csv'));assert np.array_equal(f['element'],np.arange(1,2305))
        error=max(error,float(abs(f['eppl']-last[:,i]).max()))
    assert a<1e-8 and error<1e-8
    return rows,dict(rst_sha256=sha['pull.rst'],saved_states=len(rows),all_states_max_abs_error=float(a),
                     two_faces_all_elements_endpoint_max_abs_error=error)


def compare(folder):
    source=ROOT/'.runtime/local_inputs/lateral_friction_locked/mesh.json'
    verified(source,read(ROOT/'validation/local_inputs.json')['lateral_friction_locked']['files']['mesh.json'])
    mesh=read(source);p=AUDIT/f'{CASE}_{folder.name}_checkpoint.json'
    r=read(p);assert r['case']==CASE and r['campaign']==CAMPAIGN
    verified(folder/'pull.rst',r['rst_sha256'])
    bare,ref=closed(r['bare_case'],mesh)
    _,alternate=closed('stand3_nylon_lateral_friction_locked_pin1',mesh)
    snug,_=extract(folder,'pull.rst',mesh)
    assert len(snug)==r['converged_sets'] and ref['rst_sha256']==r['bare_rst_sha256']
    equal=r['equal_bare_endpoint_load'];travel=r['last_common_travel']
    last_supported = travel['cased']['set']
    assert all(state['within_screens'] for state in r['states'][:last_supported])
    assert r['first_excluded_set'] in (None, last_supported + 1)
    assert max(equal['cased']['native_sets']) <= last_supported
    def subset(rows,ids):
        return [rows[i-1] for i in ids]
    out=dict(bare_terminal_force_N=equal['bare']['cell_force_N'],
             equal_force_bare=bare[equal['bare']['set']-1],
             equal_force_cased_bracket=subset(snug,equal['cased']['native_sets']),
             shared_travel_mm=travel['cased']['ux_mm'],
             shared_travel_bare_bracket=subset(bare,travel['bare']['native_sets']),
             shared_travel_cased=snug[travel['cased']['set']-1])
    write_json(AUDIT/f'{CASE}_{folder.name}_nickel_strain.json',dict(case=CASE,checkpoint_sha256=digest(p),
               bare_control=ref,previous_cased_control=alternate,states=snug,comparison=out,
               scope='Maximum shell element-mean equivalent plastic strain across the two nickel strips and '
                     'both exterior faces under the original bilinear law. The model retains intact attachments.'))
    print(out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);compare(p.parse_args().folder)
