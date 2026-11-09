"""Match modal shapes on the unchanged structural mesh, with separate rank and sign checks."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from native_rst import read_rst
from scipy.optimize import linear_sum_assignment


def checksum(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def native_points(result,include_case=False):
    grid=result.grid
    typ=grid.cell_data['ansys_elem_type_num']
    material=grid.cell_data['ansys_material_type']
    common=np.isin(typ,[185,186,187]) & (material<=850 if include_case else material<850)
    sub=grid.extract_cells(common)
    ids=sub.point_data['ansys_node_num']
    ix=np.argsort(ids)
    assert np.all(np.diff(ids[ix])>0)
    return ids[ix],sub.points[ix]


def reference_geometry(result,include_case=False):
    """Undo only the verified static restart displacement on prestressed native modes."""
    ids,xyz=native_points(result,include_case);path=Path(result.filename).resolve()
    if not path.parent.name.endswith(('_basis','_modal20')) or path.parent.parent.parent.name!='archive':
        return ids,xyz,None
    from audit_local import ROOT,read
    from film_identity import verified
    key=path.parent.name;camp=path.parent.parent.name
    static=read(ROOT/'.runtime/receipts'/camp/key/'status.json')['parent']
    assert static.endswith('_static')
    proof=read(ROOT/'validation/global'/f'{static}.json')
    file=path.parent.parent/static/'file.rst';verified(file,proof['rst_sha256'])
    base=read_rst(file);b,ref=native_points(base,include_case);assert np.array_equal(b,ids)
    n,u=base.nodal_displacement(base.nsets-1);i=np.searchsorted(n,ids)
    assert np.array_equal(n[i],ids)
    err=float(np.max(abs((xyz-ref)-u[i,:3])))
    assert err<1.e-9, (key,static,err)
    return ids,ref,dict(parent=static,parent_RST_sha256=proof['rst_sha256'],peak_coordinate_plus_static_displacement_error_m=err)


def exported_modes(result):
    if not any(result.sparse_window(k) for k in range(result.nsets)):
        return None
    from basis_comparison import field_files
    from audit_local import ROOT,read
    from film_identity import verified
    path=Path(result.filename).resolve()
    case,campaign=path.parent.name,path.parent.parent.name
    assert path==ROOT/'.runtime/archive'/campaign/case/'file.rst'
    proof=read(ROOT/'validation/global'/(case+'.json'))
    assert proof['case']==case and proof['campaign']==campaign
    verified(path,proof['rst_sha256'])
    return field_files(case,campaign,proof['rst_sha256'],result.nsets)


def modes(result, ids):
    f=result.time_values
    if not len(f) or np.any(f<=0) or np.any(np.diff(f)<=0):raise ValueError('Expected a pure positive-frequency modal basis')
    out=np.empty((len(f),len(ids)*3))
    exports=exported_modes(result)
    for k in range(len(f)):
        if exports is None:
            numbers,u=result.nodal_displacement(k)
        else:
            stem=exports[k+1]
            numbers=np.fromfile(stem.with_suffix('.ids'),'<i4')
            u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        order=np.argsort(numbers)
        pos=np.searchsorted(numbers[order],ids)
        if pos.max()>=len(numbers) or not np.array_equal(numbers[order[pos]],ids):
            raise ValueError('Missing structural nodes from native eigenvector')
        out[k]=u[order[pos],:3].ravel()
    if not np.isfinite(out).all():raise ValueError('Invalid displacement at a physical node')
    norms=np.linalg.norm(out,axis=1)
    if norms.min()<=0:raise ValueError('Cannot identify an eigenvector without motion on the original assembly')
    out/=norms[:,None]
    return out


def compare(reference,candidate):
    a,b=[read_rst(str(p)) for p in (reference,candidate)]
    ids,xyz,pa=reference_geometry(a)
    other,loc,pb=reference_geometry(b)
    if not np.array_equal(ids,other) or np.max(np.abs(xyz-loc))>1.e-9:
        raise ValueError('Reference and candidate must have the same original solid mesh in metres')
    left=modes(a,ids);right=modes(b,ids)
    signed=np.clip(left@right.T,-1.,1.);mac=signed**2
    rows,cols=linear_sum_assignment(-mac)
    assigned=dict(zip(rows,cols))
    records=[]
    for i in range(len(mac)):
        order=np.argsort(mac[i])[::-1]
        j=assigned.get(i)
        records.append(dict(reference_rank=i+1,reference_Hz=float(a.time_values[i]),
                            best_rank=int(order[0])+1,best_MAC=float(mac[i,order[0]]),
                            runner_up_MAC=float(mac[i,order[1]]) if len(order)>1 else None,
                            assigned_rank=int(j)+1 if j is not None else None,
                            assigned_Hz=float(b.time_values[j]) if j is not None else None,
                            assigned_MAC=float(mac[i,j]) if j is not None else None,
                            assigned_sign=int(np.sign(signed[i,j])) if j is not None else None,
                            equal_rank_MAC=float(mac[i,i]) if i<len(right) else None,
                            equal_rank_sign=int(np.sign(signed[i,i])) if i<len(right) else None))
    return dict(method='Squared Euclidean correlation of three signed translations per common solid node; unweighted, not mass-normalized MAC. Assignment maximizes total score across the two supplied bases.',
                common_original_solid_nodes=len(ids),coordinate_tolerance_m=1.e-9,static_pose_checks=[pa,pb],
                reference_rst_sha256=checksum(reference),candidate_rst_sha256=checksum(candidate),modes=records)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference',type=Path);parser.add_argument('candidate',type=Path)
    parser.add_argument('output',type=Path);parser.add_argument('--repeat',action='store_true')
    a=parser.parse_args();record=compare(a.reference,a.candidate)
    if a.repeat:
        if any(row['assigned_rank']!=row['reference_rank'] or row['assigned_MAC']<.999
               or abs(row['assigned_Hz']/row['reference_Hz']-1)>1e-5 for row in record['modes']):
            raise ValueError('Independent repeat disagrees with the reference shapes')
        record['scope']='Isolated bare refined default vs revision-2 bare refined default'
    a.output.parent.mkdir(exist_ok=True,parents=True)
    a.output.write_text(json.dumps(record,indent=2)+'\n')
    print(len(record['modes']),'reference modes;',record['common_original_solid_nodes'],'original solid nodes')
if __name__=='__main__':main()
