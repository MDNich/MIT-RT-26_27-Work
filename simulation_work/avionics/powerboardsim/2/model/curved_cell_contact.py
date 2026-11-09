"""Recheck raised-case clearances at two signed base-X states on curved native element surfaces."""

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from film_identity import digest, verified, write_json
from native_rst import read_rst
from seeded_motion import FS, integrate, participation


def contact_solids(rst):
    g = rst.quadgrid
    solid = np.isin(g.cell_data['ansys_elem_type_num'], [185, 186, 187])
    return [g.extract_cells(solid & np.isin(g.cell_data['ansys_material_type'], mats))
              for mats in ([850], [176, 187, 191])]


def set_coordinates(groups, ids, coordinates_m):
    for group in groups:
        nodes = group.point_data['ansys_node_num']
        select = np.searchsorted(ids, nodes)
        assert np.array_equal(ids[select], nodes)
        group.points = coordinates_m[select]
        group.point_data['coordinates'] = group.points.astype(np.float64)


def curved_skins(groups, level):
    skins = [group.extract_surface(nonlinear_subdivision=level, algorithm='dataset_surface').triangulate()
             for group in groups]
    for surface in skins:
        surface.points = surface.point_data['coordinates']
        assert surface.n_open_edges == 0
    return skins


def sampled_clearance(groups, ids, coordinates_m, levels):
    set_coordinates(groups, ids, coordinates_m)
    records = {}
    for level in levels:
        cap, cells = curved_skins(groups, level)
        _, count = cap.collision(cells, contact_mode=1, box_tolerance=0., cell_tolerance=0.)
        sd = cells.compute_implicit_distance(cap).point_data['implicit_distance'] * 1000
        assert np.isfinite(sd).all()
        records[level] = dict(PLA_triangles=cap.n_cells, cell_triangles=cells.n_cells,
                              intersect=bool(count), minimum_signed_vertex_gap_mm=float(sd.min()))
    return records


def run(variant, campaign):
    basis = variant + '_basis'
    vault = ROOT / '.runtime/archive' / campaign / basis
    proof = read(ROOT / 'validation/global' / f'{basis}.json')
    peak_path = ROOT / 'validation/peak_contact' / f'{variant}.json'
    search_path = ROOT / 'validation/clearance_rms' / f'{basis}.json'
    peak, search = read(peak_path), read(search_path)
    assert campaign == proof['campaign'] == peak['campaign'] == search['campaign']
    assert proof['rst_sha256'] == peak['basis_sha256'] == search['rst_sha256']
    verified(vault / 'file.rst', proof['rst_sha256'])
    ledger = read(ROOT / '.runtime/receipts' / campaign / basis / 'archived.json')
    verified(vault / 'solve.out', next(f['sha256'] for f in ledger['files'] if f['name'] == 'solve.out'))
    rst = read_rst(vault / 'file.rst')
    approach = search['scopes']['cells']['directions']['X']['seed_screen']
    times = np.array([approach['most_approached_sample_s'], peak['time_s']])
    indices = np.rint(times * FS).astype(int)
    log = (vault / 'solve.out').read_text(errors='replace')
    actual, q, _ = integrate(rst.time_values, participation(log, 'X'), 'X', indices)
    assert np.array_equal(actual, times)
    groups = contact_solids(rst)
    ids = np.unique(np.concatenate([group.point_data['ansys_node_num'] for group in groups]))
    xyz = rst.mesh.nodes[np.searchsorted(rst.mesh.nnum, ids)]
    assert np.array_equal(rst.mesh.nnum[np.searchsorted(rst.mesh.nnum, ids)], ids)
    displacement = np.zeros((len(q), len(ids), 3))
    for k, src in field_files(basis, campaign, proof['rst_sha256'], rst.nsets).items():
        nodes = np.fromfile(src.with_suffix('.ids'), '<i4')
        values = np.fromfile(src.with_suffix('.u'), '<f8').reshape(-1, 3)
        order = np.argsort(nodes)
        select = order[np.searchsorted(nodes[order], ids)]
        assert np.array_equal(nodes[select], ids)
        displacement += q[:, k-1, None, None] * values[select]

    records = {}
    for name, move in zip(('tightened', 'largest_approach', 'peak_layer_tension'),
                          (np.zeros_like(displacement[0]), *displacement), strict=True):
        records[name] = sampled_clearance(groups, ids, xyz+move, (1,2,3))
        print(variant, name, records[name], flush=True)
    assert not any(r['intersect'] for r in records['tightened'].values())
    for name, old in [('largest_approach', approach['maximum_target_vertex_depth_in_PLA_mm']),
                      ('peak_layer_tension', peak['peak']['deepest_sampled_cell_vertex_mm'])]:
        # First reproduce the existing midside-node comparison before interpreting finer skins.
        assert abs(records[name][1]['minimum_signed_vertex_gap_mm'] + old) < .0001
    write_json(ROOT / 'validation/curved_contact' / f'{variant}.json', dict(
        case=variant, campaign=campaign, basis_RST_sha256=proof['rst_sha256'],
        approach_audit_sha256=digest(search_path), peak_tension_audit_sha256=digest(peak_path),
        times_s=dict(largest_approach=float(times[0]), peak_layer_tension=float(times[1])), states=records,
        scope='Independent signed base-X history on the tightened native geometry. Each level subdivides the '
              'same deformed quadratic elements. Signed distances sample cell vertices against the closed PLA '
              'surface. Negative values and a triangle intersection indicate loss of the open-gap assumption.'))


