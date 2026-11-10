"""Plot the native base-Z startup crossings on the board's locked-contact mode shapes."""
from audit_local import ROOT, read
from report_plot import plt
from stage_snug_fit import AUDIT


def draw():
    result = read(AUDIT / 'startup_outer_comparison.json')['variants']
    fig, ax = plt.subplots(figsize=(7.65, 1.95), layout='constrained')
    for row, (screw, colour) in enumerate((('aluminium', '#38761D'), ('nylon', '#3C78D8'))):
        ax.hlines(row, 0, 51, color='#dddddd', lw=1)
        branch = result[screw]['methods']['native']
        for index, side in enumerate(branch['order']):
            lo, hi = branch['cells'][side]['time_interval_ms']
            middle = (lo + hi) / 2
            ax.plot(middle, row, marker='o' if side == 'left' else 'D', color=colour, ms=5)
            ax.annotate(f'{side.capitalize()} {middle:.1f} ms', (middle, row),
                        xytext=(-3 if index == 0 else 3, 6 if row == 0 else 5),
                        textcoords='offset points', fontsize=9,
                        ha='right' if index == 0 else 'left', va='bottom')
    reserve = read(AUDIT / 'nylon_pocket_preload.json')['axes']['Z']['integrations']['independent']
    limit = 1000 * reserve['sign_independent_latest_sample'] / result['nylon']['methods']['exact']['sample_rate_Hz']
    ax.plot([0, limit], [1, 1], color='#5A43A0', lw=2.5, solid_capstyle='butt')
    ax.plot(limit, 1, marker='|', color='#5A43A0', ms=9)
    ax.text(limit / 2, .88, f'Middle-pocket pressure\nchanges by {limit:.1f} ms',
            color='#5A43A0', ha='center', va='top', fontsize=8)
    ax.set(xlim=(0, 53), ylim=(-.25, 1.47), yticks=(0, 1), yticklabels=('Aluminium', 'Nylon'),
           xlabel='Time after base-Z vibration starts [ms]')
    ax.spines[['left', 'top', 'right']].set_visible(False)
    ax.tick_params(axis='y', length=0)
    fig.savefig(ROOT / 'docs/figures/snug-outer-startup.pdf', metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


if __name__ == '__main__':
    draw()
