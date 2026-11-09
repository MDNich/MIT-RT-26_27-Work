"""Check the locked quadratic case tetrahedra and locate severe native shape warnings."""
import argparse
from math import factorial, prod
from itertools import product
import re

import numpy as np

from audit_local import ROOT, read
from case_stress import source
from check_case_mesh import dL, edges
from film_identity import verified, write_json
from stage_snug_fit import AUDIT, input_record


def cubic_controls():
    # The Jacobian of a quadratic map is linear, so its determinant has degree at most three.
    powers=np.array([a for a in product(range(4),repeat=4) if sum(a)==3])
    sites=powers/3
    bernstein=np.array([[6/prod(factorial(int(e)) for e in a)*np.prod(p**a) for a in powers] for p in sites])
    assert np.allclose(bernstein.sum(axis=1),1) and np.linalg.cond(bernstein)<10
    gradients=[np.vstack([(4*p[i]-1)*dL[i] for i in range(4)]+
                         [4*(p[a]*dL[b]+p[b]*dL[a]) for a,b in edges]) for p in sites]
    return np.linalg.inv(bernstein).T,gradients


def run(variant,campaign):
    name=variant+'_basis'
    proof,directory,rst=source(name,campaign)
    parent=read(ROOT/'.runtime/receipts'/campaign/name/'status.json')['parent']
    setup=input_record(parent)
    hashes={r['name']:r['sha256'] for r in read(ROOT/'.runtime/receipts'/campaign/name/'archived.json')['files']}
    flagged=set()
    for path in sorted(directory.glob('file*.err')):
        verified(path,hashes[path.name])
        for body in re.split(r'\*\*\* (?:WARNING|ERROR) \*\*\*',path.read_text(errors='replace'))[1:]:
            message=' '.join(body.split())
            if 'exceeds the error limit' in message:
                match=re.search(r'\belement (\d+) has ',message,re.I)
                if not match:raise ValueError(message[:250])
                flagged.add(int(match[1]))
    data=rst.grid.cell_data
    elems=np.sort(data['ansys_elem_num'][(data['ansys_elem_type_num']==187)&(data['ansys_material_type']==850)])
    mesh=read(AUDIT/f"mesh_{setup['size_mm']}.json")
    assert len(elems)==mesh['tetrahedra'] and mesh['step_sha256']==setup['step_sha256']
    order=np.argsort(rst.mesh.enum)
    idx=order[np.searchsorted(rst.mesh.enum[order],elems)];assert np.array_equal(rst.mesh.enum[idx],elems)
    native=rst.mesh.elem
    conn=np.stack([native[i][10:20] for i in idx])
    pos=np.searchsorted(rst.mesh.nnum,conn);assert np.array_equal(rst.mesh.nnum[pos],conn)
    x=rst.mesh.nodes[pos]*1000
    transform,gradients=cubic_controls()
    controls=np.stack([np.linalg.det(x.transpose(0,2,1)@g) for g in gradients],axis=1)@transform
    bounds=controls.min(axis=1)
    assert np.isfinite(controls).all() and bounds.min()>1.e-8, 'Inconclusive positive-Jacobian check'
    flagged_case={str(int(e)):dict(minimum_Jacobian_bound_mm3=float(bounds[i]),
                                  centroid_mm=x[i,:4].mean(axis=0).tolist())
                  for i,e in enumerate(elems) if e in flagged}
    result=dict(case=name,campaign=campaign,rst_sha256=proof['rst_sha256'],preload=parent,
                checked_tetrahedra=len(elems),minimum_Jacobian_bound_mm3=float(bounds.min()),
                minimum_bound_element=int(elems[bounds.argmin()]),native_error_limit_elements=sorted(flagged),
                case_error_limit_elements=flagged_case,
                scope='Positive cubic Bernstein coefficient bounds verify orientation of the quadratic PLA '
                      'volume maps in the locked state. Element angles and solution convergence are separate checks.')
    write_json(AUDIT/(name+'_mesh.json'),result)
    print(name,len(elems),'minimum Jacobian bound',bounds.min(),'flagged',flagged_case)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant')
    p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args()
    run(a.variant,a.campaign)
