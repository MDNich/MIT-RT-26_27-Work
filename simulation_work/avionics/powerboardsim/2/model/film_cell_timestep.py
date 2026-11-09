"""Resolve the cell identity and timing of surface intersections between displayed movie frames."""
import argparse

import numpy as np
from scipy.linalg import expm
from scipy.signal import lfilter

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from curved_cell_contact import contact_solids, sampled_clearance
from early_cell_clearance import outer_faces, subdivision_weights
from film_cell_contact import plane_control, series, surface_fields
from film_identity import digest, verified, write_json
from seeded_motion import FRAMES, FS, integrate, participation


def linear_input_displacement(frequency, factor, acc, dt):
    """Exact oscillator recurrence at the knots of a piecewise-linear acceleration input."""
    assert acc[0] == 0.
    omega = 2*np.pi*frequency
    # The auxiliary states are applied acceleration and its constant slope over one interval.
    matrix = np.array([[0,1,0,0],[-omega**2,-.04*omega,-factor,0],[0,0,0,1],[0,0,0,0.]])
    transition = expm(dt*matrix)
    system = transition[:2,:2]
    next_input = transition[:2,3]/dt
    old_input = transition[:2,2]-next_input
    trace = np.trace(system)
    cofactor = system-trace*np.eye(2)
    numerator = [next_input[0],old_input[0]+(cofactor@next_input)[0],(cofactor@old_input)[0]]
    return lfilter(numerator,[1.,-trace,np.linalg.det(system)],acc)


def ramp_control():
    dt = 1/FS
    t = np.arange(4000)*dt
    errors = []
    for freq in (253.,3900.):
        omega = 2*np.pi*freq
        zeta = .02
        damped = omega*np.sqrt(1-zeta**2)
        factor = 1.3
        u = linear_input_displacement(freq,factor,t,dt)
        homogeneous = (2*zeta/omega**3*np.cos(damped*t) +
                       (2*zeta**2-1)/(omega**2*damped)*np.sin(damped*t))
        solution = -factor*(t/omega**2-2*zeta/omega**3+np.exp(-zeta*omega*t)*homogeneous)
        errors.append(float(np.max(abs(solution-u))/np.max(abs(solution))))
    assert max(errors)<1.e-8
    return max(errors)


def refined_coordinates(method, load, samples, frequencies, gamma):
    if method=='linear_input_exact':
        error = ramp_control()
        q = np.column_stack([linear_input_displacement(f,g,load,1/FS)[samples]
                             for f,g in zip(frequencies,gamma,strict=True)])
        return q, dict(integration='Matrix exponential with piecewise-linear input',ramp_control_relative_max_error=error)
    refinement = {'half_step':2,'quarter_step':4}[method]
    dense = np.arange((len(load)-1)*refinement+1)/refinement
    acc = np.interp(dense,np.arange(len(load)),load)
    q = np.empty((len(samples),len(frequencies)))
    scale = 2*FS*refinement
    for k,(f,g) in enumerate(zip(frequencies,gamma,strict=True)):
        omega = 2*np.pi*f
        coefficients = [scale**2+.04*omega*scale+omega**2,2*(omega**2-scale**2),scale**2-.04*omega*scale+omega**2]
        q[:,k] = lfilter(-g*np.array([1.,2.,1.]),coefficients,acc)[samples*refinement]
    return q, dict(integration='Average-acceleration Newmark with piecewise-linear input',integration_step_s=1/(FS*refinement))


