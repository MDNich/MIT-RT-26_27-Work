"""Compare nickel plastic strain at the same cell travel and pull force in the nominal damage fixtures."""
from report_plot import plt
import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read, table
from compare_pull_laws import at_first_crossing, loading_curve
from film_identity import verified, write_json


def strain_history(branch):
    load, source = loading_curve(branch, True)
    case = source['case']
    folder = ROOT/'.runtime/archive'/source['campaign']/case
    receipts = ROOT/'.runtime/receipts'/source['campaign']/case
    hashes = {row['name']: row['sha256'] for row in read(receipts/'archived.json')['files']}
    footprint = read(ROOT/'validation/damage_footprint'/(case+'.json'))
    assert footprint['mesh_sha256'] == source['mesh_sha256'] and footprint['rst_sha256'] == source['rst_sha256']
    assert footprint['history_sha256'] == hashes['history.csv']
    verified(folder/'history.csv', hashes['history.csv'])
    history = table(folder/'history.csv')
    r = reader.read_binary(folder/'tear.rst')
    mesh = read(ROOT/'.runtime/local_inputs/damage_cont_nominal/mesh.json')
    regions = np.array(mesh['region'])
    elements = np.arange(1, len(regions)+1)
    assert len(elements) == 2304
    grid = r.grid.cell_data
    nickel = grid['NICKEL'].astype(bool)
    assert (grid['ansys_elem_type_num'][nickel] == 181).all()
    assert np.array_equal(np.sort(grid['ansys_elem_num'][nickel]), elements)
    # The original post deck requests the maximum element-average EPEQ across top,
    # middle and bottom, and also exports every element's bottom value individually.
    states = []
    for point in load[load['ux_mm'] > 0]:
        k = int(point['native_set'])-1
        row, = history[np.isclose(history['time'], point['time'], atol=1e-8, rtol=0)]
        assert abs(row['ux_mm'] - point['ux_mm']) < 1e-7
        name = f"damage_{int(row['step'])}.csv"
        verified(folder/name, hashes[name])
        fields = table(folder/name)
        assert np.array_equal(fields['element'], elements)
        ids, values, _ = r.element_solution_data(k, 'ENL')
        idx = np.searchsorted(ids, elements)
        assert np.array_equal(ids[idx], elements)
        records = np.stack([values[i] for i in idx])
        assert records.shape == (len(elements), 120)
        # Three stored sections, four shell nodes, ten nonlinear quantities per node.
        sections = records.reshape(-1, 3, 4, 10)[:, :, :, 3].mean(axis=2, dtype=float)
        assert np.isfinite(sections).all() and sections.min() >= -1e-8
        np.testing.assert_allclose(sections[:, 0], fields['peeq_bot'], atol=2e-10, rtol=2e-7)
        element, section = np.unravel_index(np.argmax(sections), sections.shape)
        peak = float(sections[element, section])
        assert np.isclose(peak, row['peeq'], atol=2e-10, rtol=2e-7)
        states.append(dict(native_set=k+1, travel_mm=float(point['ux_mm']), force_N=float(point['cell_fx_N']),
                           max_equivalent_plastic_strain=peak, peak_element=int(elements[element]),
                           peak_region=str(regions[element]), bottom_at_peak=float(sections[element, 0])))
    return load, source, states


def compare(histories):
    assert len({source['mesh_sha256'] for _, source, _ in histories.values()}) == 1
    # Choose the largest saved displacement within the common material/contact range
    # and the original 0.5 mm side-pull test. Use a matching bare force at that point.
    common = set.intersection(*[{round(s['travel_mm'], 8) for s in states if s['travel_mm'] <= .50000001}
                                for _, _, states in histories.values()])
    travel = max(common)
    stations = {}
    for branch, (rows, _, states) in histories.items():
        station, = [s for s in states if abs(s['travel_mm'] - travel) < 1e-8]
        row, = rows[rows['native_set'] == station['native_set']]
        screws = -float(row['screw_support_N_x']) if branch != 'bare' else 0.
        neighbour = -float(row['neighbor_support_N_x']) if branch != 'bare' else 0.
        stations[branch] = dict(station, screw_path_N=screws, neighbour_path_N=neighbour,
                                original_clamps_N=station['force_N']-screws-neighbour-float(row['force_N_x']))
    force = stations['bare']['force_N']
    checks = {}
    for branch, (rows, source, states) in histories.items():
        crossing = at_first_crossing(rows, 'cell_fx_N', force)
        by_set = {s['native_set']: s for s in states}
        checks[branch] = dict(source=source, pull_stations_checked=len(states), at_common_travel=stations[branch],
                              at_common_force=crossing, strain_at_adjacent_force_stations=[
                                  by_set[point['native_set']] for point in crossing['bracket']])
    return dict(common_travel_mm=travel, common_force_N=force, fixtures=checks,
                scope='Nominal multilinear nickel, positive edge-cell pull. EPEQ is the maximum of the '
                      'element-averaged section values. Force brackets preserve the actual neighbouring states.')


def draw(histories, result, path):
    travel = result['common_travel_mm']
    force = result['common_force_N']
    fig, (left, right) = plt.subplots(1, 2, figsize=(8.1, 3.05), layout='constrained', sharey=True)
    styles = {'bare': ('Bare', '#08357E', 'o'), 'stand3_nylon': ('Nylon screws', '#3C78D8', 's'),
              'stand3_aluminium': ('Aluminium screws', '#38761D', '^')}
    for branch, (_, _, states) in histories.items():
        label, colour, marker = styles[branch]
        upper = result['fixtures'][branch]['at_common_force']['bracket'][-1]['native_set']
        for ax, field, keep in [(left, 'travel_mm', [s for s in states if s['travel_mm'] <= travel+1e-8]),
                                (right, 'force_N', [s for s in states if s['native_set'] <= upper])]:
            ax.plot([s[field] for s in keep], [100*s['max_equivalent_plastic_strain'] for s in keep],
                    color=colour, marker=marker, markersize=3.5, linewidth=1.25, label=label)
    left.set(title='Prescribed cell travel', xlabel='Cell travel [mm]', ylabel='Peak nickel plastic strain [\\%]')
    right.set(title='Applied cell force', xlabel='Lateral force [N]')
    right.axvline(force, linestyle='--', color='#7A0101', linewidth=1.1, label=f'{force:.2f} N')
    right.legend(loc='upper left', frameon=False, fontsize=8)
    for ax in (left, right):
        ax.grid(axis='y', alpha=.2)
        ax.spines[['top','right']].set_visible(False)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
    fig.savefig(path, metadata={'CreationDate':None, 'ModDate':None})
    plt.close(fig)


if __name__ == '__main__':
    paths = {branch: strain_history(branch) for branch in ('bare','stand3_nylon','stand3_aluminium')}
    result = compare(paths)
    draw(paths, result, ROOT/'docs/figures/raised-nickel-damage-strain.pdf')
    write_json(ROOT/'validation/pull_laws/raised_nickel_strain.json', result)
