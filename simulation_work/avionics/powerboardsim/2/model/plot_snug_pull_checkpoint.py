"""Plot the audited early forward pull with both screw materials and the matched bare fixture."""
import numpy as np
from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator

from audit_local import ROOT, read
from compare_pull import series
from compare_snug_forward_mounts import CHECKPOINTS, OUTPUT
from film_identity import verified
from report_plot import plt
from stage_snug_fit import AUDIT


def plot():
    comparison = read(OUTPUT)
    for key, name in CHECKPOINTS.items():
        verified(AUDIT/name, comparison['checkpoint_sha256'][key])
    proof, bare = series(comparison['bare_case'])
    assert proof['rst_sha256'] == comparison['bare_rst_sha256']
    rows = comparison['common_native_travel']
    labels = ['Bare', 'Nylon', 'Aluminium']
    colors = ['#08357E', '#38761D', '#7A0101']
    fig, (ax, bx, cx) = plt.subplots(1, 3, figsize=(8.15, 2.5), layout='constrained',
                                   gridspec_kw={'width_ratios': [1.2, 1., 1.2]})
    ax.plot([r['ux_mm'] for r in bare], [r['cell_force_N'] for r in bare],
            '.-', color=colors[0], ms=3, lw=1.3, label=labels[0])
    for key, label, color in zip(('nylon', 'aluminium'), labels[1:], colors[1:], strict=True):
        ax.plot([r['travel_mm'] for r in rows], [r[key]['cell_force_N'] for r in rows],
                'o-', ms=2.8, lw=1.3, color=color, label=label)
    ax.set(xlim=(0, .22), ylim=(0, 260), xlabel='Cell travel [mm]', ylabel='Applied force [N]',
           title='Same imposed travel', xticks=[0, .1, .2])
    ax.legend(fontsize=8, frameon=False, loc='upper left')
    endpoint = comparison['bare_endpoint']
    target = endpoint['cell_force_N']
    bx.plot(endpoint['ux_mm'], 2, 'o', color=colors[0], ms=4)
    bx.text(endpoint['ux_mm'], 2.16, '0.500', color=colors[0], ha='center', fontsize=8)
    for key, y, color in zip(('nylon', 'aluminium'), (1, 0), colors[1:], strict=True):
        item = comparison['equal_load'][key]
        x = item['travel_mm']
        lo, hi = item['native_travel_mm']
        bx.errorbar(x, y, xerr=np.array([[x-lo], [hi-x]]), fmt='D', capsize=4,
                    markersize=4, color=color, lw=1.4)
        bx.text(x, y+.17, f'{x:.3f}', color=color, ha='center', fontsize=8)
    bx.set(xscale='log', xlim=(.014, .75), ylim=(-.45, 2.55), yticks=[2, 1, 0],
           yticklabels=labels, xlabel='Cell travel [mm, log scale]', title=f'At {target:.2f} N')
    bx.xaxis.set_major_locator(FixedLocator([.02, .05, .1, .5]))
    bx.xaxis.set_major_formatter(FixedFormatter(['0.02', '0.05', '0.1', '0.5']))
    bx.xaxis.set_minor_locator(NullLocator())
    end = rows[-1]
    screws = [0.] + [end[key]['screw_support_resistance_N'] for key in ('nylon', 'aluminium')]
    nickel = [end['bare']['cell_force_N']] + [end[key]['nickel_clamp_resistance_N'] for key in ('nylon', 'aluminium')]
    neighbours = [0.] + [end[key]['neighbor_resistance_N'] for key in ('nylon', 'aluminium')]
    cx.barh([2, 1, 0], screws, height=.48, color='#8EACD5', label='Case mounts')
    cx.barh([2, 1, 0], nickel, left=screws, height=.48, color='#5A43A0', label='Nickel clamps')
    cx.barh([2, 1, 0], neighbours, left=np.array(screws)+nickel, height=.48, color='#38761D', label='Fixed neighbour')
    for y, total in zip((2, 1, 0), np.array(screws)+nickel+neighbours, strict=True):
        cx.text(total+2., y, f'{total:.2f}', va='center', fontsize=8)
    cx.set(xlim=(0, 305), ylim=(-.45, 2.75), yticks=[2, 1, 0], yticklabels=labels,
           xlabel='Lateral support reaction [N]', title='At 0.206875 mm')
    cx.legend(fontsize=7, frameon=False, loc='upper right')
    for axis in (ax, bx, cx):
        axis.title.set(color='#08357E', fontsize=10)
        axis.tick_params(labelsize=8)
        axis.spines[['top', 'right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/snug-forward-pull.pdf', metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


if __name__ == '__main__':
    plot()
