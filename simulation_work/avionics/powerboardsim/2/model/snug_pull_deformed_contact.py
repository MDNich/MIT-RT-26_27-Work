"""Compare DPF-displaced pocket facets and the fitted rigid cell with saved nonlinear contact states."""
import argparse
from pathlib import Path

import numpy as np
import pyvista as pv
from ansys.mapdl import reader

from audit_local import read,ROOT
from film_identity import digest,verified,write_json
from local_equilibrium import positions
from pull_pose_clearance import rigid_pose
from snug_bare_pull_poses import collision_probe
from snug_local_checkpoint import CASE
from stage_snug_fit import AUDIT


def run(folder):
    path=AUDIT/(CASE+'_'+folder.name+'_checkpoint.json')
    check=read(path);verified(folder/'pull.rst',check['rst_sha256'])
    assert check['case']==CASE and not check['completed']
    raw=reader.read_binary(str(folder/'pull.rst'))
    points=folder/'dpf_points'
    verified(points/'request.json',check['DPF_files']['dpf_points/request.json'])
    verified(points/'displacements.bin',check['pose_check']['DPF_translations_sha256'])
    nodes=np.array(read(points/'request.json')['nodes'])
    u=np.fromfile(points/'displacements.bin','<f8').reshape(raw.nsets,len(nodes),3)
    mesh=read(ROOT/'.runtime/local_inputs/lateral_friction_locked/mesh.json')
    attached=np.array(mesh['attachment']);pilot=raw.mesh.nodes[positions(raw.mesh.nnum,[mesh['pilot']])[0]]
    elem=raw.mesh.elem
    pairs=np.stack([e[10:18] for e in elem if e[1]==862 and e[2]==861])
    assert np.array_equal(pairs[:,2],pairs[:,3]) and np.array_equal(pairs[:,2],pairs[:,6])
    selected,conn=np.unique(pairs[:,[0,1,2,4,5,7]],return_inverse=True)
    control=np.column_stack([np.full(len(pairs),6),conn.reshape(-1,6)])
    surfaces=np.full(len(pairs),pv.CellType.QUADRATIC_TRIANGLE)
    targets=np.stack([e[10:14] for e in elem if e[1]==861 and e[2]==861])
    faces=targets[targets[:,2]>0]
    assert len(faces)==len(targets)-1 and np.array_equal(faces[:,2],faces[:,3])
    ids,local=np.unique(faces[:,:3],return_inverse=True)
    triangles=local.reshape(-1,3)
    cell=pv.PolyData(raw.mesh.nodes[positions(raw.mesh.nnum,ids)],np.c_[np.full(len(triangles),3),triangles])
    assert cell.n_open_edges==0
    xyz=raw.mesh.nodes[positions(raw.mesh.nnum,selected)]
    initial=raw.mesh.nodes[positions(raw.mesh.nnum,attached)]
    k0,k1=[r['native_set'] for r in check['first_loaded_moving_cell_bracket']]
    states=[]
    for k in [k0,k1,check['last_common_travel']['cased']['set']]:
        row=check['states'][k-1]; disp=u[k-1]
        rotation,translation,resid=rigid_pose(initial,initial+disp[positions(nodes,attached)],pilot)
        pos=xyz+disp[positions(nodes,selected)]
        patch=pv.UnstructuredGrid(control,surfaces,pos)
        patch.point_data['double_coordinates']=pos
        rec=[]
        for level in (2,3):
            shell=patch.extract_surface(nonlinear_subdivision=level,algorithm='dataset_surface').triangulate()
            shell.points=shell.point_data['double_coordinates']
            assert shell.n_cells==len(pairs)*4**level
            crosses=collision_probe(cell,shell)(pilot,rotation,translation)
            rec.append(dict(subdivision=level,facet_intersection=bool(crosses)))
        c=row['both_contact_pairs']['861']
        states.append(dict(native_set=k,pilot_travel_mm=row['travel_mm'],native_closed_faces=c['closed_faces'],
                           native_loaded_penetration_mm=c['max_loaded_penetration_mm'],surface_tests=rec,
                           rigid_fit_residual_mm=resid))
        print(states[-1],flush=True)
    write_json(AUDIT/(CASE+'_'+folder.name+'_deformed_faces.json'),dict(checkpoint_sha256=digest(path),
               moving_cell_target_facets=int(len(targets)-1),selected_quadratic_PLA_faces=len(pairs),states=states,
               scope='Geometric intersection of the meshed moving cell with the deformed native pocket selection. '
                     'The two subdivisions approximate the curved PLA surface and do not measure contact pressure.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);run(parser.parse_args().folder)
