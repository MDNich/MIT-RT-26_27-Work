"""Compare changes in the maximum principal elastic strain at the same PCB surface corners."""
import re

import numpy as np
from scipy.spatial import cKDTree
from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from native_rst import read_rst
from pcb_installation import maximum_principal_strain, signed_corners


def surface_fields(paths, sets, heights, modulus, nu):
    blocks = []
    ids = []
    errors = []
    for path in paths:
        result = read_rst(path)
        grid = result.grid.cell_data
        elements = np.sort(grid['ansys_elem_num'][grid['ansys_material_type'] == 208])
        if not len(elements):
            continue
        ids.extend(elements)
        station_fields = []
        for i, station in enumerate(sets):
            en, nodes, elastic = signed_corners(result, elements, station, 'EEL', 7)
            se, sn, stress = signed_corners(result, elements, station, 'ENS', 6)
            assert np.array_equal(en, se) and np.array_equal(nodes, sn)
            if i == 0:
                xyz = result.mesh.nodes[positions(result.mesh.nnum, nodes)]
                faces = np.isclose(xyz[:, 2, None], heights, atol=1.e-9, rtol=0)
                assert np.all(faces.sum(axis=1) <= 1)
                selected = faces.any(axis=1)
                labels = np.column_stack([en, nodes])[selected]
            else:
                assert np.array_equal(labels, np.column_stack([en, nodes])[selected])
            values = elastic[selected, :6]
            s = stress[selected].astype(float)
            predicted = s * (1 + nu) / modulus
            predicted[:, :3] -= nu * s[:, :3].sum(axis=1)[:, None] / modulus
            predicted[:, 3:] *= 2
            errors.append(np.linalg.norm(predicted-values) / np.linalg.norm(values))
            station_fields.append(1.e6 * maximum_principal_strain(values))
        blocks.append((labels, xyz[selected], np.column_stack(station_fields)))
    assert len(ids) == len(set(ids)) == 39014 and max(errors) < 1.e-4
    keys, xyz, values = (np.concatenate(v) for v in zip(*blocks, strict=True))
    ix = np.argsort(keys[:, 0], kind='stable')
    return keys[ix], xyz[ix], values[ix], float(max(errors))


