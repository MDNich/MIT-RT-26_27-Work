"""Compare the changes in battery spacing and the motions that produce them."""
import numpy as np

from audit_local import ROOT, read
from film_identity import digest, write_json
from report_plot import plt
from stage_snug_fit import AUDIT

BRANCHES = ('bare', 'snug125_nylon', 'snug125_aluminium')
FINE = 'snug125_nylon_mesh15'


def compare():
    records = {}
    sources = {}
    for variant in (*BRANCHES, FINE):
        for method in (('exact',) if variant == FINE else ('native', 'exact')):
            path = AUDIT/f'{variant}_cell_spacing_{method}.json'
            record = read(path)
            assert record['variant'] == variant and record['method'] == method
            sources[path.name] = digest(path)
            records[variant, method] = record
    controls = {}
    for axis in 'XYZ':
        drive = records['bare', 'native']['axes'][axis]['input_sha256']
        worst_exact = worst_cutoff = worst_distance = 0.
        for (variant, method), record in records.items():
            row = record['axes'][axis]
            assert row['input_sha256'] == drive and row['max_nodal_reconstruction_error_um'] < 1e-6
            for pair, values in row['pairs'].items():
                for direction in ('approach', 'opening'):
                    key = 'peak_' + direction
                    full = values[key+'_um']
                    assert full > 0
                    worst_cutoff = max(worst_cutoff, abs(values[key+'_3500Hz_um']/full - 1))
                    if method == 'native':
                        exact = records[variant, 'exact']['axes'][axis]['pairs'][pair]
                        assert record['basis_rst_sha256'] == records[variant, 'exact']['basis_rst_sha256']
                        worst_exact = max(worst_exact, abs(exact[key+'_um']/full - 1))
                worst_distance = max(worst_distance, values['max_axial_minus_distance_change_um'])
            peak = row['at_left_middle_peak']
            assert abs(peak['left_relative_to_clamps_um'] - peak['middle_relative_to_left_clamps_um']
                       - row['pairs']['left_middle']['peak_approach_um']) < 1e-9
        controls[axis] = dict(max_native_exact_difference_pct=100*worst_exact,
                              max_3500_to_4000Hz_difference_pct=100*worst_cutoff,
                              largest_difference_from_3D_distance_um=worst_distance)
    write_json(AUDIT/'cell_spacing_comparison.json', dict(inputs=sources, checks=controls))
    print(controls)
    return records


def draw(records):
    colours = ['#08357E', '#3C78D8', '#38761D']
    labels = ['Bare', 'Nylon', 'Aluminium']
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.8, 2.65), layout='constrained',
                                 gridspec_kw={'width_ratios': [1, 1.12]})
    for j, (variant, name, colour) in enumerate(zip(BRANCHES, labels, colours, strict=True)):
        row = records[variant, 'native']['axes']['X']
        values = [row['pairs'][p]['peak_approach_um'] for p in ('left_middle', 'middle_right')]
        x = np.arange(2) + (j-1)*.25
        bars = ax.bar(x, values, width=.23, color=colour, label=name)
        ax.bar_label(bars, fmt='%.0f', fontsize=8, padding=2)
        left, middle = [row['at_left_middle_peak'][key] for key in
                        ('left_relative_to_clamps_um', 'middle_relative_to_left_clamps_um')]
        y = 2-j
        bx.plot([middle, left], [y, y], lw=1.8, color=colour)
        bx.scatter([middle], [y], marker='o', color='white', edgecolors=colour, linewidths=1.5,
                   zorder=3, label='Middle cell' if j == 0 else None)
        bx.scatter([left], [y], marker='s', color=colour, zorder=3, label='Left cell' if j == 0 else None)
        for value in (left, middle):
            bx.annotate(f'{value:+.1f}', (value, y), xytext=(0, 7), textcoords='offset points',
                        ha='center', fontsize=8, color=colour)
    ax.set(xticks=[0, 1], xticklabels=['Left--middle', 'Middle--right'], ylim=(0, 200),
           ylabel=r'Peak approach [$\mu$m]', title='Cell pairs under base X')
    ax.legend(frameon=False, fontsize=7.5, loc='upper left')
    bx.set(yticks=[2, 1, 0], yticklabels=labels, ylim=(-.65, 2.6), xlim=(-92, 54),
           xlabel=r'Motion from left clamps [$\mu$m]', title='At closest left--middle approach')
    bx.axvline(0, color='#777777', lw=.65, zorder=0)
    bx.legend(frameon=False, ncols=2, fontsize=7, loc='lower center', handlelength=1)
    for panel, axis in ((ax, 'y'), (bx, 'x')):
        panel.spines[['top', 'right']].set_visible(False)
        panel.grid(axis=axis, alpha=.14)
        panel.set_axisbelow(True)
    fig.savefig(ROOT/'docs/figures/snug-cell-spacing.pdf', metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


if __name__ == '__main__':
    draw(compare())
