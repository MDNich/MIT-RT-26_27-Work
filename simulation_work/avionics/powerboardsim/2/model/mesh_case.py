"""Generate a curved quadratic tetrahedral PLA solid in the CAD frame (millimetres)."""
from pathlib import Path
import hashlib,json
import numpy as np
import gmsh
ROOT=Path(__file__).resolve().parents[1]

def make(size, *, step=None, mesh_dir=None, audit_dir=None):
    step=step or next((ROOT/'geometry').glob('*.STEP'))
    audit_dir=audit_dir or ROOT/'validation'
    audit_dir.mkdir(parents=True,exist_ok=True)
    gmsh.initialize()
    gmsh.option.setNumber('General.Terminal',0)
    model=gmsh.model
    (solid,)=model.occ.importShapes(str(step));model.occ.synchronize()
    gmsh.option.setNumber('Mesh.MeshSizeMax',size)
    gmsh.option.setNumber('Mesh.MeshSizeMin',size/3)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',15)
    gmsh.option.setNumber('Mesh.ElementOrder',2)
    model.mesh.generate(3)
    ids,coords,_=model.mesh.getNodes()
    idx=np.argsort(ids);ids=ids[idx];pts=coords.reshape(-1,3)[idx]
    et,ei,en=model.mesh.getElements(*solid)
    assert et.tolist()==[11] # quadratic tetrahedron
    tets=np.searchsorted(ids,en[0].reshape(-1,10))
    det=model.mesh.getElementQualities(ei[0],'minSJ')
    if det.min()<=0:
        model.mesh.optimize('HighOrder')
        ids,coords,_=model.mesh.getNodes()
        idx=np.argsort(ids);ids=ids[idx];pts=coords.reshape(-1,3)[idx]
        et,ei,en=model.mesh.getElements(*solid)
        tets=np.searchsorted(ids,en[0].reshape(-1,10))
        det=model.mesh.getElementQualities(ei[0],'minSJ')
    if det.min()<=0:raise ValueError(f'Inverted case element: scaled Jacobian {det.min()}')
    surf={}
    for _,tag in model.getEntities(2):
        et2,_,ns=model.mesh.getElements(2,tag)
        assert et2.tolist()==[9]
        surf[str(tag)]=np.searchsorted(ids,ns[0].reshape(-1,6))
    vol=model.occ.getMass(*solid)
    folder=mesh_dir or ROOT/'.runtime/mesh';folder.mkdir(exist_ok=True,parents=True)
    np.savez_compressed(folder/f'case_{size:g}.npz',points=pts,tets=tets,**surf)
    j=dict(size_max_mm=size,nodes=len(ids),tetrahedra=len(tets),minimum_scaled_jacobian=float(det.min()),cad_volume_mm3=vol,step_sha256=hashlib.sha256(step.read_bytes()).hexdigest())
    (audit_dir/f'mesh_{size:g}.json').write_text(json.dumps(j,indent=2)+'\n')
    print(j,flush=True);gmsh.finalize()
if __name__=='__main__':
    import sys
    for v in sys.argv[1:]:make(float(v))
