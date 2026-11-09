"""Match the two screw-material scenarios at the same mounting height."""
import argparse

import numpy as np
from scipy.optimize import linear_sum_assignment

from audit_local import ROOT,read
from basis_comparison import field_files
from film_identity import verified,write_json
from modal_correspondence import reference_geometry
from native_rst import read_rst
from study_cases import native_case


def compare(seat,campaign):
    data=[];poses=[];sources={};freq=[]
    for material in ('nylon','aluminium'):
        key=native_case(seat+'_'+material,'basis')
        proof=read(ROOT/'validation/global'/f'{key}.json')
        assert key==proof['case'] and campaign==proof['campaign']
        path=ROOT/'.runtime/archive'/campaign/key/'file.rst';verified(path,proof['rst_sha256'])
        r=read_rst(path);ids,undeformed,pose=reference_geometry(r,include_case=True)
        mesh=r.grid.cell_data;pla=r.grid.extract_cells((mesh['ansys_material_type']==850)&(mesh['ansys_elem_type_num']==187))
        local=np.unique(pla.point_data['ansys_node_num']);scope=np.searchsorted(ids,local)
        assert np.array_equal(ids[scope],local)
        if data:
            assert np.array_equal(refids,ids) and np.array_equal(refscope,scope) and np.allclose(refpts,undeformed,atol=1e-9,rtol=0)
        else:refids,refpts,refscope=ids,undeformed,scope
        sets=field_files(key,campaign,proof['rst_sha256'],r.nsets)
        u=np.empty((r.nsets,len(ids),3))
        for i in range(r.nsets):
            stem=sets[i+1];n=np.fromfile(stem.with_suffix('.ids'),'<i4')
            v=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
            order=np.argsort(n);j=order[np.searchsorted(n[order],ids)];assert np.array_equal(n[j],ids)
            u[i]=v[j]
        assert np.isfinite(u).all()
        data.append(u);poses.append(pose);sources[key]=proof['rst_sha256'];freq.append(r.time_values.copy())
    def mac(fields):
        a,b=[v.reshape(len(v),-1) for v in fields]
        den=np.outer(np.linalg.norm(a,axis=1),np.linalg.norm(b,axis=1))
        assert np.all(den>0)
        return np.clip(a@b.T/den,-1,1)**2
    full=mac(data);cap=mac([v[:,refscope,:] for v in data])
    ii,jj=linear_sum_assignment(-full);assigned=dict(zip(ii,jj));rows=[]
    for i in range(len(freq[0])):
        possible=np.argsort(full[i])[::-1];j=assigned.get(i)
        info=dict(nylon_mode=i+1,nylon_Hz=float(freq[0][i]),best_full_MAC=float(full[i,possible[0]]),
                  runner_up_full_MAC=float(full[i,possible[1]]),best_aluminium_mode=int(possible[0])+1)
        if j is not None:
            info.update(aluminium_mode=int(j)+1,aluminium_Hz=float(freq[1][j]),
                        frequency_change_percent=float(100*(freq[1][j]/freq[0][i]-1)),
                        full_solid_MAC=float(full[i,j]),case_only_MAC=float(cap[i,j]))
        rows.append(info)
    result=dict(seat=seat,campaign=campaign,native_sources=sources,pose_checks=poses,
        matched_solid_nodes=len(refids),matched_PLA_nodes=len(refscope),rows=rows,
        scope='One-to-one maximum total MAC assignment on identical, unweighted solid-node translations including the PLA. Also report a case-only correlation and alternative matches. Frequencies use the actual locked-state geometry for each material.')
    write_json(ROOT/'validation/screw_modal_comparison'/f'{seat}.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('seat',choices=('flush','stand3','snug125'));p.add_argument('campaign')
    a=p.parse_args();compare(a.seat,a.campaign)
