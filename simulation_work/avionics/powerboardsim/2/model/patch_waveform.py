"""Locate an early sampled geometric contact in the central cell region for a transient replay."""
import sys
import numpy as np
from audit_contact_patch import exterior
from contact_patch import BRANCH, ROOT, FS, integrate, local_fields
from film_identity import write_json

def footprint(campaign,state):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    from basis_comparison import field_files
    from clearance_response import surface
    from contact_patch import nodal_field
    from native_rst import read_rst
    case=BRANCH+'_basis'
    raw=read_rst(ROOT/'.runtime/archive'/campaign/case/'file.rst')
    fields=field_files(case,campaign,state['native_basis'],raw.nsets)
    _,q,_=integrate(state['freq'],state['gamma'],'X',np.array([state['sample']]))
    def displaced(materials):
        skin,_,ids,_=surface(raw,materials)
        skin.points=skin.points+sum(nodal_field(fields[k+1],ids)*w for k,w in enumerate(q[0]))
        return skin
    result,count=displaced([850]).collision(displaced([176,187,191]),contact_mode=0,box_tolerance=0.,cell_tolerance=0.)
    expected=read_clearance()['scopes']['cells']['directions']['X']['seed_screen']['intersecting_triangle_pairs_at_that_sample']
    assert count==expected
    faces=np.unique(result.field_data['ContactCells']);centers=result.cell_centers().points[faces]*1000
    pairs=cKDTree(centers).query_pairs(4,output_type='ndarray')
    graph=coo_matrix((np.ones(len(pairs)),pairs.T),shape=(len(centers),len(centers)))
    _,groups=connected_components(graph,directed=False)
    return dict(time_s=state['sample']/FS,triangle_pairs=int(count),distinct_PLA_triangles=len(centers),
        neighbor_distance_mm=4,groups=[dict(PLA_triangles=int(np.sum(groups==i)),
        minimum_xyz_mm=centers[groups==i].min(axis=0).tolist(),maximum_xyz_mm=centers[groups==i].max(axis=0).tolist())
        for i in np.unique(groups)])
def read_clearance():
    from audit_local import read
    return read(ROOT/'validation/clearance_rms'/(BRANCH+'_basis.json'))

def probe(campaign):
    state=local_fields(campaign,9)
    stop=round(.25*FS)
    t,q,_=integrate(state['freq'],state['gamma'],'X',np.arange(stop+1))
    base=state['xyz']+state['locked']
    pla=exterior(state,[850],state['locked'])
    cells=exterior(state,[187,191],state['locked'])
    def hits(i):
        xyz=base+state['phi']@q[i]
        pla.points=xyz
        cells.points=xyz
        _,count=pla.collision(cells,contact_mode=1,box_tolerance=0.,cell_tolerance=0.)
        return int(count)
    stride=8
    assert hits(0)==0
    high=next((i for i in range(stride,stop+1,stride) if hits(i)),None)
    if high is None:raise ValueError('No central cell crossing in the initial quarter second')
    low=high-stride
    first=next(i for i in range(low+1,high+1) if hits(i))
    assert hits(first-1)==0 and hits(first)>0
    until=int(np.ceil((first+.004*FS)/8))*8
    record=dict(campaign=campaign,branch=BRANCH,global_basis_sha256=state['native_basis'],
        original_sampling_Hz=FS,early_search_stride=stride,examined_geometry='Both cell skins and PLA in the central axial band of radius 9 mm',
        sampled_clear_time_s=float(t[first-1]),sampled_contact_time_s=float(t[first]),replay_last_index=until,
        replay_last_time_s=until/FS,scope='The first hit on the 8192 Hz survey grid is refined on its preceding eight original samples. Earlier excursions between survey samples and contact elsewhere in the assembly are unresolved.')
    record['full_assembly_peak_intersections']=footprint(campaign,state)
    write_json(ROOT/'validation/patch_waveform.json',record)
    print(record)
if __name__=='__main__':probe(sys.argv[1])
