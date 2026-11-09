"""Check MAPDL midside-node order and integrate its isoparametric SOLID187 volume."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
edges=[(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)]
dL=np.asarray([[-1,-1,-1],[1,0,0],[0,1,0],[0,0,1]])
# Degree-three tetrahedral rule for the cubic determinant of a quadratic coordinate map.
points=[(np.full(4,.25),-.8)]
for i in range(4):
    xi=np.full(4,1/6);xi[i]=.5;points.append((xi,.45))
def check(path, *, audit_dir=None):
    m=np.load(path);x=m['points'][m['tets'][:,[0,1,2,3,4,5,6,7,9,8]]]
    deviation=[]
    for j,(a,b) in enumerate(edges):
        half=(x[:,a]+x[:,b])/2
        err=np.linalg.norm(x[:,4+j]-half,axis=1)/np.linalg.norm(x[:,a]-x[:,b],axis=1)
        deviation.append(float(np.median(err)))
    assert max(deviation)<1e-6
    volume=0;min_det=1e12
    for L,w in points:
        mat=np.vstack([(4*L[i]-1)*dL[i] for i in range(4)]+[4*(L[a]*dL[b]+L[b]*dL[a]) for a,b in edges])
        det=np.linalg.det(x.transpose(0,2,1)@mat)
        volume+=w*det.sum()/6;min_det=min(min_det,float(det.min()))
    cad=json.loads(((audit_dir or ROOT/'validation')/('mesh_'+path.stem.split('_')[1]+'.json')).read_text())['cad_volume_mm3']
    assert min_det>0 and abs(volume/cad-1)<.001
    return dict(mesh=path.name,solids=len(x),volume_mm3=volume,cad_volume_mm3=cad,relative_volume_error=volume/cad-1,minimum_det_probe_mm3=min_det,median_relative_midpoint_deviation=deviation)
if __name__=='__main__':
    j=[check(p) for p in sorted((ROOT/'.runtime/mesh').glob('case_*.npz'))]
    (ROOT/'validation/solid187_mapping.json').write_text(json.dumps(j,indent=2)+'\n')
    print([(x['mesh'],x['volume_mm3']) for x in j])