def native_peak(variant,campaign,axis):
    """Check the three cell skins at the maximum native layer stress in a nine-second base history."""
    from audit_motion import selected_native_coordinates
    from case_stress import source
    from motion_surface import displacement_basis
    key=variant+'_basis'
    modal,_,rst=source(key,campaign)
    case=variant+'_motion_'+axis
    proof_path=ROOT/'validation/motion'/f'{case}.json'
    proof=read(proof_path)
    assert proof['case']==case and proof['campaign']==campaign and proof['basis_rst_sha256']==modal['rst_sha256']
    stress=proof['native_seeded_PLA_layer_stress']
    search_path=ROOT/'validation/clearance_rms'/f'{key}.json'
    search=read(search_path)
    assert search['rst_sha256']==modal['rst_sha256'] and search['campaign']==campaign
    approach=search['scopes']['cells']['directions'][axis]['seed_screen']
    spectrum=variant+f'_psd_{axis}_private1'
    stress_path=ROOT/'validation/pla_stress'/f'{spectrum}.json'
    stress_proof=read(stress_path)
    assert stress_proof['basis_sha256']==modal['rst_sha256'] and stress_proof['campaign']==campaign
    expected=stress_proof['independent_signed_waveform']
    assert (expected['critical_corner_node'],expected['critical_element'])==(stress['corner_node'],stress['element'])
    requested={'independent_approach_sample':approach['most_approached_sample_s'],
               'independent_stress_peak_sample':expected['maximum']['time_s'],
               'native_stress_peak_sample':stress['peak_time_s']}
    times=np.unique(list(requested.values()))
    samples=np.rint(times*FS).astype(int)
    assert np.array_equal(times,samples/FS)
    mcf=ROOT/'.runtime/archive'/campaign/case/'file.mcf'
    verified(mcf,proof['mcf_sha256'])
    q=selected_native_coordinates(mcf,rst.time_values,samples)
    trace=ROOT/'.runtime/post'/campaign/spectrum/'PLA_critical_history.npz'
    verified(trace,stress_proof['independent_signed_waveform']['cache_sha256'])
    with np.load(trace) as fields:
        recovered=q@fields['modal_Z_Pa']*1.e-6+float(fields['mean_MPa'])
    index=int(np.searchsorted(times,stress['peak_time_s']))
    assert np.isclose(recovered[index],stress['peak_tension_MPa'],rtol=1.e-11)
    cover,cells=contact_solids(rst)
    solids=[cover]+[cells.extract_cells(cells.cell_data['ansys_material_type']==mat) for mat in (176,191,187)]
    ids=np.unique(np.concatenate([solid.point_data['ansys_node_num'] for solid in solids]))
    pos=np.searchsorted(rst.mesh.nnum,ids)
    assert np.array_equal(ids,rst.mesh.nnum[pos])
    fields=field_files(key,campaign,modal['rst_sha256'],rst.nsets)
    modes=displacement_basis(rst,ids,fields)
    xyz=rst.mesh.nodes[pos]
    states={}
    for i,sample in enumerate(samples):
        deformed=xyz+(q[i]@modes.reshape(len(modes),-1)).reshape(xyz.shape)
        measures={name:sampled_clearance([cover,solid],ids,deformed,(2,3)) for name,solid in
                  zip(('left','centre','right'),solids[1:],strict=True)}
        assert all(row[2]['intersect']==row[3]['intersect'] for row in measures.values())
        states[int(sample)]=dict(time_s=float(times[i]),layer_tension_MPa=float(recovered[i]),cells=measures)
    out=ROOT/'validation/curved_contact'/f'{variant}_native_{axis}.json'
    write_json(out,dict(variant=variant,base_axis=axis,campaign=campaign,native_motion_sha256=digest(proof_path),
        native_MCF_sha256=proof['mcf_sha256'],basis_rst_sha256=modal['rst_sha256'],
        independent_approach_sha256=digest(search_path),independent_stress_sha256=digest(stress_path),stress_field_sha256=digest(trace),
        sampling_Hz=FS,sample_times_s=requested,stress_node=stress['corner_node'],stress_element=stress['element'],
        peak_native_layer_tension_MPa=stress['peak_tension_MPa'],states=states,
        scope='Closed cell and case skins at selected native MCF stations. Peak refers to the monitored printed-layer '
              'stress corner over the nine-second record. Native modal superposition holds the contact state fixed.'))
    print(out.name,stress['peak_tension_MPa'],stress['peak_time_s'],flush=True)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=['stand3_nylon','stand3_aluminium'])
    parser.add_argument('campaign')
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--axis',choices=list('XYZ'),default='X')
    args=parser.parse_args()
    if args.native:
        native_peak(args.variant,args.campaign,args.axis)
    elif args.axis!='X':
        parser.error('The original independent curved-skin controls use base X.')
    else:
        run(args.variant,args.campaign)
