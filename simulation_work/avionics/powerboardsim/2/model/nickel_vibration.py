"""Evaluate the six battery strips under base vibration using their stored element-corner tensors."""
import argparse
import fcntl
import re

import numpy as np

from audit_local import ROOT, read
from case_fit import GROUPS
from case_stress import corners, source
from film_identity import digest, verified, write_json
from independent_psd import moments, spectrum_input
from pcb_dynamic_stress import equivalent
from seeded_motion import FS, integrate, participation
from study_cases import native_case


def element_set(result, material_ids):
    grid = result.grid.cell_data
    mask = (grid['ansys_elem_type_num'] == 187) & np.isin(grid['ansys_material_type'], list(material_ids))
    ids = grid['ansys_elem_num'][mask]
    order = np.argsort(ids)
    elements = ids[order]
    materials = grid['ansys_material_type'][mask][order]
    assert np.all(np.diff(elements) > 0) and set(materials) == set(material_ids)
    return elements, materials


def early_crossing(modal, static, coordinates, limit):
    """Compare the simultaneous six-component stress at every corner for each sampled instant."""
    assert equivalent(static).max() < limit
    last_max = float(equivalent(static).max())
    for start in range(0, len(coordinates), 32):
        q = coordinates[start:start+32]
        dynamic = q @ modal.reshape(len(modal), -1)
        vm = equivalent(dynamic.reshape(len(q), *static.shape) + static[None, :, :])
        peaks = vm.max(axis=1)
        hits = np.flatnonzero(peaks >= limit)
        if hits.size:
            j = int(hits[0])
            corner = int(vm[j].argmax())
            assert start + j > 0
            before = q[j-1] if j else coordinates[start-1]
            at = q[j] @ modal[:, corner, :] + static[corner]
            prev = before @ modal[:, corner, :] + static[corner]
            prior_peak = float(peaks[j-1]) if j else last_max
            assert equivalent(prev) <= prior_peak + .01 and prior_peak < limit <= equivalent(at)
            return corner, dict(sample=start+j, time_bracket_s=[(start+j-1)/FS, (start+j)/FS],
                                previous_all_corner_max_MPa=prior_peak*1e-6, trial_MPa=float(equivalent(at))*1e-6,
                                previous_same_corner_MPa=float(equivalent(prev))*1e-6, signed_trial_components_MPa=(at*1e-6).tolist())
        last_max = float(peaks[-1])
    return None, None


