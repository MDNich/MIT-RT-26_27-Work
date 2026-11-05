"""Render the frozen geometry-control prefix without reading the active solve."""
import json
import numpy as np
import matplotlib.pyplot as plt
from latex_style import configure_latex


def create(root):
    path = root / 'validation/native_geometry_control_prefix.json'
    if not path.exists():
        return ''
    d = json.loads(path.read_text())
    assert d['status'] == 'VERIFIED_PREFIX_ONLY_TERMINAL_PENDING'
    c = d['comparison']; a = d['native_prefix_audit']
    assert c['comparison_passed'] and c['native_control_checks_passed'] and a['passed']
    samples = c['comparisons']
    configure_latex()
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.0), constrained_layout=True)
    axes[0].semilogy([x['time_s'] for x in samples],
                     [x['max_live_profile_difference_K'] for x in samples], 'o', ms=4, color='#24547a')
    axes[0].axvline(7, color='gray', ls=':', lw=.9)
    axes[0].set(xlabel='Compared time [s]', ylabel='Maximum live profile difference [K]',
                title='Selected comparison times only')
    chosen = [min(samples, key=lambda x: abs(x['time_s'] - 7)), samples[-1]]
    for sample in chosen:
        start = sample['native_rows_removed_during_solve']
        depth = (np.array(sample['radius_m']) - sample['radius_m'][0]) * 1000
        delta = np.array(sample['native_temperature_C']) - np.array(sample['independent_temperature_C'])
        axes[1].plot(depth[start:], delta[start:], label=f"{sample['time_s']:.4g} s")
    axes[1].axvline(4.7625, color='gray', ls=':', lw=.9)
    axes[1].set(xlabel='Depth from original liner bore [mm]',
                ylabel='Native minus cylindrical reference [K]', title='Live nodal profiles')
    axes[1].legend(fontsize=8)
    fig.suptitle('Sustainer Al geometry control: verified prefix, full history unfinished')
    out = root / 'docs/analysis/geometry_control_comparison'
    fig.savefig(out.with_suffix('.pdf')); fig.savefig(out.with_suffix('.png'), dpi=180)
    plt.close(fig)
    events = '\n'.join(
        f"{e['rows_scheduled']} & {e['scheduled_index']} & {e['scheduled_time_s']:.6f} & "
        f"{e['independent_scheduled_time_s']:.6f} & {e['first_transferred_time_s']:.6f} \\\\"
        for e in c['removal_events'])
    text = r'''
\clearpage
\section{Geometry consistency and exact removal-event verification}
\label{sec:geometry-control}
\textbf{This section reports a verified prefix, not a completed spatial-convergence result.}
The fresh ten-core sustainer Al control has been independently compared through
TIME s (INDEX accepted native intervals). Its prescribed horizon is 127 s.
Both row-removal events and the heating-to-cooling transition pass the unchanged
checks. The complete cooling history, terminal native logs/restarts and comparison
of casing peaks against the 80-row case remain unfinished at this edition.

\subsection{Why the earlier 160-row comparisons were held}
The original 160/40-row mesh uses two angular cells across a $0.5^\circ$ sector.
Its controller assigned circular-arc areas and volumes, while the eight-node
SOLID278 mesh has straight-sided faces. For one angular cell of width
$\delta\theta$ radians and axial length $\ell$, the geometric measures are
\begin{align}
A_{\mathrm{arc}} &= r\,\delta\theta\,\ell,
& A_{\mathrm{hex}} &= 2r\sin(\delta\theta/2)\,\ell,\\
V_{\mathrm{arc}} &= \tfrac12(r_o^2-r_i^2)\delta\theta\,\ell,
& V_{\mathrm{hex}} &= \tfrac12(r_o^2-r_i^2)\sin(\delta\theta)\,\ell.
\end{align}
Thus $A_{\mathrm{hex}}/A_{\mathrm{arc}}=\sin(\delta\theta/2)/(\delta\theta/2)$
and $V_{\mathrm{hex}}/V_{\mathrm{arc}}=\sin(\delta\theta)/\delta\theta$.
At $\delta\theta=0.25^\circ$, these ratios are 0.999999206726 and
0.999996826905. Direct triangle-area and hexahedral-Jacobian integration of
the actual mesh coordinates confirmed the mismatch. The native applied
hot-face power also followed the polygonal area rather than the controller's
arc area. These discrepancies are small, but the discrete removal event is
triggered by crossing a residual-mass threshold; a small accumulated difference
can move it by a complete coupling interval.

The original native calculation scheduled row two at 6.540625 s, whereas the
independent cylindrical calculation scheduled it at 6.543750 s: one heating
interval, $\Delta t=0.003125$ s, later. Tightening the native heat-flow tolerance
from $10^{-5}$ to $10^{-7}$ did not change this mismatch. Both native runs
passed their balance and topology audits but failed the strict event comparison,
and were cleanly paused with their records preserved. Their selected live-profile
differences were below 0.25 K; field agreement alone therefore was insufficient.
An isolated independent area perturbation reproduced the earlier second event,
supporting the geometry diagnosis without establishing a unique cause for every
remaining field difference. No material coefficient or removal cutoff was fitted.

\subsection{Fresh control and unchanged acceptance rules}
The fresh control retains 160 phenolic and 40 casing radial cells, two axial and
two angular cells, 800 elements and 1809 nodes. Height remains 0.5 mm.
The total angle is reduced to $0.05^\circ$ and the controller now uses the exact
straight-sided measures above. Full-ring mass/power scaling becomes 7200.
The radial and temporal resolution, $10^{-7}$ heat-flow tolerance, material DLL,
reaction laws, 0.001 residual-solid cutoff and comparison gates are unchanged
from the tighter-tolerance diagnostic. Initial temperature is 22 degrees Celsius;
no discrepant native solution was inherited.

This is a \emph{joint geometry-consistency and angular-refinement control};
the two changes have not been tested separately. Direct integration agrees with
its controller areas to $3.3\times10^{-13}$ relative and volumes to
$1.1\times10^{-10}$. A separate two-solid curved STEP passes the dimension and
volume round-trip checks; its exact CAD volumes are deliberately distinguished
from the straight-sided finite-element volumes. Historical primary maps and
sealed inputs were checked and remain unchanged.

\clearpage
\subsection{Verified events, cooling and field comparisons}
The removal gate requires matching event sets and matching scheduled times
within $10^{-8}$ s, in addition to matching removed-row counts. Either sign of
a one-interval mismatch fails. A regression check retained all nine previously
passing comparisons. For this new prefix both event sets match, and the largest
event-time difference is $1.56\times10^{-13}$ s (floating-point accumulation).
Scheduling occurs after a converged interval; the new exposed face receives
the load during the following solve, hence the distinct transfer times below.
\begin{table}[H]\centering\small
\begin{tabular}{rrrrr}\toprule
Row & Interval & Native schedule [s] & Reference schedule [s] & First transfer [s]\\\midrule
EVENTS
\bottomrule\end{tabular}
\caption{Whole-row removal events in the verified control prefix. The second
native event lies in the bracket (6.540625, 6.543750] s.}
\end{table}

At 7 s the imposed hot-gas pulse ends. The subsequent solves use 22-degree gas
and $h=8\ \mathrm{W\,m^{-2}\,K^{-1}}$, with char consumption disabled by the
prescribed exposure switch. Native load transfer, persistent deactivation and
cooling controls pass. This switch verifies the imposed scenario, not a measured
motor tailoff.

All INDEX native intervals through TIME s pass the step-balance,
live-element, single-substep and sealed-input checks. Maximum relative energy
residual is ENERGY and hot-power residual is POWER; maximum absolute mass
residual is MASS kg. Immutable audit/checkpoint hashes and the selected
independent profiles are frozen in
\path{validation/native_geometry_control_prefix.json}. This record intentionally
does not replace the terminal acceptance file, which does not yet exist.

Across COUNT selected comparison times, including both schedule/transfer pairs,
the pulse switch and the final frozen state, the largest live-profile difference
is MAXDIFF K, at 7 s. This is a maximum over the recorded comparisons, not
a bound over every intermediate native state. Conversion and solid-mass checks
also pass. The reference remains a separate cylindrical radial assembly;
numerical agreement does not calibrate the unmeasured wall heating or char law.
\begin{figure}[H]\centering
\includegraphics[width=\textwidth]{../analysis/geometry_control_comparison.pdf}
\caption{Frozen native/reference comparison. The left panel shows discrete
sample comparisons, without interpolation between them. The right panel excludes
removed rows; its vertical dotted line marks the phenolic/casing interface.}
\end{figure}

The main campaign remains held while this single ten-core control completes.
Only after terminal and spatial review will the remaining cases be mapped to
fresh corrected packages. Published four-case primary and time-only results
remain unchanged; no new burnthrough time or full-history casing maximum is
claimed from this partial control.
'''
    replacements = {'TIME': f"{c['accepted_native_time_s']:.4f}", 'INDEX': str(a['steps']),
                    'EVENTS': events, 'COUNT': str(len(samples)),
                    'MAXDIFF': f"{max(x['max_live_profile_difference_K'] for x in samples):.8f}",
                    'ENERGY': r'\num{' + f"{a['max_energy_relative_error']:.4g}" + '}',
                    'POWER': r'\num{' + f"{a['max_hot_power_relative_error']:.4g}" + '}',
                    'MASS': r'\num{' + f"{a['max_abs_mass_residual_kg']:.4g}" + '}'}
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text
