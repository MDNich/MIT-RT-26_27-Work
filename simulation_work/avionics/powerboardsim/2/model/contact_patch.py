"""Drive a local cell/PLA contact patch with the signed motion of the tightened board."""
from collections import defaultdict
import json
from pathlib import Path
import sys

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from dpf_readback import export
from film_identity import digest, verified, write_json
from native_rst import read_rst
from seeded_motion import FS, integrate, participation
from stage_local_jobs import seal

BRANCH = 'stand3_nylon'
MATERIALS = (850, 191, 187)
# SOLID187 corner and midside indices, in native connectivity order.
TET_FACES = (
    (0, 1, 2, 4, 5, 6), (0, 1, 3, 4, 8, 7),
    (1, 2, 3, 5, 9, 8), (2, 0, 3, 6, 7, 9),
)


def subset(grid, material, center, radius, axial_span):
    volume = grid.extract_cells((grid.cell_data['ansys_material_type'] == material)
                                & (grid.cell_data['ansys_elem_type_num'] == 187))
    assert np.all(volume.celltypes == 24)
    connectivity = volume.point_data['ansys_node_num'][volume.cells.reshape(-1, 11)[:, 1:]]
    element_ids = volume.cell_data['ansys_elem_num']
    centroids = volume.cell_centers().points
    axis_points = np.repeat(center[None,:], len(centroids), axis=0)
    axis_points[:,1] = np.clip(centroids[:,1], *axial_span)
    selected = np.linalg.norm(centroids - axis_points, axis=1) <= radius
    faces = defaultdict(list)
    for ei, nodes in enumerate(connectivity):
        for face in TET_FACES:
            side = nodes[list(face)]
            faces[tuple(sorted(side[:3]))].append((ei, side))
    exterior = []
    cut = set()
    for neighbors in faces.values():
        assert len(neighbors) <= 2
        active = [(ei, side) for ei, side in neighbors if selected[ei]]
        if not active:
            continue
        if len(neighbors) == 1:
            ei, side = active[0]
            exterior.append((int(element_ids[ei]), side))
        elif len(active) == 1:
            cut.update(active[0][1].tolist())
    assert cut and exterior
    elements = list(zip(element_ids[selected], connectivity[selected], strict=True))
    return elements, exterior, np.array(sorted(cut))


def coords_at(raw, nodes):
    index = np.searchsorted(raw.mesh.nnum, nodes)
    assert np.array_equal(raw.mesh.nnum[index], nodes)
    return raw.mesh.nodes[index]


def nodal_field(stem, nodes):
    ids = np.fromfile(stem.with_suffix('.ids'), '<i4')
    u = np.fromfile(stem.with_suffix('.u'), '<f8').reshape(-1, 3)
    order = np.argsort(ids)
    take = order[np.searchsorted(ids[order], nodes)]
    assert np.array_equal(ids[take], nodes)
    return u[take]


def local_fields(campaign, radius_mm):
    case = BRANCH + '_basis'
    data = ROOT/'.runtime/archive'/campaign
    evidence = read(ROOT/'validation/clearance_rms'/f'{case}.json')
    assert evidence['campaign'] == campaign
    critical = evidence['scopes']['cells']['directions']['X']
    sample = round(critical['seed_screen']['most_approached_sample_s'] * FS)
    center = .0005 * (np.array(critical['from_xyz_mm']) + critical['to_xyz_mm'])
    static_case = BRANCH + '_static'
    static = read(ROOT/'validation/global'/f'{static_case}.json')
    basis = read(ROOT/'validation/global'/f'{case}.json')
    assert static['campaign'] == basis['campaign'] == campaign
    assert basis['rst_sha256'] == evidence['rst_sha256']
    for name, proof in ((static_case, static), (case, basis)):
        verified(data/name/'file.rst', proof['rst_sha256'])
    original = read_rst(data/static_case/'file.rst')
    modes = read_rst(data/case/'file.rst')
    grid = modes.quadgrid
    cell = grid.extract_cells((grid.cell_data['ansys_material_type'] == 191) & (grid.cell_data['ansys_elem_type_num'] == 187))
    axial_span = tuple(cell.bounds[2:4])
    bodies = {m: subset(grid, m, center, .001*radius_mm, axial_span) for m in MATERIALS}
    groups = {m: np.unique(np.concatenate([n for _, n in body[0]])) for m, body in bodies.items()}
    nodes = np.unique(np.concatenate(list(groups.values())))
    xyz = coords_at(original, nodes)
    k = original.nsets
    stamp = export(static_case, campaign, [k])/f'set_{k:04d}'
    locked = nodal_field(stamp, nodes)
    assert np.max(abs(xyz + locked - coords_at(modes, nodes))) < 1e-9
    log = data/case/'solve.out'
    ledger = read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
    verified(log, next(row['sha256'] for row in ledger['files'] if row['name'] == 'solve.out'))
    freq = modes.time_values
    fields = field_files(case, campaign, basis['rst_sha256'], len(freq))
    phi = np.stack([nodal_field(fields[i+1], nodes) for i in range(len(freq))], axis=-1)
    gamma = participation(log.read_text(errors='replace'), 'X')
    _, q, _ = integrate(freq, gamma, 'X', np.array([sample]))
    amplitude = phi @ q[0]
    driven = np.unique(np.concatenate([bodies[850][2], groups[191], groups[187]]))
    return dict(bodies=bodies, nodes=nodes, xyz=xyz, locked=locked, amplitude=amplitude,
                driven=driven, groups=groups, phi=phi, gamma=gamma, freq=freq,
                native_basis=basis['rst_sha256'], native_static=static['rst_sha256'],
                sample=sample, center=center, axial_span=axial_span)