def signed_cache(campaign, basis, static, modal, elements, s_nodes, mean):
    cache = ROOT/'.runtime/post'/campaign/basis['case']/'nickel'
    seal = cache/'sources.json'
    shape_file = cache/'modes.npy'
    mean_file = cache/'static.npy'
    cache.mkdir(parents=True,exist_ok=True)
    with (cache/'write.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if seal.is_file():
            saved = read(seal)
            assert saved['static_rst'] == static['rst_sha256'] and saved['basis_rst'] == basis['rst_sha256']
            verified(shape_file, saved['modal_stresses_sha256'])
            verified(mean_file, saved['static_stresses_sha256'])
            assert np.array_equal(np.load(mean_file),mean)
            tensor = np.load(shape_file, mmap_mode='r')
        else:
            tensor = np.empty((modal.nsets, len(s_nodes), 6))
            for k in range(len(freq)):
                ids, tensor[k] = corners(modal, k, 'ENS', elements, 6)
                assert np.array_equal(ids, s_nodes)
            np.save(shape_file,tensor)
            np.save(mean_file,mean)
            write_json(seal,dict(static_rst=static['rst_sha256'],basis_rst=basis['rst_sha256'],
                                 modal_stresses_sha256=digest(shape_file),static_stresses_sha256=digest(mean_file)))
    return tensor, seal


def run(variant, axis, campaign):
    static, static_dir, st = source(native_case(variant, 'static'), campaign)
    basis, mode_dir, modal = source(native_case(variant, 'basis'), campaign)
    psd, _, statistical = source(native_case(variant, 'psd_'+axis), campaign)
    fit = read(ROOT / 'validation/rigid_case_drawdown.json')
    mats = {r['native_material']:r['STEP_body'] for r in fit['records'] if r['STEP_body'] in GROUPS['nickel']}
    assert len(mats) == 6
    elements, materials = element_set(st, mats)
    for result in (modal, statistical):
        matched, assigned = element_set(result, mats)
        assert np.array_equal(elements, matched) and np.array_equal(materials, assigned)
    identities = np.repeat(elements, 4)
    corner_material = np.repeat(materials, 4)
    s_nodes, mean = corners(st, st.nsets-1, 'ENS', elements, 6)
    p_nodes, rms = corners(statistical, [3, 1], 'ENS', elements, 11)
    assert np.array_equal(s_nodes, p_nodes) and np.all(rms[:, 10] >= 0)
    # Static and perturbation tensors must refer to the same material axes at each corner.
    orient_node, orient = corners(st, st.nsets-1, 'EUL', elements, 3)
    for raw, k in [(modal, 0), (statistical, [3, 1])]:
        ids, frame = corners(raw, k, 'EUL', elements, 3)
        assert np.array_equal(ids, orient_node) and np.max(abs(frame-orient)) < 1e-5

    def archive_file(case, folder, name):
        receipt = read(ROOT / '.runtime/receipts' / campaign / case / 'archived.json')
        path = folder / name
        return path, verified(path, next(f['sha256'] for f in receipt['files'] if f['name'] == name))

    deck, deck_sha = archive_file(static['case'], static_dir, 'model.inp')
    material_cards = deck.read_text()
    for mat in mats:
        assert re.search(rf'^MP,EX,{mat},220000000000,', material_cards, re.I | re.M)
        assert re.search(rf'^MP,NUXY,{mat},0\.305,', material_cards, re.I | re.M)
        assert not re.search(rf'^TB,[^,]*,{mat},', material_cards, re.I | re.M)
    log, log_sha = archive_file(basis['case'], mode_dir, 'solve.out')
    gamma = participation(log.read_text(errors='replace'), axis)
    freq = modal.time_values
    tensor, seal = signed_cache(campaign, basis, static, modal, elements, s_nodes, mean)
    path, fk, sk, damping = spectrum_input(axis)
    cov, _ = moments(freq, gamma, fk, sk, damping, .125)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    assert eigenvalues.min() > -1e-12 * eigenvalues.max()
    factor = eigenvectors * np.sqrt(np.maximum(eigenvalues, 0))
    correlated = np.moveaxis(tensor, 0, 2) @ factor
    dynamic_rms = np.linalg.norm(equivalent(correlated.transpose(0,2,1)), axis=1)
    predicted = np.column_stack((np.linalg.norm(correlated,axis=2), dynamic_rms))
    stored = np.column_stack((rms[:, :6], rms[:, 10]))
    error = np.linalg.norm(predicted-stored, axis=0) / np.linalg.norm(stored, axis=0)
    assert error.max() < .001, error

    native_peak = psd['native_psd_fields']['scopes']['nickel']
    worst = int(np.argmax(rms[:,10]))
    assert native_peak['stress_element'] == identities[worst] and native_peak['stress_node'] == s_nodes[worst]
    assert np.isclose(native_peak['equivalent_stress_rms_Pa'], rms[worst,10])
    source_spec = read(ROOT/'validation/local_inputs.json')['damage_cont_nominal']
    trial_file = ROOT/'.runtime/local_inputs/damage_cont_nominal/config.json'
    verified(trial_file, source_spec['files']['config.json'])
    trial = float(read(trial_file)['yield_MPa'])
    indices = np.arange(int(.1*FS)+2)
    t, q, _ = integrate(freq, gamma, axis, indices)
    assert np.array_equal(t, indices/FS)
    idx, crossing = early_crossing(tensor, mean, q, trial*1e6)
    xyz = st.mesh.nodes[np.searchsorted(st.mesh.nnum, s_nodes)]*1000

    def location(i):
        return dict(element=int(identities[i]), node=int(s_nodes[i]), STEP_body=mats[int(corner_material[i])],
                    original_xyz_mm=xyz[i].tolist())

    if crossing is not None:
        crossing.update(location(idx))
    strips = {}
    for mat, tag in mats.items():
        group = np.flatnonzero(corner_material == mat)
        top = group[rms[group, 10].argmax()]
        center = next(r['STEP_centre_mm'] for r in fit['records'] if r['STEP_body'] == tag)
        strips[tag] = dict(native_material=mat, original_centre_mm=center, elements=len(group)//4,
                           max_static_equivalent_MPa=float(equivalent(mean[group]).max()*1e-6),
                           static_at_dynamic_peak_MPa=float(equivalent(mean[top])*1e-6),
                           native_equivalent_RMS_MPa=float(rms[top,10]*1e-6), peak=location(top))
    out = ROOT / 'validation/nickel_vibration' / (variant+'_'+axis+'.json')
    write_json(out, dict(variant=variant, axis=axis, campaign=campaign, static_rst=static['rst_sha256'],
        modal_rst=basis['rst_sha256'], psd_rst=psd['rst_sha256'], static_deck=deck_sha, modal_listing=log_sha,
        spectrum_deck=digest(path), strip_elements=len(elements), element_corner_count=len(s_nodes), strips=strips,
        RMS_relative_field_norm_errors=error.tolist(), trial_reference_config_sha256=digest(trial_file),
        trial_reference_yield_MPa=trial, independently_evaluated_window_s=[float(t[0]), float(t[-1])],
        first_sample_above_reference=crossing, signed_tensor_cache_sha256=digest(seal), physical_scope='Native linear statistical stress at the six strips. '
        'The independent early waveform adds the locked signed tensor and signed modal tensors before computing von Mises. '
        'The only reference yield stress is the assumed input to the historical local damage model.'))
    print(variant, axis, 'RMS MPa', rms[worst,10]*1e-6, 'first trial crossing', crossing, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant')
    p.add_argument('axis', choices='XYZ')
    p.add_argument('--campaign', default='nov08_01')
    args = p.parse_args()
    run(args.variant, args.axis, args.campaign)