def compare():
    paired_path = ROOT/'validation/pcb_installation/flush_pair_step3_substep6.json'
    matched = read(paired_path)
    supported = [row for row in matched['sets'] if any(np.isclose(row['travel_mm'], [0., .65, .80]))]
    assert len(supported) == 3 and np.allclose([v['travel_mm'] for v in supported], [0., .65, .80])
    nylon_path = ROOT/'validation/pcb_installation/flush_nylon_surf1_static.json'
    nylon = read(nylon_path)
    campaign = matched['campaign']
    rt = ROOT/'.runtime'
    assert nylon['campaign'] == campaign
    src = rt/'archive'/campaign/nylon['case']/'file.rst'
    verified(src, nylon['rst_sha256'])
    heights = np.array([nylon['history'][0]['surfaces'][f]['xyz_mm'][2] for f in ('low_Z', 'high_Z')]) * .001
    aluminium = 'flush_aluminium_surf1_static'
    stamp = 'step3_substep6'
    base = rt/'partition_snapshots'/campaign/aluminium/stamp
    manifest = read(base/'receipts.json')
    assert manifest['case'] == aluminium and manifest['campaign'] == campaign
    verified(base/'receipts.json', matched['aluminium_partition_sha256'])
    part_names = [f'file{i}.rst' for i in range(manifest['cores'])]
    for name in part_names:
        verified(base/name, manifest['files'][name]['SHA256'])
    assert np.isclose(maximum_principal_strain(np.array([[0., 0., 0., 2., 0., 0.]]))[0], 1.)
    geometry = read_rst(src)
    tied = []
    input_hashes = [nylon['input_sha256'], manifest['model_sha256']]
    for case, sha in zip([nylon['case'], aluminium], input_hashes, strict=True):
        deck = rt/'inputs'/case/'model.inp'
        verified(deck, sha)
        ties = re.findall(rb'(?im)^CERIG,(96010[1-4]),(\d+),UXYZ', deck.read_bytes())
        assert len({int(p) for p, _ in ties}) == 4
        tied.append(sorted((int(p),int(n)) for p,n in ties))
    assert tied[0] == tied[1]
    tied_nodes = np.unique([n for _,n in tied[0]])
    tied_xy = geometry.mesh.nodes[positions(geometry.mesh.nnum, tied_nodes), :2]
    tree = cKDTree(1000*tied_xy)
    output = {}
    for variant, paths in [('nylon', [src]), ('aluminium', [base/n for n in part_names])]:
        sets = [r[variant+'_set'] for r in supported]
        labels, xyz, values, error = surface_fields(paths, sets, heights, nylon['modulus_Pa'], nylon['Poisson_ratio'])
        if variant == 'nylon':
            reference_labels, reference_xyz = labels, xyz
        else:
            assert np.array_equal(labels, reference_labels) and np.array_equal(xyz, reference_xyz)
        distance = tree.query(1000*xyz[:, :2])[0]
        rows = []
        for i, station in enumerate(sets):
            faces = {}
            for key, height in zip(('low_Z','high_Z'), heights, strict=True):
                selection = np.flatnonzero(np.isclose(xyz[:, 2], height, rtol=0, atol=1.e-9))
                assert len(selection) == nylon['history'][0]['surfaces'][key]['unaveraged_corners']
                peak_total = float(values[selection, i].max())
                if variant == 'nylon':
                    existing, = [v for v in nylon['history'] if v['native_set'] == station]
                    assert np.isclose(peak_total,existing['surfaces'][key]['peak_principal_tensile_microstrain'],atol=1.e-7,rtol=1.e-10)
                if i == 0:
                    faces[key] = dict(total_max_microstrain=peak_total, largest_corner_increase_microstrain=0.,
                                      beyond_2mm_largest_increase_microstrain=0.)
                    continue
                delta = values[selection, i] - values[selection, 0]
                j = selection[np.argmax(delta)]
                outside = selection[distance[selection] >= 2.]
                distant = outside[np.argmax(values[outside,i] - values[outside,0])]
                faces[key] = dict(distance_from_tied_PCB_patch_mm=float(distance[j]),
                                  beyond_2mm_largest_increase_microstrain=float(values[distant,i]-values[distant,0]),
                                  beyond_2mm_element=int(labels[distant,0]),beyond_2mm_node=int(labels[distant,1]),
                                  total_max_microstrain=peak_total, largest_corner_increase_microstrain=float(delta.max()),
                                  station_microstrain_at_corner=float(values[j,i]), lock_microstrain_at_corner=float(values[j,0]),
                                  element=int(labels[j,0]),node=int(labels[j,1]),original_xyz_mm=(1000*xyz[j]).tolist())
            rows.append(dict(set=station,travel_mm=supported[i]['travel_mm'],faces=faces))
        output[variant] = dict(max_stress_strain_relative_error=error,history=rows)
    write_json(ROOT/'validation/pcb_installation/flush_surface_strain_comparison.json', dict(
        case_comparison_sha256=digest(paired_path),nylon_PCB_control_sha256=digest(nylon_path),campaign=campaign,
        nylon_combined_rst_sha256=nylon['rst_sha256'],aluminium_partitions_sha256=digest(base/'receipts.json'),
        surface_corner_records=len(labels),tied_PCB_nodes=len(tied_nodes),results=output,
        scope='Maximum principal elastic strain evaluated at unaveraged PCB surface corners. Each change subtracts the '
              'same corner’s value at six-bolt lock. The reported increase is the maximum of those differences on the '
              'given face. The 2 mm exclusion uses in-plane distance to the nearest tied PCB bearing node. The PCB uses the inherited isotropic elastic model. These are not solder-joint failure limits.'))
    for k,v in output.items():
        print(k,v['history'][-1], flush=True)


if __name__ == '__main__':
    compare()