def clip_history(variant, axis, campaign, method, modal, folder, samples):
    case = f'{variant}_motion_{axis}'
    validation = 'motion' if method == 'native' else 'independent_motion'
    path = ROOT/'validation'/validation/f'{case}.json'
    proof = read(path)
    assert proof['basis_rst_sha256'] == modal['rst_sha256'] and proof['case'] == case and proof['campaign'] == campaign
    cache = ROOT/'.runtime/post'/campaign/case
    if method == 'native':
        mcf = ROOT/'.runtime/archive'/campaign/case/'file.mcf'
        verified(mcf, proof['mcf_sha256'])
        with mcf.open() as stream:
            for _ in range(9 + int(samples[0])):
                next(stream)
            data = np.loadtxt(stream, max_rows=len(samples))
        assert data.shape == (len(samples),len(modal['frequencies_Hz'])+1)
        assert np.allclose(data[:,0], samples/FS, rtol=0, atol=5.1e-7)
        q = data[:,1:]
        history_sha = proof['mcf_sha256']
    else:
        assert proof['coordinate_method'] == 'independent'
        cache = cache/'independent'
        verified(folder/'solve.out', proof['modal_listing_sha256'])
        gamma = participation((folder/'solve.out').read_text(errors='replace'),axis)
        t, q, _ = integrate(modal['frequencies_Hz'], gamma, axis, samples)
        assert np.array_equal(t,samples/FS)
        history_sha = None
    clip = cache/'coordinates.npz'
    verified(clip,proof['clip_sha256'])
    with np.load(clip) as previous:
        assert np.array_equal(previous['time_s'],FRAMES/FS)
        assert np.array_equal(previous['frequencies_Hz'],modal['frequencies_Hz'])
        assert np.allclose(q[FRAMES-samples[0]],previous['coordinates'],rtol=2.e-11,atol=1.e-17)
    evidence = dict(accepted_motion_sha256=digest(path),clip_sha256=proof['clip_sha256'],native_mcf_sha256=history_sha)
    if method in ('half_step','quarter_step','linear_input_exact'):
        input_path = ROOT/'.runtime/motion_loads'/f'{axis}.txt'
        verified(input_path,proof['input_sha256'])
        table = np.loadtxt(input_path,skiprows=1,max_rows=int(samples[-1])+1)
        assert np.allclose(table[:,0],np.arange(len(table))/FS,rtol=0,atol=5.1e-13)
        refined, control = refined_coordinates(method,table[:,1],samples,modal['frequencies_Hz'],gamma)
        evidence.update(control,sealed_input_sha256=proof['input_sha256'],
                        difference_from_historical_relative_L2=float(np.linalg.norm(refined-q)/np.linalg.norm(q)))
        if method=='linear_input_exact':
            errors = [float(np.linalg.norm(q-refined)/np.linalg.norm(refined))]
            for step in ('half_step','quarter_step'):
                trial, _ = refined_coordinates(step,table[:,1],samples,modal['frequencies_Hz'],gamma)
                errors.append(float(np.linalg.norm(trial-refined)/np.linalg.norm(refined)))
            assert errors[2] < errors[1] < errors[0]
            evidence['nominal_half_quarter_relative_L2_vs_exact'] = errors
        q = refined
    return q,evidence


def intervals(indices):
    if not len(indices):
        return []
    breaks = np.flatnonzero(np.diff(indices)>1)+1
    return [(int(v[0]),int(v[-1])) for v in np.split(indices,breaks)]


