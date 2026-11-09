"""Check the physical cell/PLA geometry at the exact times used in the raised-case movies."""
import argparse
from itertools import combinations

import numpy as np
from scipy.spatial import cKDTree
from vtkmodules.vtkCommonDataModel import vtkTriangle

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from curved_cell_contact import contact_solids, sampled_clearance
from early_cell_clearance import bezier, outer_faces, subdivision_weights, unresolved
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FRAMES, FS, integrate, participation

TOL_MM = 1e-8


def envelopes(rest, modes, modal_limit):
    spread = (modal_limit @ np.abs(modes).reshape(len(modes), -1)).reshape(rest.shape)
    return (rest-spread).min(axis=1)-TOL_MM, (rest+spread).max(axis=1)+TOL_MM


def candidate_pairs(first, second):
    """Axis-aligned enclosing boxes include every control point at every film sample."""
    a0, a1 = first
    b0, b1 = second
    centre_a, centre_b = (a0+a1)*.5, (b0+b1)*.5
    ra = np.linalg.norm(a1-centre_a, axis=1)
    rb = np.linalg.norm(b1-centre_b, axis=1)
    near = cKDTree(centre_a).query_ball_point(centre_b, rb+ra.max()+TOL_MM)
    i = np.array([n for group in near for n in group], dtype=int)
    j = np.repeat(np.arange(len(b0)), [len(group) for group in near])
    keep = np.all((a1[i]>=b0[j]) & (b1[j]>=a0[i]), axis=1)
    return i[keep], j[keep]


def triangles_cross(a, b):
    return any(vtkTriangle.TrianglesIntersect(*p[:3], *q[:3]) for p, q in zip(a, b, strict=True))


def separate_convex_hulls(a, b):
    """Try the face normals and edge cross products of both six-point hulls near tangency."""
    remaining = np.arange(len(a))
    edges = list(combinations(range(6), 2))
    faces = list(combinations(range(6), 3))
    axes = [(0, i, j, 0, i, k) for i, j, k in faces]
    axes += [(1, i, j, 1, i, k) for i, j, k in faces]
    axes += [(0, i, j, 1, k, l) for i, j in edges for k, l in edges]
    for left, i, j, right, k, l in axes:
        if not len(remaining):
            break
        p, q = a[remaining], b[remaining]
        x, y = (p,q)[left], (p,q)[right]
        axis = np.cross(x[:,j]-x[:,i], y[:,l]-y[:,k])
        length = np.linalg.norm(axis, axis=1)
        axis /= np.maximum(length, 1e-30)[:,None]
        pa = np.einsum('nij,nj->ni', p-p[:,:1], axis)
        pb = np.einsum('nij,nj->ni', q-p[:,:1], axis)
        gap = np.maximum(pa.min(1)-pb.max(1), pb.min(1)-pa.max(1))
        remaining = remaining[gap<=TOL_MM]
    return remaining


def classify(a, b, weights):
    """Prove separation on curved faces or test for crossing at two triangulation refinements."""
    hits = {}
    for depth in range(9):
        use = unresolved(a, b, TOL_MM)
        if not len(use):
            return 'separated', hits
        a, b = a[use], b[use]
        if depth >= 5:
            use = separate_convex_hulls(a, b)
            if not len(use):
                return 'separated', hits
            a, b = a[use], b[use]
        if depth >= 3:
            hits[depth] = triangles_cross(a, b)
            if hits[depth] and hits.get(depth-1):
                return 'intersecting', hits
        if depth < 8 and len(a) < 50000:
            a = np.repeat(weights @ a[:,None], 4, axis=1).reshape(-1, 6, 3)
            b = np.tile(weights @ b[:,None], (1,4,1,1)).reshape(-1, 6, 3)
        else:
            break
    return 'unresolved', hits


def series(rest, modes, q, weights):
    limits = np.max(np.abs(q), axis=0)
    ia, ib = candidate_pairs(*(envelopes(x, u, limits) for x, u in zip(rest, modes, strict=True)))
    if not len(ia):
        return ['separated']*len(q), 0, []
    sides = []
    for x, u, indices in zip(rest, modes, (ia, ib), strict=True):
        unique, inverse = np.unique(indices, return_inverse=True)
        sides.append((x[unique], np.ascontiguousarray(u[:,unique]).reshape(len(u),-1), inverse))
    states = []
    depths = []
    for start in range(0, len(q), 16):
        samples = q[start:start+16]
        blocks = [x + (samples@u).reshape(len(samples), *x.shape) for x, u, _ in sides]
        for a, b in zip(*blocks, strict=True):
            state, hits = classify(a[sides[0][2]], b[sides[1][2]], weights)
            states.append(state)
            if state == 'intersecting':
                depths.append(max(hits))
    return states, len(ia), depths


def plane_control(weights):
    tri = np.array([[[0.,0.,0.], [1.,0.,0.], [0.,1.,0.]],
                    [[1.3,.1,-1.], [1.3,.1,1.], [1.3,.6,0.]]])
    mid = (tri[:,[0,1,2]] + tri[:,[1,2,0]])*.5
    patches = bezier(np.concatenate([tri, mid], axis=1))
    rest = [p[None] for p in patches]
    modes = [np.zeros_like(p[None]) for p in rest]
    modes[1][:,:,:,0] = -1
    states, _, _ = series(rest, modes, np.array([[0.],[1.],[0.]]), weights)
    assert states == ['separated', 'intersecting', 'separated']


