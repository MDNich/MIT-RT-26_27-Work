"""Compare first touch of the registered quadratic FE skins with the exact native Balius CAD."""
import numpy as np
import pyvista as pv
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersModeling import vtkCollisionDetectionFilter

from case_fit import PCB_BOTTOM,PCB_CENTER
from film_identity import digest, verified, write_json
from native_rst import read_rst
from audit_local import read,ROOT
from stage_snug_fit import AUDIT,MESH


def skin(mesh, subdivision):
    local=mesh['points']
    xyz=np.column_stack((PCB_CENTER[0]+local[:,0],PCB_CENTER[1]+local[:,2],PCB_BOTTOM-10-1.25-local[:,1]))
    tri=np.concatenate([mesh[k] for k in mesh if k.isdigit()])
    boundary=pv.UnstructuredGrid(np.c_[np.full(len(tri),6),tri],np.full(len(tri),pv.CellType.QUADRATIC_TRIANGLE),xyz)
    boundary.point_data['xyz64']=xyz
    result=boundary.extract_surface(algorithm='dataset_surface',nonlinear_subdivision=subdivision).triangulate()
    result.points=result.point_data['xyz64']
    return result


def first_hit(moving,target):
    trans=vtkTransform()
    detect=vtkCollisionDetectionFilter()
    detect.SetInputData(0,moving);detect.SetInputData(1,target)
    detect.SetTransform(0,trans);detect.SetTransform(1,vtkTransform())
    detect.SetCellTolerance(0.);detect.SetBoxTolerance(0.);detect.SetCollisionModeToFirstContact()
    def hit(spacing):
        trans.Identity();trans.Translate(0.,0.,1.25-spacing);detect.Update()
        return bool(detect.GetNumberOfContacts())
    lo,hi=1.05,1.45
    assert hit(lo) and not hit(hi)
    initial=hit(1.25)
    while hi-lo>.00025:
        mid=(lo+hi)/2
        if hit(mid):lo=mid
        else:hi=mid
    return dict(intersects_at_1p25=initial,first_touch_standoff_bracket_mm=[lo,hi])


def run(sizes=(2,3), audit_file='cell_surface_closure.json'):
    proof=read(ROOT/'validation/global/bare_static.json')
    path=ROOT/'.runtime/archive'/proof['campaign']/'bare_static/file.rst';verified(path,proof['rst_sha256'])
    grid=read_rst(path).quadgrid
    # The native global Workbench RST uses metres. Restore double precision in millimetres.
    grid.points=grid.points.astype(float)*1000
    grid.point_data['xyz64']=grid.points
    targets={}
    for body,mat in [(4,176),(19,191),(15,187)]:
        elem=np.isin(grid.cell_data['ansys_elem_type_num'],[185,186,187])&(grid.cell_data['ansys_material_type']==mat)
        cell=grid.extract_cells(elem)
        for sub in (2,3):
            target=cell.extract_surface(algorithm='dataset_surface',nonlinear_subdivision=sub).triangulate()
            target.points=target.point_data['xyz64'];targets[body,sub]=target
    rows=[]
    for mesh_size in sizes:
        file=MESH/f'case_{mesh_size}.npz'
        with np.load(file) as mesh:
            for sub in (2,3):
                case=skin(mesh,sub)
                for (body,level),target in targets.items():
                    if level==sub:
                        row=dict(mesh_mm=mesh_size,subdivision=sub,cell_STEP_body=body,**first_hit(case,target))
                        rows.append(row);print(row,flush=True)
    write_json(AUDIT/audit_file,dict(bare_rst_sha256=proof['rst_sha256'],mesh_sha256={k:digest(MESH/f'case_{k}.npz') for k in sizes},rows=rows,
               scope='Undeformed quadratic skins, rigid translation only. Contact formulation, preload and cell rotation affect native reactions.'))


if __name__=='__main__':run()
