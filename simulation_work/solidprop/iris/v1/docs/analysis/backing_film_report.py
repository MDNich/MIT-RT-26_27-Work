"""Plot recovered wall heating and report audited endpoint sensitivity."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from continuous_heating_campaign import digest
from ops import ROOT


def build(cases, inputs):
    def register(path):
        sha = digest(path)
        inputs[str(path.relative_to(ROOT))] = sha
        return sha

    def read(name, expected=None):
        path = ROOT / name
        sha = register(path)
        if expected and sha != expected:
            raise ValueError(f'Heating sensitivity input changed: {name}')
        return json.loads(path.read_text())

    proof = read('validation/evolving_backing_film_audit.json')
    plan = read('configs/evolving_backing_film.json', proof['plan_sha256'])
    traces = read('validation/evolving_backing_film_histories.json', proof['histories_sha256'])
    assert register(ROOT/'model/audit_backing_film.py') == proof['auditor_sha256']
    assert proof['native'] is False and proof['eligible_for_motor_lifetime'] is False
    assert len(plan['cases']) == proof['jobs'] == 24
    for name, sha in plan['inputs'].items():
        assert digest(ROOT/name) == sha
    levels = ('500', '1000', '2000')
    colors = ('#37658a', '#54514a', '#ad4d20')
    results = proof['results']
    rows, flux_rows, verified, reopened = [], [], [], []
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 3.7), sharex=True, sharey=True, layout='constrained')
    for (case, label, _), ax in zip(cases, axes.flat):
        group = results[case]
        is_cf = case.endswith('_cf')
        times, material, means = [], [], []
        for level, color in zip(levels, colors):
            record = group[level]
            event = record['event_s']
            times.append(f'{event:.1f}')
            milestone = record['events']['first_1000C' if is_cf else 'all_liquid']
            material.append(f'{milestone[1]:.1f}' if milestone else '---')
            trace = traces[case][level]
            assert trace['event_s'] == event and trace['events'] == record['events']
            t = np.asarray(trace['time_s'])
            q = np.asarray(trace['mean_film_MW_m2'])
            cut = np.searchsorted(t, trace['events']['property_flag'][1])
            ax.plot(t[:cut], q[:cut], lw=1.35, color=color, label=level)
            ax.plot(t[max(0, cut-1):], q[max(0, cut-1):], lw=1.35, color=color, ls='--')
            ax.plot(t[-1], q[-1], marker='.', color=color, ms=4)
            lo, hi = trace['whole_mean_bounds_MW_m2']
            means.append(f'{(lo+hi)/2:.3f}')
            if level != '1000':
                if not record['final_FV_pairs_pass']:
                    raise ValueError(f'{case}/{level} needs further convergence work')
                verified.append(record)
                for axis, work in record['additional_FV_checks'].items():
                    assert work['passed']
                    path = ROOT/'configs/evolving_backing_film_rechecks'/f'{case}_film{level}.json'
                    assert register(path) == work['schedule_sha256']
                    reopened.append((label, level, axis, work['checks']))
        rows.append(' & '.join([label, *times, *material]) + r' \\')
        doses = [traces[case][h]['total_film_MJ_per_initial_m2'] for h in levels]
        dose_range = f'{min(doses):.1f}--{max(doses):.1f}'
        flux_rows.append(' & '.join([label, *means, dose_range]) + r' \\')
        ax.set_title(label, size=10)
        ax.tick_params(labelsize=8)
    endpoints = [r for group in traces.values() for r in group.values()]
    axes[0, 0].set_xlim(0, 1.035 * max(r['event_s'] for r in endpoints))
    axes[0, 0].set_ylim(0, 1.07 * max(max(r['mean_film_MW_m2']) for r in endpoints))
    for ax in axes[-1]:
        ax.set_xlabel('Exposure [s]', fontsize=9)
    for ax in axes[:, 0]:
        ax.set_ylabel('Wall flux [MW/m²]', fontsize=9)
    axes[0, 0].legend(frameon=False, fontsize=7, ncol=3, handlelength=1.2, loc='upper right')
    plot = ROOT/'docs/analysis/evolving_backing_heat_flux.png'
    fig.savefig(plot, dpi=200)
    plt.close(fig)
    register(plot)
    receipts = [run for item in verified for run in item['FV_records'].values()]
    receipts += [step['record'] for _, _, _, steps in reopened for step in steps]
    refs = [item['reference_FE'] for item in verified]
    max_heat = max(r['max_heat_error'] for r in receipts)
    max_mass = max(r['max_mass_error'] for r in receipts)
    max_difference = max(abs(check['delta_event_s']) for check in refs)
    max_thickness = max(check['max_common_thickness_mm'] for check in refs)
    max_interface = max(check['max_common_interface_K'] for check in refs)
    other = []
    for label, level, axis, steps in reopened:
        n, nc, dt = steps[-1]['level']
        change = abs(steps[-1]['pair']['event_difference_s'])
        other.append(rf'{label} at {level} required additional {axis} refinement. '
                     rf'At {n}/{nc} cells, the last two step ceilings were '
                     rf"{steps[-2]['level'][2]:g} and {dt:g} s. Their endpoints differed by {change:.4f} s.")
    worst_bound = max((trace['whole_mean_bounds_MW_m2'][1]-trace['whole_mean_bounds_MW_m2'][0])/2
                      for group in traces.values() for trace in group.values())
    tex = r'''\section{How strongly does incident heating change the answer?}\label{sec:film}
The following exposures start at 22 $^\circ$C, with bare phenolic facing 2504 K gas
at 800 psi. Each column changes the gas-side film coefficient before blowing,
$h_0$, in W/(m$^2$ K). Wall temperature, gas release, char consumption and
the casing response evolve together. The first three columns give the time
to consume the original liner, including its char. The last three show when
all aluminium cells become liquid or the hottest CF casing cell reaches
1000 $^\circ$C. Times are in seconds.
\begin{table}[H]\centering\begin{tabular}{lrrr@{\hspace{1.6em}}rrr}\toprule
 & \multicolumn{3}{c}{Liner exhausted} & \multicolumn{3}{c}{Casing event}\\
$h_0$ & 500 & 1000 & 2000 & 500 & 1000 & 2000 \\\midrule
ROWS
\bottomrule\end{tabular}\end{table}
The dash means the CF surrogate stayed below 1000 $^\circ$C until exhaustion.
All four casings exceeded their original material-property flags at all three
loads. The calculation retains the molten metal or decomposed composite in place.
\begin{figure}[H]\centering\includegraphics[width=0.98\textwidth]{../analysis/evolving_backing_heat_flux.png}
\caption{Modelled convective heat entering the receding surface over each
half-second interval and the final partial interval. Colours identify $h_0$.
Dashes start at the first 300 $^\circ$C Al or 150 $^\circ$C CF interface flag.
The final dot marks the mean over the last interval before liner loss.}
\end{figure}
The film changes the rate at which energy enters the wall. Even with a fixed
gas temperature and $h_0$, the driving temperature difference falls as the
surface heats, and gas from the liner suppresses convection. The actual
incident load requires a firing measurement or an independently validated
gas-side calculation.
\clearpage
\section{Heat delivered to the receding surface and numerical checks}
For one radian of circumference and one metre of axial length, the exposed
area equals its instantaneous radius $r_s$ in SI units. Each saved interval
provides its convective energy $\Delta E_f$, including the blowing correction.
The plotted flux divides this energy by the duration and average endpoint area.
Because the surface moves monotonically outwards, the two endpoint areas
also enclose the exact area--time integral. For the full exposure,
\[
 \frac{\sum\Delta E_f}{\sum r_{j+1}\Delta t_j}
 \leq \overline{q''}_f =
 \frac{\int q''_f r_s\,dt}{\int r_s\,dt}
 \leq \frac{\sum\Delta E_f}{\sum r_j\Delta t_j}.
\]
The table gives the midpoint of these bounds in MW/m$^2$. Across all
twelve histories their largest half-width is BOUND kW/m$^2$. The last column
gives cumulative film energy per original exposed area across the three loads.
\begin{table}[H]\centering\begin{tabular}{lrrrr}\toprule
 & \multicolumn{3}{c}{Mean flux [MW/m$^2$]} & Energy per original area\\
$h_0$ [W/(m$^2$ K)] & 500 & 1000 & 2000 & [MJ/m$^2$] \\\midrule
FLUXROWS
\bottomrule\end{tabular}\end{table}
\paragraph{Checking each heating level.}
For each of the eight new combinations, the finite-volume calculation was
repeated with 320/80 and 640/160 liner/casing cells at a 0.04 s step ceiling,
then with 640/160 cells at 0.02 s. An accepted pair must have overlapping
event brackets, less than 5\% endpoint change and matched thickness within
the larger of 0.02 mm and 1\% of original thickness. EXTRA

A second radial finite-element calculation used 160/40 cells and a 0.02 s
ceiling from ignition in all eight cases. Across those cases the two methods
differ by at most EVENT s at exhaustion, THICK mm of liner on
common reporting times, and TEMP K at the casing interface. For the
finite-volume records the largest fractional mass imbalance is MASS and
the largest heat imbalance relative to incident energy is HEAT.
These checks quantify numerical agreement for the stated closures.
\paragraph{What still controls the physical answer.}
In this calculation gas impinges directly on bare phenolic until its last
material is removed. Actual ignition-to-exposure delay, burn duration, casing
retention and circumferential hot spots can change the result. A local
heat-flux history and pre/post-fire liner profiles at the same station would
test both the imposed load and the predicted loss. The table on the preceding
page gives a sensitivity to load, with no assigned probability.
\clearpage
'''
    def sci(value):
        mantissa, exponent = f'{value:.1e}'.split('e')
        return '$' + rf'{mantissa}\times 10^{{{int(exponent)}}}$'

    fields = {'FLUXROWS': '\n'.join(flux_rows), 'ROWS': '\n'.join(rows),
              'BOUND': f'{1000*worst_bound:.3f}', 'EXTRA': ' '.join(other),
              'EVENT': f'{max_difference:.3f}', 'THICK': f'{max_thickness:.4f}',
              'TEMP': f'{max_interface:.2f}', 'MASS': sci(max_mass), 'HEAT': sci(max_heat)}
    for marker, value in fields.items():
        tex = tex.replace(marker, value)
    output = ROOT/'docs/en/continuous_backing_film.tex'
    output.write_text(tex)
    register(output)
    register(Path(__file__).resolve())
    stage_ranges = []
    for stage in ('sustainer', 'booster'):
        events = [results[case][level]['event_s'] for case, _, _ in cases
                  for level in ('500', '2000') if case.startswith(stage)]
        stage_ranges.append(f'{min(events):.0f}--{max(events):.0f}')
    return stage_ranges
