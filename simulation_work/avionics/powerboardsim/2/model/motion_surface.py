"""Expand the native modal coordinates without losing the sign or mixing neighboring elements."""
import argparse
import json
from pathlib import Path

import numpy as np
import pyvista as pv
from native_rst import read_rst

from pcb_dynamic_stress import digest, equivalent
from seeded_motion import FRAMES,FS,ROOT


def displacement_basis(r,ids,fields=None):
    ids=np.asarray(ids)
    out=np.empty((len(r.time_values),len(ids),3))
    for k in range(len(out)):
        if fields is None:
            node,u=r.nodal_displacement(k)
        else:
            stem=fields[k+1]
            node=np.fromfile(stem.with_suffix('.ids'),'<i4')
            u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        order=np.argsort(node);ix=np.searchsorted(node[order],ids)
        if np.any(ix==len(node)) or not np.array_equal(node[order[ix]],ids):
            raise ValueError('Missing result node')
        out[k]=u[order[ix],:3]
    if not np.isfinite(out).all():raise ValueError('Invalid native shape')
    return out


def pcb_skin(r,locations):
    grid=r.grid
    pcb=grid.extract_cells((grid.cell_data['ansys_material_type']==208)&np.isin(grid.cell_data['ansys_elem_type_num'],[185,186,187]))
    surface=pcb.extract_surface(algorithm='dataset_surface',nonlinear_subdivision=0).triangulate()
    corner=surface.faces.reshape(-1,4)[:,1:]
    node=surface.point_data['ansys_node_num'][corner]
    element=surface.cell_data['ansys_elem_num'][:,None]*np.ones((1,3),dtype=np.int64)
    e=np.repeat(locations['element'],locations['counts']).astype(np.int64)
    n=locations['node'].astype(np.int64)
    stride=max(n.max(),int(node.max()))+1
    key=e*stride+n
    order=np.argsort(key,kind='stable')
    keys=element.astype(np.int64)*stride+node
    selected=np.searchsorted(key[order],keys)
    if selected.max()>=len(order) or not np.array_equal(key[order[selected]],keys):raise ValueError('Unmapped PCB surface corner')
    ix,conn=np.unique(order[selected],return_inverse=True)
    ids=n[ix]
    # Each vertex belongs to one element and one specific corner. Geometry can share
    # a point, but stress is discontinuous at element boundaries.
    xyz=r.mesh.nodes[np.searchsorted(r.mesh.nnum,ids)]
    if not np.allclose(xyz[conn.reshape(-1,3)],surface.points[corner],rtol=0,atol=1e-8):
        raise ValueError('Stress corner does not coincide with its surface vertex')
    faces=np.column_stack((np.full(len(corner),3),conn.reshape(-1,3)))
    return pv.PolyData(xyz,faces),ids,ix


def verify(rst,cache):
    source=ROOT.parent/'1/output/latex/random_vibration/reproduction/motion'
    r=read_rst(str(rst))
    record=dict(rst_sha256=digest(rst),axes={})
    assert record['rst_sha256']==json.loads((cache/'basis.json').read_text())['rst_sha256']
    for axis in 'XYZ':
        hist=np.genfromtxt(source/f'native/expand_{axis}/native_node_checks.csv',delimiter=',',names=True)
        uniq=np.unique(hist['node'].astype(int));q=np.loadtxt(source/f'inputs/modal_coordinates_{axis}_clip.csv',delimiter=',',skiprows=1)
        if axis=='X':refids=uniq;basis=displacement_basis(r,uniq);clip_x=q[:,1:]
        assert np.array_equal(uniq,refids)
        predicted=(q[:,1:]@basis.reshape(len(basis),-1)).reshape(480,len(uniq),3)
        t=hist['set'].astype(int)-1; n=np.searchsorted(uniq,hist['node'])
        ref=np.column_stack([hist['u'+i] for i in 'xyz'])
        assert np.array_equal(np.unique(t)+1,[1,2,120,240,360,480]) and len(set(zip(t,n)))==len(t)==6*len(uniq) and np.allclose(hist['time'],FRAMES[t]/FS,rtol=0,atol=1e-10)
        error=predicted[t,n]-ref
        max_abs=float(abs(error).max());rel=float(np.linalg.norm(error)/np.linalg.norm(ref))
        if rel>1e-5 or max_abs>1e-8:raise ValueError((axis,rel,max_abs))
        record['axes'][axis]=dict(native_comparison_frame_indices=(np.unique(t)+1).tolist(),observed_nodes=uniq.tolist(),peak_difference_m=max_abs,relative_L2=rel)
        if axis=='X':
            frames=json.loads((source/'audits/dpf_stress_unaveraged_frames.json').read_text())
            expected=np.array([[row['u_nodes'][str(node)] for node in uniq] for row in frames])
            assert expected.shape==predicted.shape and np.array_equal([row['frame'] for row in frames],np.arange(1,481))
            dpf_err=abs(expected-predicted).max()
            assert dpf_err<1e-8
            record['axes'][axis].update(dpf_comparison_frames=480,dpf_max_difference_m=float(dpf_err))
    mesh,nodes,rows=pcb_skin(r,np.load(cache/'locations.npz'))
    stress=np.load(cache/'tensors.npy',mmap_mode='r')
    xmax=-1
    # Audit the field actually drawn on the exterior skin. Interior and boundary
    # extrema can be different, even with a correct element-corner mapping.
    for k in range(0,len(rows),2048):
        block=np.ascontiguousarray(stress[:,rows[k:k+2048]]).reshape(len(stress),-1)
        xmax=max(xmax,float(equivalent((clip_x@block).reshape(480,-1,6)).max()))
    whole=json.loads((ROOT/'validation/pcb_dynamic_stress_reader.json').read_text())['peak_dynamic_von_Mises_Pa']
    assert xmax>0 and xmax<whole*(1+1e-10)
    record['surface']=dict(triangles=mesh.n_cells,element_corner_vertices=len(rows),distinct_geometry_nodes=len(np.unique(nodes)),maximum_visible_Pa=xmax,maximum_full_PCB_Pa=whole)
    assert record['surface']['distinct_geometry_nodes']<len(rows)
    (ROOT/'validation/motion_surface_reader.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('rst',type=Path);p.add_argument('stress_cache',type=Path)
    a=p.parse_args();verify(a.rst,a.stress_cache)
