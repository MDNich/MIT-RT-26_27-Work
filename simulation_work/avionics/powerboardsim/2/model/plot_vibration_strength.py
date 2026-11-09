"""Compare peak signed PLA tension with the directional printed-coupon strengths."""
import numpy as np

from audit_local import ROOT, read
from film_identity import digest
from installation_material import PLA
from report_plot import plt


def draw():
    startup = read(ROOT/'validation/startup_ramp/comparison.json')['cases']
    axes = 'XYZ'
    x = np.arange(len(axes))
    fig, panels = plt.subplots(1, 3, figsize=(9.2, 2.9), sharey=True, layout='constrained')
    for j, (screw, color) in enumerate((('nylon', '#3C78D8'), ('aluminium', '#38761D'))):
        peak = []
        ramp_layer = []
        ramp_plane = []
        for axis in axes:
            key = f'stand3_{screw}'
            source = ROOT/'validation/motion'/f'{key}_motion_{axis}.json'
            native = read(source)
            geometry = read(ROOT/'validation/curved_contact'/f'{key}_native_{axis}.json')
            assert geometry['native_motion_sha256'] == digest(source) and native['duration_s'] == 9.
            stress = native['native_seeded_PLA_layer_stress']['peak_tension_MPa']
            assert np.isclose(stress, geometry['peak_native_layer_tension_MPa'])
            peak.append(100 * stress / PLA['layer_tension_MPa'])
            ramp = startup[f'{key}_{axis}']
            ramp_layer.append(100 * ramp['layer_tension_MPa']['maximum_MPa'] / PLA['layer_tension_MPa'])
            ramp_plane.append(100 * ramp['in_plane_tension_MPa']['maximum_MPa'] / PLA['in_plane_tension_MPa'])
        for panel, values in zip(panels, (peak, ramp_layer, ramp_plane), strict=True):
            bars = panel.bar(x + (j-.5)*.35, values, width=.33, color=color, label=screw.capitalize()+' screws')
            panel.bar_label(bars, fmt='%.0f', fontsize=8, padding=2)
    titles = ('Through layers, 9 s', 'Through layers, first 0.1 s', 'In plane, first 0.1 s')
    for panel, title in zip(panels, titles, strict=True):
        panel.set(title=title, xlabel='Base excitation axis', xticks=x, xticklabels=list(axes), ylim=(0, 300))
        panel.axhline(100, color='#7A0101', linestyle='--', linewidth=1)
        panel.spines[['right', 'top']].set_visible(False)
    panels[0].set_ylabel(r'Peak / coupon strength [\%]')
    handles, labels = panels[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncols=2, frameon=False, loc='outside lower center', fontsize=9)
    fig.savefig(ROOT/'docs/figures/pla-vibration-strength.pdf', metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__ == '__main__':
    draw()
