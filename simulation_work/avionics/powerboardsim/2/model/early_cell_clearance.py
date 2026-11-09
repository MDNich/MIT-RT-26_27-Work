"""Bound cell-to-PLA clearance during the seeded vibration ramp leading to the nickel stress screen."""
import argparse

import numpy as np
from scipy.spatial import cKDTree

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from clearance_response import surface
from film_identity import digest, verified, write_json
from seeded_motion import FS, integrate, participation

EDGES = [(0,1), (1,2), (2,0)]
TET_SIDES = [[0,1,2,4,5,6], [0,1,3,4,8,7], [0,2,3,6,9,7], [1,2,3,5,9,8]]


def outer_faces(rst, mats):
    cells = rst.grid.cell_data
    elem = cells['ansys_elem_num'][(cells['ansys_elem_type_num'] == 187) & np.isin(cells['ansys_material_type'], mats)]
    order = np.argsort(rst.mesh.enum)
    pos = order[np.searchsorted(rst.mesh.enum[order], elem)]
    assert np.array_equal(rst.mesh.enum[pos], elem)
    raw = rst.mesh.elem
    tets = np.stack([raw[i][10:20] for i in pos])
    faces = tets[:,TET_SIDES].reshape(-1,6)
    _, first, counts = np.unique(np.sort(faces[:,:3], axis=1), axis=0, return_index=True, return_counts=True)
    assert counts.max() == 2
    faces = faces[first[counts == 1]]
    _, flat, ids, _ = surface(rst, mats)
    # Confirm all four triangles and every true midside identity against the native skin reader.
    split = [[0,3,5], [3,1,4], [5,4,2], [3,4,5]]
    def sorted_rows(tri):
        key = np.sort(tri.reshape(-1,3), axis=1)
        return key[np.lexsort(key.T)]
    assert np.array_equal(sorted_rows(faces[:,split]), sorted_rows(ids[flat]))
    return faces


def bezier(lagrange):
    """Convert six interpolation points to the convex-hull controls of the same triangle."""
    ctrl = lagrange.copy()
    for i,(a,b) in enumerate(EDGES):
        ctrl[...,3+i,:] = 2*lagrange[...,3+i,:] - .5*(lagrange[...,a,:]+lagrange[...,b,:])
    return ctrl


def subdivision_weights():
    vertices = np.eye(3)
    mids = np.array([.5*(vertices[a]+vertices[b]) for a,b in EDGES])
    nodes = np.concatenate([vertices,mids])
    children = nodes[[[0,3,5],[3,1,4],[5,4,2],[3,4,5]]]
    middle = [.5*(children[:,a]+children[:,b]) for a,b in EDGES]
    sites = np.concatenate([children,np.stack(middle,axis=1)],axis=1)
    coefficients = np.concatenate([sites**2, np.stack([2*sites[:,:,a]*sites[:,:,b] for a,b in EDGES],axis=2)],axis=2)
    weights = bezier(coefficients)
    # Exact de Casteljau restriction. Every new control lies in its parent hull.
    assert np.all(weights>=0) and np.allclose(weights.sum(axis=2),1)
    return weights


def unresolved(a, b, minimum):
    """Return hull pairs whose separation still needs a finer geometric test."""
    lower = np.maximum(a.min(1)-b.max(1), b.min(1)-a.max(1))
    keep = np.flatnonzero(np.linalg.norm(np.maximum(0,lower),axis=1) <= minimum)
    for j in (0,1,2):
        if not len(keep):
            break
        p = a[keep] if j == 0 else b[keep]
        if j < 2:
            axis = np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
        else:
            axis = a[keep].mean(1)-b[keep].mean(1)
        length = np.linalg.norm(axis,axis=1)
        normal = axis/np.maximum(length[:,None],1e-30)
        # Shift by a common origin before projection to reduce round-off.
        pa = np.einsum('nij,nj->ni', a[keep]-p[:,0,None,:],normal)
        pb = np.einsum('nij,nj->ni', b[keep]-p[:,0,None,:],normal)
        gap = np.maximum(pb.min(1)-pa.max(1),pa.min(1)-pb.max(1))
        keep = keep[gap <= minimum]
    return keep


