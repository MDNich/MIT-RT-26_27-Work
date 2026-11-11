"""Plot only closed, audited reverse pulls against the matching bare fixture."""
import numpy as np

from audit_local import ROOT, read
from compare_pull import series
from film_identity import digest, verified, write_json
from report_plot import plt
from stage_snug_fit import AUDIT


def common_station(records, bare):
    """Use an exact saved travel shared by both mounts, below each deck's screens."""
    if len(records) != 2:
        return None
    stations = [{round(-r['ux_mm'], 9): r for r in item['native_points']
                 if r['set'] <= item['last_screened_set']} for item in records]
    magnitude = max(set(stations[0]) & set(stations[1]))
    baseline, = [r for r in bare if abs(r['ux_mm'] + magnitude) < 1e-8]
    models = []
    for item, rows in zip(records, stations, strict=True):
        row = rows[magnitude]
        path = ROOT / 'validation/pull_material' / (item['case'] + '.json')
        comparison = read(AUDIT / (item['case'] + '_comparison.json'))
        verified(path, comparison['print_material_sha256'])
        material = read(path)
        state, = [s for s in material['history'] if s['native_set'] == row['set']]
        assert abs(state['travel_mm'] - row['ux_mm']) < 1e-8
        assert abs(state['cell_force_N'] - row['cell_force_N']) < 1e-5
        fractions = {k: state['all_' + k] / v for k, v in material['reference_properties'].items()}
        assert max(fractions.values()) < 1
        models.append(dict(case=item['case'], native=row, material_sha256=digest(path),
                           material_state=state, printed_reference_fractions=fractions))
    return dict(travel_magnitude_mm=magnitude, bare=baseline, models=models,
                scope='Exact shared saved travel, not an interpolated station. Parent-mesh material screens apply.')


def plot():
    bare_name = 'bare_lateral_friction_locked_minus'
    bare_proof, bare = series(bare_name)
    records = []
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(8.1, 2.8), layout='constrained',
                               gridspec_kw={'width_ratios': [1.45, 1]})
    ax.plot([-r['ux_mm'] for r in bare], [-r['cell_force_N'] for r in bare],
            '.-', color='#08357E', ms=3, lw=1.4, label='Bare')
    bx.plot(.5, 0, 'o', color='#08357E', ms=5)
    labels = ['Bare']
    for material, label, color in [('nylon', 'Nylon', '#38761D'),
                                    ('aluminium', 'Aluminium', '#7A0101')]:
        case = f'snug125_{material}_lateral_friction_locked_minus_pin1_m15'
        path = AUDIT / (case + '_comparison.json')
        if not path.exists():
            continue
        item = read(path)
        assert item['case'] == case and item['bare'] == bare_name
        assert item['bare_rst_sha256'] == bare_proof['rst_sha256']
        verdict = ROOT / 'validation' / ('local' if item['full_numerical_path'] else 'partial_local') / (case + '.json')
        verified(verdict, item['fixture_sha256'])
        proof, rows = series(case, proof_path=verdict)
        assert proof['rst_sha256'] == item['native_rst_sha256']
        assert 'refined_tab_crossing' not in item  # Forward refinement is not transferable.
        end = item['equal_travel']['cased']['set']
        screened = [r for r in rows if r['set'] <= end]
        later = [r for r in rows if r['set'] >= end]
        ax.plot([-r['ux_mm'] for r in screened], [-r['cell_force_N'] for r in screened],
                '.-', color=color, ms=4, lw=1.5, label=label)
        if len(later) > 1:
            ax.plot([-r['ux_mm'] for r in later], [-r['cell_force_N'] for r in later],
                    '--', color=color, alpha=.45, lw=1.2)
        equal = item['equal_load']
        if equal:
            match = equal['cased']
            x = abs(match['travel_mm'])
            lo, hi = sorted(abs(v) for v in match['native_travel_mm'])
            y = len(labels)
            labels.append(label)
            bx.errorbar(x, y, xerr=np.array([[x-lo], [hi-x]]), fmt='D',
                        color=color, capsize=4, ms=5)
            bx.annotate(f'{x:.2f} mm', (x, y), xytext=(0, -12), textcoords='offset points',
                        ha='center', va='top', fontsize=9, color=color)
        records.append(dict(case=case, comparison_sha256=digest(path),
                            input_sha256=item['input_sha256'], rst_sha256=item['native_rst_sha256'],
                            native_points=rows, last_screened_set=end,
                            equal_load=equal, equal_travel=item['equal_travel'],
                            moving_cell_contact_bracket=item['moving_cell_contact_bracket']))
    assert records, 'No closed reverse comparison is available'
    ax.set(xlabel='Reverse cell travel [mm]', ylabel='Applied force magnitude [N]',
           xlim=(0, .51), title='Away from the neighbouring cells')
    ax.legend(frameon=False, fontsize=9)
    target = abs(bare[-1]['cell_force_N'])
    bx.annotate('0.50 mm', (.5, 0), xytext=(0, -12), textcoords='offset points',
                ha='center', va='top', fontsize=9, color='#08357E')
    bx.set(xlabel='Reverse cell travel [mm]', title=f'At the same {target:.1f} N load',
           xlim=(0, .56), ylim=(-.5, len(labels)-.35), yticks=range(len(labels)),
           yticklabels=labels)
    bx.invert_yaxis()
    for axis in (ax, bx):
        axis.spines[['top', 'right']].set_visible(False)
        axis.grid(alpha=.15)
        axis.title.set(color='#08357E', fontsize=11)
    fig.savefig(ROOT / 'docs/figures/snug-reverse-pull.pdf',
                metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)
    write_json(AUDIT / 'reverse_pull_plot.json', dict(
        bare_case=bare_name, bare_rst_sha256=bare_proof['rst_sha256'], models=records,
        common_screened_native_station=common_station(records, bare),
        scope='Negative-X local fixtures. Solid curves stop at the last native material/contact-screened station; '
              'dashes show numerical continuation. Parent-mesh coupon screens are not allowable loads or '
              'converged fracture predictions. Diamonds interpolate only between adjacent saved equilibria.'))


if __name__ == '__main__':
    plot()
