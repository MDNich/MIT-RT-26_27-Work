"""Compare audited prestressed bases; match shapes on identical physical nodes and separately locate case motion."""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from audit_local import ROOT,read
from film_identity import verified,write_json,digest
from dpf_readback import export
from modal_correspondence import reference_geometry
from native_rst import read_rst

def field_files(case,campaign,sha,n):
    # Keep batch names below filesystem length limits. The DPF backend can serve compressed fields
    # without relaunching IronPython for each mode. The final audited mode may already be cached.
    from dpf_readback import ROOT as droot
    path=droot/'.runtime/post'/campaign/case/'dpf_u'
    sets=list(range(1,n+1));result={}
    for i in sets:
        k=path/f'sets_{i}'/f'set_{i:04d}.json'
        if k.is_file():
            d=export(case,campaign,[i]);result[i]=d/f'set_{i:04d}'
    missing=[i for i in sets if i not in result]
    for j in range(0,len(missing),12):
        batch=missing[j:j+12];d=export(case,campaign,batch)
        for k in batch:result[k]=d/f'set_{k:04d}'
    assert len(result)==n
    return result

def compare(case,campaign):
    parents={};proof={};fields={};scopes={};result={}
    for key in ('bare_basis',case):
        proof[key]=p=read(ROOT/'validation/global'/f'{key}.json');assert p['case']==key and p['campaign']==campaign
        path=ROOT/'.runtime/archive'/campaign/key/'file.rst';verified(path,p['rst_sha256'])
        r=read_rst(path);parents[key]=r
        frequency=np.asarray(p['frequencies_Hz'])
        assert np.array_equal(r.time_values,frequency)
        g=r.grid;typ=g.cell_data['ansys_elem_type_num'];material=g.cell_data['ansys_material_type']
        solid=np.isin(typ,[185,186,187]);scopes[key]={}
        for name,mask in [('pcb',material==208),('cells',np.isin(material,[176,187,191])),('pla',material==850)]:
            if np.any(mask&solid):
                scopes[key][name]=np.unique(g.extract_cells(mask&solid).point_data['ansys_node_num'])
        if key!='bare_basis':
            fields[key]=field_files(key,campaign,p['rst_sha256'],len(frequency))
    ids,xyz,p0=reference_geometry(parents['bare_basis']);other,p,p1=reference_geometry(parents[case])
    assert np.array_equal(ids,other) and np.max(abs(xyz-p))<1e-9
    mat={};amps={}
    for key,r in parents.items():
        a=np.empty((r.nsets,len(ids)*3));amps[key]=[]
        for i in range(r.nsets):
            if key in fields:
                stem=fields[key][i+1]
                n=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
            else:n,u=r.nodal_displacement(i);u=u[:,:3]
            sort=np.argsort(n);n=n[sort];u=u[sort]
            def select(ns):
                loc=np.searchsorted(n,ns);assert np.array_equal(n[loc],ns);v=u[loc];assert np.isfinite(v).all();return v
            fornorm=select(ids).ravel();den=np.linalg.norm(fornorm);assert den>0;a[i]=fornorm/den
            q={name:float(np.linalg.norm(select(arr),axis=1).max()) for name,arr in scopes[key].items()}
            amps[key].append({name+'_to_PCB_peak_ratio':val/q['pcb'] for name,val in q.items() if name!='pcb'})
        mat[key]=a
    a,b=mat.values();signed=np.clip(a@b.T,-1,1);mac=signed**2
    ii,jj=linear_sum_assignment(-mac);assigned=dict(zip(ii,jj))
    f0=parents['bare_basis'].time_values;f1=parents[case].time_values
    rows=[]
    for i,fr in enumerate(f0):
        j=assigned.get(i);order=np.argsort(mac[i])[::-1]
        rows.append(dict(bare_rank=i+1,bare_Hz=fr,candidate_rank=None if j is None else int(j)+1,candidate_Hz=None if j is None else f1[j],
                   assigned_MAC=None if j is None else float(mac[i,j]),best_available_rank=int(order[0])+1,
                   best_MAC=float(mac[i,order[0]]),runner_up_MAC=float(mac[i,order[1]])))
    cs=[dict(rank=i+1,Hz=f1[i],**amps[case][i],best_bare_MAC=float(mac[:,i].max()),best_bare_rank=int(mac[:,i].argmax())+1) for i in range(len(f1))]
    rec=dict(campaign=campaign,bare='bare_basis',case=case,original_solid_nodes=len(ids),
          static_pose_checks=[p0,p1],native_source_sha256={key:p['rst_sha256'] for key,p in proof.items()},bare_modes=rows,cased_modes=cs,
          scope='Unweighted translational MAC on the unchanged original solid mesh. Assignment maximizes sum over both bases. The largest-component-body amplitude ratios use maximum vector lengths and are not effective mass or forced response.')
    write_json(ROOT/'validation/modal_pairs'/f'{case}.json',rec)
    print(case,len(rows),'bare vs',len(cs),'cased modes; first',cs[0],flush=True)
    return rec

if __name__=='__main__':compare(*sys.argv[1:])