def clearance_at_rest(a,b,minimum):
    minimum += 1e-8  # Geometry is in millimetres.
    def spheres(ctrl):
        lo,hi = ctrl.min(1),ctrl.max(1)
        return (lo+hi)*.5,np.linalg.norm((hi-lo)*.5,axis=1)
    ctr_a,ra = spheres(a)
    ctr_b,rb = spheres(b)
    choices = cKDTree(ctr_a).query_ball_point(ctr_b,rb+ra.max()+minimum)
    ia = np.array([i for group in choices for i in group],int)
    ib = np.repeat(np.arange(len(b)),[len(group) for group in choices])
    separation = np.linalg.norm(ctr_a[ia]-ctr_b[ib],axis=1)-ra[ia]-rb[ib]
    pick = np.flatnonzero(separation <= minimum)
    pending_a, pending_b = a[ia[pick]], b[ib[pick]]
    weights = subdivision_weights()
    counts = []
    for depth in range(9):
        idx = unresolved(pending_a,pending_b,minimum)
        counts.append(len(idx))
        if not len(idx):
            return counts
        # Patch vertices are actual points on the quadratic surfaces.
        points = pending_a[idx,:3,None,:] - pending_b[idx,None,:3,:]
        if np.linalg.norm(points,axis=3).min() < minimum-2e-8:
            raise ValueError('A pair of surface points violates the requested separation')
        if depth == 8 or len(idx) > 50_000:
            raise ValueError(f'Could not certify the requested separation: {counts}')
        child_a = weights @ pending_a[idx,None,:,:]
        child_b = weights @ pending_b[idx,None,:,:]
        pending_a = np.repeat(child_a,4,axis=1).reshape(-1,6,3)
        pending_b = np.tile(child_b,(1,4,1,1)).reshape(-1,6,3)
    raise AssertionError('Missing clearance classification')


def run(variant, campaign, axis="X"):
    trial_path = ROOT / 'validation/nickel_vibration' / f'{variant}_{axis}.json'
    trial = read(trial_path)
    basis = variant+'_basis'
    proof, folder, rst = source(basis,campaign)
    assert trial['variant']==variant and trial['campaign']==campaign and trial['modal_rst']==proof['rst_sha256']
    log = folder/'solve.out'
    verified(log, trial['modal_listing'])
    if trial['axis'] != axis or trial['first_sample_above_reference'] is None:
        raise ValueError(f'No {axis} stress crossing is recorded for {variant}')
    last = trial['first_sample_above_reference']['sample']
    t, q, _ = integrate(rst.time_values, participation(log.read_text(errors='replace'),axis), axis,np.arange(last+1))
    shapes = [outer_faces(rst,ms) for ms in ([850],[176,187,191])]
    ids = np.unique(np.concatenate([s.ravel() for s in shapes]))
    ix = np.searchsorted(rst.mesh.nnum,ids)
    assert np.array_equal(rst.mesh.nnum[ix],ids)
    xyz = rst.mesh.nodes[ix] * 1000
    nodes = [np.searchsorted(ids,s) for s in shapes]
    ctrl = [bezier(xyz[n]) for n in nodes]
    # A conservative clearance below the smallest previously sampled vertex gap.
    minimum = .13
    separation = clearance_at_rest(*ctrl,minimum)
    modes = np.empty((rst.nsets,len(ids),3))
    for k, stem in field_files(basis,campaign,proof['rst_sha256'],rst.nsets).items():
        nums = np.fromfile(stem.with_suffix('.ids'),'<i4')
        field = np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        order = np.argsort(nums)
        select = order[np.searchsorted(nums[order],ids)]
        assert np.array_equal(nums[select],ids)
        modes[k-1] = 1000*field[select]
    # Translation of the same frame cancels from the distance between the two bodies.
    modes -= modes[:,np.unique(nodes[1]),:].mean(axis=1,keepdims=True)
    bound = {}
    for name, faces in zip(('PLA','cells'),nodes,strict=True):
        peak = 0.
        for i in range(0,len(faces),64):
            controls = bezier(modes[:,faces[i:i+64],:])
            motion = q @ controls.reshape(len(modes),-1)
            peak = max(peak, float(np.linalg.norm(motion.reshape(-1,3),axis=1).max()))
        bound[name] = peak
    residual = minimum-sum(bound.values())
    assert residual > 1e-6, (minimum,bound)
    out = ROOT/'validation/nickel_vibration'/f'{variant}_{axis}_clearance.json'
    write_json(out,dict(variant=variant, axis=axis, campaign=campaign, basis_rst=proof['rst_sha256'], trial_sha256=digest(trial_path),
        last_sample=last,through_time_s=float(t[-1]),surface_face_counts=[len(s) for s in shapes],
        certified_initial_clearance_lower_mm=minimum,unresolved_hull_pairs_by_subdivision=separation,
        peak_control_motion_in_common_frame_mm=bound,certified_remaining_cell_clearance_lower_mm=residual,
        scope='All quadratic cell and PLA exterior faces; convex-hull separation checked at lock. Bounds on '
              'all Bézier control-point displacements include every sampled instant up through the first nickel '
              'stress screening event. Applies to this recorded waveform and its piecewise linear time interpolation.'))
    print(variant, separation, bound, residual)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=['stand3_nylon','stand3_aluminium'])
    p.add_argument('--campaign',default='nov08_01')
    p.add_argument('--axis',choices=list('XYZ'),default='X')
    a = p.parse_args()
    run(a.variant,a.campaign,a.axis)