def mesh_cards(state):
    nodes, xyz = state['nodes'], state['xyz']
    lines = ['/batch', '/prep7', 'csys,0', 'esys,0', 'et,1,solid187',
             'mp,ex,850,3.4269e9', 'mp,ey,850,3.4269e9', 'mp,ez,850,3.0649e9',
             'mp,prxy,850,.35', 'mp,prxz,850,.35', 'mp,pryz,850,.35',
             'mp,gxy,850,1.26922e9', 'mp,gxz,850,1.20154e9', 'mp,gyz,850,1.20154e9',
             'mp,dens,850,1170']
    for m in (191, 187):
        lines.extend([f'mp,ex,{m},2.e11', f'mp,nuxy,{m},.3', f'mp,dens,{m},2200'])
    lines += [f'n,{n},{x:.14g},{y:.14g},{z:.14g}' for n,(x,y,z) in zip(nodes,xyz,strict=True)]
    lines.append('type,1')
    for material, (elements, _, _) in state['bodies'].items():
        lines.append(f'mat,{material}')
        for number, connectivity in elements:
            lines += [f'en,{number},'+','.join(map(str,connectivity[:8])), 'emore,'+','.join(map(str,connectivity[8:]))]
    return lines


def face_cards(state):
    lines = ['et,2,targe170','et,3,conta174','keyopt,3,2,0','keyopt,3,9,0',
             'keyopt,3,12,0','mp,mu,3,0','r,31','rmodif,31,4,-1e-6','rmodif,31,6,-.0006','real,31']
    for material, (_, exterior, _) in state['bodies'].items():
        et = 3 if material == 850 else 2
        lines += [f'type,{et}', 'mat,3']
        for element, face in exterior:
            lines += [f'esel,s,elem,,{element}', 'nsel,none']
            lines.extend(f'nsel,a,node,,{n}' for n in face)
            lines.append('esurf')
    lines.extend(['allsel,all','esel,s,type,,3','cm,PBTOUCH,elem','allsel,all'])
    return lines


def prescribed(state, displacement):
    lines = []
    for n,index in zip(state['driven'],np.searchsorted(state['nodes'],state['driven']),strict=True):
        for dof, value in zip(('ux','uy','uz'),displacement[index],strict=True):
            lines.append(f'd,{n},{dof},{value:.14g}')
    return lines


def make_static(state, contact):
    lines = mesh_cards(state)
    if contact:
        lines.extend(face_cards(state))
    lines += ['allsel,all','finish','/solu','antype,static','nlgeom,on','nropt,full','autots,on',
              'neqit,60','kbc,0','outres,all,all']
    if contact:
        lines.append('cncheck,detail,31,31')
    for step,scale in enumerate((0.,1.,0.),1):
        lines += prescribed(state,state['locked']+scale*state['amplitude'])
        lines += [f'time,{step}','nsubst,10,400,5','solve']
    lines += ['finish','/post1','file,file,rst','set,last','/com,LOCAL_CUT_PATH_COMPLETED','finish','/exit,nosave']
    return ('\n'.join(lines)+'\n').encode()


def stage(campaign):
    rt = ROOT/'.runtime'
    catalog = {}
    for radius in (9,15):
        state = local_fields(campaign,radius)
        for contact in (False,True):
            kind = 'contact' if contact else 'free'
            case = f'patch_{BRANCH}_span{radius}_{kind}_v1'
            folder = rt/'inputs'/case
            folder.mkdir(exist_ok=True)
            sha = seal(folder/'model.inp',make_static(state,contact))
            sets = {str(m):dict(tetrahedra=len(parts[0]),exterior_faces=len(parts[1]),cut_nodes=len(parts[2]))
                    for m,parts in state['bodies'].items()}
            info = dict(case=case,campaign=campaign,radius_mm=radius,contact=contact,
                        input_sha256=sha,parent_modal_sha256=state['native_basis'],parent_static_sha256=state['native_static'],
                        center_xyz_mm=(state['center']*1e3).tolist(),cell_span_y_mm=(np.array(state['axial_span'])*1e3).tolist(),forced_sample_s=state['sample']/FS,
                        material_sets=sets,nodes=len(state['nodes']),driven_nodes=len(state['driven']),
                        units='m, N, Pa',loading='Static cut-boundary path from the tightened state to the X waveform sample and back. Cell nodes follow the global field.')
            catalog[case]=info
    write_json(ROOT/'validation/contact_patch_inputs.json',catalog)
    print({n:(s['nodes'],s['driven_nodes']) for n,s in catalog.items()})

if __name__ == '__main__':
    stage(sys.argv[1])
