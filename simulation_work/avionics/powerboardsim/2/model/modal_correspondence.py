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


def native_points(result):
    grid=result.grid
    typ=grid.cell_data['ansys_elem_type_num']
    material=grid.cell_data['ansys_material_type']
    common=np.isin(typ,[185,186,187]) & (material<850)
    sub=grid.extract_cells(common)
    ids=sub.point_data['ansys_node_num']
    ix=np.argsort(ids)
    assert np.all(np.diff(ids[ix])>0)
    return ids[ix],sub.points[ix]


def modes(result, ids):
    f=result.time_values
    if not len(f) or np.any(f<=0) or np.any(np.diff(f)<=0):raise ValueError('Expected a pure positive-frequency modal basis')
    out=np.empty((len(f),len(ids)*3))
    for k in range(len(f)):
        numbers,u=result.nodal_displacement(k)
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
    ids,xyz=native_points(a)
    other,loc=native_points(b)
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
                common_original_solid_nodes=len(ids),coordinate_tolerance_m=1.e-9,
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