def surface_fields(rst, shapes, solids, fields):
    """Represent every quadratic face in a common frame translating with the cell surface nodes."""
    ids = np.unique(np.concatenate([s.point_data['ansys_node_num'] for s in solids]))
    pos = np.searchsorted(rst.mesh.nnum, ids)
    assert np.array_equal(rst.mesh.nnum[pos], ids)
    xyz = rst.mesh.nodes[pos]*1000
    nodes = [np.searchsorted(ids, f) for f in shapes]
    assert all(np.array_equal(ids[ix], f) for ix,f in zip(nodes,shapes,strict=True))
    phi = 1000*displacement_basis(rst, ids, fields)
    phi -= phi[:,np.unique(np.concatenate([f.ravel() for f in nodes[1:]])),:].mean(axis=1, keepdims=True)
    rest = [bezier(xyz[f]) for f in nodes]
    modes = [bezier(phi[:,f,:]) for f in nodes]
    return ids, xyz, phi, rest, modes


def run(variant, campaign):
    key = variant+'_basis'
    proof, folder, rst = source(key, campaign)
    shapes = [outer_faces(rst, mats) for mats in ([850], [176,187,191])]
    solids = contact_solids(rst)
    fields = field_files(key, campaign, proof['rst_sha256'], rst.nsets)
    ids, xyz, phi, rest, modes = surface_fields(rst, shapes, solids, fields)
    weights = subdivision_weights()
    plane_control(weights)
    control_path = ROOT/'validation/curved_contact'/f'{variant}.json'
    control = read(control_path)
    assert control['basis_RST_sha256'] == proof['rst_sha256']
    control_times = np.array(list(control['times_s'].values()))
    listing = (folder/'solve.out').read_text(errors='replace')
    log_sha = digest(folder/'solve.out')
    t, trials, _ = integrate(rst.time_values, participation(listing, 'X'), 'X', np.rint(control_times*FS).astype(int))
    assert np.array_equal(t, control_times)
    states, _, _ = series(rest, modes, np.vstack([np.zeros(rst.nsets), trials]), weights)
    names = ['tightened', *control['times_s']]
    expected = ['intersecting' if control['states'][name]['3']['intersect'] else 'separated' for name in names]
    assert states == expected, (states, expected)
    stress_path = ROOT/'validation/seeded_pcb_stress_comparison.json'
    stress = read(stress_path)['cases'][variant]
    assert stress['basis_sha256']==proof['rst_sha256'] and stress['coordinate_method']=='Independent integration'
    stress_index = int(stress['peak_frame'])-1  # October counts its frames from one.
    assert FRAMES[stress_index]/FS == stress['peak_time_s']
    results = {}
    for axis in 'XYZ':
        case = variant+'_motion_'+axis
        audit = ROOT/'validation/independent_motion'/(case+'.json')
        motion = read(audit)
        assert motion['campaign']==campaign and motion['basis_rst_sha256']==proof['rst_sha256']
        assert motion['coordinate_method']=='independent' and log_sha==motion['modal_listing_sha256']
        clip = ROOT/'.runtime/post'/campaign/case/'independent/coordinates.npz'
        verified(clip, motion['clip_sha256'])
        with np.load(clip) as data:
            assert np.array_equal(data['time_s'], FRAMES/FS)
            q = data['coordinates']
            states, count, crossing_depths = series(rest, modes, q, weights)
        groups = {name: [i for i,s in enumerate(states) if s==name] for name in ('separated','intersecting','unresolved')}
        assert sum(map(len,groups.values()))==480
        sample = {0}
        if axis=='X':
            sample.add(stress_index)
        if groups['intersecting']:
            crossings = np.asarray(groups['intersecting'])
            runs = np.split(crossings, np.flatnonzero(np.diff(crossings)>1)+1)
            sample.update(int(segment[len(segment)//2]) for segment in runs)
        sample.update(groups['unresolved'])
        checks = {}
        for frame in sorted(sample):
            moved_mm = xyz + (q[frame] @ phi.reshape(len(phi),-1)).reshape(xyz.shape)
            measures = sampled_clearance(solids, ids, moved_mm*.001, levels=(2,3))
            checks[frame] = measures
            if states[frame] != 'unresolved':
                assert measures[3]['intersect']==(states[frame]=='intersecting'), (variant,axis,frame,measures)
        results[axis] = dict(input_audit_sha256=digest(audit), clip_sha256=motion['clip_sha256'],
                             candidate_face_pairs=count, frames=groups, finer_intersection_depths=crossing_depths,
                             full_skin_checks=checks)
        print(variant, axis, count, {k:len(v) for k,v in groups.items()}, flush=True)
    write_json(ROOT/'validation/film_cell_contact'/f'{variant}.json', dict(
        variant=variant, campaign=campaign, basis_sha256=proof['rst_sha256'], control_sha256=digest(control_path),
        control_states=dict(zip(names,expected,strict=True)), quadratic_faces=[len(s) for s in shapes],
        time_s=(FRAMES[[0,-1]]/FS).tolist(), frame_spacing_s=float((FRAMES[1]-FRAMES[0])/FS),
        stress_audit_sha256=digest(stress_path), frame_index_base=0, peak_PCB_stress_X_frame_index=stress_index,
        geometry_tolerance_mm=TOL_MM, axes=results,
        scope='All exterior cell and PLA quadratic faces in physical scale at the 480 displayed instants. '
              'Separated means their Bezier convex hulls were separated, with subdivision as needed. '
              'Intersecting means two successive triangle refinements crossed, starting at eight segments per edge. '
              'The linear response holds the tightened contact state fixed. Sample counts do not measure '
              'contact duration, probability, forces or motion after impact.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=['stand3_nylon','stand3_aluminium'])
    parser.add_argument('--campaign', default='nov08_01')
    args=parser.parse_args()
    run(args.variant, args.campaign)