def run(variant, axis, campaign, method, cutoff=None):
    key = variant+'_basis'
    modal, folder, rst = source(key,campaign)
    samples = np.arange(FRAMES[0],FRAMES[-1]+1)
    q, evidence = clip_history(variant,axis,campaign,method,modal,folder,samples)
    frequencies = np.asarray(modal['frequencies_Hz'])
    assert np.array_equal(frequencies,rst.time_values)
    keep = np.ones(rst.nsets,dtype=bool) if cutoff is None else frequencies<=cutoff
    if cutoff is not None:
        evidence.update(cutoff_Hz=cutoff,retained_modes=int(keep.sum()),highest_retained_frequency_Hz=float(frequencies[keep][-1]))
        assert method=='independent' and 2000 <= cutoff < frequencies[-1] and np.any(keep)
        q = q[:,keep]
    baseline_path = ROOT/'validation/film_cell_contact'/f'{variant}.json'
    baseline = read(baseline_path)
    assert baseline['variant']==variant and baseline['basis_sha256']==modal['rst_sha256'] and baseline['campaign']==campaign
    force = read(ROOT/'validation/cell_force'/f'{variant}.json')
    assert force['basis_rst_sha256']==modal['rst_sha256']
    materials = sorted(force['geometry'],key=lambda k:force['geometry'][k]['centroid_mm'][0])
    assert materials==['176','191','187']
    cover, cells = contact_solids(rst)
    solids = [cover]+[cells.extract_cells(cells.cell_data['ansys_material_type']==int(k)) for k in materials]
    shapes = [outer_faces(rst,[k]) for k in [850,*map(int,materials)]]
    assert [len(shapes[0]),sum(map(len,shapes[1:]))]==baseline['quadratic_faces']
    field = field_files(key,campaign,modal['rst_sha256'],rst.nsets)
    ids, xyz, phi, rest, modes = surface_fields(rst,shapes,solids,field)
    phi = phi[keep]
    modes = [m[keep] for m in modes]
    weights = subdivision_weights()
    plane_control(weights)
    results = {}
    combined = np.full(len(q),'separated',dtype='U12')
    for i,(cell,material) in enumerate(zip(['left','centre','right'],materials,strict=True),1):
        states, count, depths = series([rest[0],rest[i]],[modes[0],modes[i]],q,weights)
        states = np.asarray(states)
        assert len(states)==len(samples) and set(states) <= {'separated','intersecting','unresolved'}
        combined[(states=='unresolved') & (combined!='intersecting')] = 'unresolved'
        combined[states=='intersecting'] = 'intersecting'
        events = intervals(samples[states=='intersecting'])
        checks = []
        for first,last in events:
            middle = (first+last)//2
            moved = xyz+(q[middle-samples[0]]@phi.reshape(len(phi),-1)).reshape(xyz.shape)
            skins = sampled_clearance([solids[0],solids[i]],ids,moved*.001,(2,3))
            assert skins[3]['intersect'], (cell,middle,skins)
            checks.append(dict(sample=middle,time_s=middle/FS,curved_skins=skins))
        results[cell] = dict(material=int(material),quadratic_faces=len(shapes[i]),candidate_face_pairs=count,
                             crossing_intervals_samples=events,unresolved_intervals_samples=intervals(samples[states=='unresolved']),
                             intersecting_samples=len(depths),midpoint_checks=checks)
        print(variant,axis,method,cell,events,flush=True)
    displayed = combined[FRAMES-samples[0]]
    reference = np.empty(len(FRAMES),dtype=displayed.dtype)
    group = baseline['axes'][axis]['frames']
    assert sorted(group['separated']+group['intersecting']+group['unresolved'])==list(range(len(FRAMES)))
    for state,frames in group.items():
        reference[frames]=state
    differences = np.flatnonzero(reference!=displayed)
    if method=='independent' and cutoff is None:
        assert len(differences)==0
    label = method if cutoff is None else f'{method}_{cutoff}Hz'
    write_json(ROOT/'validation/film_cell_timestep'/f'{variant}_{axis}_{label}.json',dict(
        variant=variant,campaign=campaign,axis=axis,coordinate_method=method,basis_rst_sha256=modal['rst_sha256'],
        **evidence,displayed_frame_control_sha256=digest(baseline_path),samples=len(q),sampling_Hz=FS,
        first_sample=int(samples[0]),last_sample=int(samples[-1]),changed_movie_frames_one_based=(differences+1).tolist(),
        unresolved_samples=int(np.count_nonzero(combined=='unresolved')),intersecting_samples=int(np.count_nonzero(combined=='intersecting')),
        cell_order='Increasing PCB X',cells=results,scope='Physical-scale quadratic skin geometry at every integration station '
        'within the original film interval. Endpoints are integer indices from the start of the excitation. Each '
        'consecutive run is a sequence of predicted surface intersections under fixed open contact.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=['stand3_nylon','stand3_aluminium'])
    p.add_argument('axis',choices=list('XYZ'))
    p.add_argument('--campaign',default='nov08_01')
    p.add_argument('--coordinates',choices=['independent','native','half_step','quarter_step','linear_input_exact'],required=True)
    p.add_argument('--max-frequency',type=int,help='Truncate the existing modal basis at this frequency in Hz.')
    a=p.parse_args()
    run(a.variant,a.axis,a.campaign,a.coordinates,a.max_frequency)
