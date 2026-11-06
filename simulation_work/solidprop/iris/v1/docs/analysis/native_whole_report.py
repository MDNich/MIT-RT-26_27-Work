"""Build the whole-exposure ANSYS comparison from accepted run receipts."""
import json
from pathlib import Path

import numpy as np

import matplotlib.pyplot as plt

from continuous_heating_campaign import digest
from ops import ROOT


def build(cases, inputs):
    def track(path):
        value = digest(path)
        inputs[str(path.relative_to(ROOT))] = value
        return value

    ledger = ROOT/'validation/native_whole_exposure_comparison.json'
    track(ledger)
    report = json.loads(ledger.read_text())
    assert not report['eligible_for_motor_lifetime']
    assert track(ROOT/'model/compare_native_whole_exposures.py') == report['source_sha256']
    assert track(ROOT/'model/audit_liner_energy.py') == report['energy_auditor_sha256']
    by_case = {r['case']: r for r in report['cases']}
    assert [r['job'] for r in by_case.values()] == report['accepted_jobs']
    assert len(by_case) + len(report['pending_jobs']) == len(cases)
    assert report['complete_four_cases'] == (len(by_case) == 4)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.65), layout='constrained')
    rows, checks = [], []
    errors, residuals = [], []
    for case, label, color in cases:
        if case not in by_case:
            continue
        result = by_case[case]
        job = result['job']
        receipt = ROOT/f'validation/native_sector_r2_{job}.json'
        assert track(receipt) == result['native_evidence_sha256']
        run = json.loads(receipt.read_text())
        replay = run['strict_guest_replay']
        assert track(ROOT/'model/replay_archived_sector.py') == replay['source_sha256']
        assert replay['native_blocks'] == run['native_blocks']
        errors.append(replay['max_field_error_K'])
        residuals.append(abs(run['balances']['energy_relative']))
        assert run['passed'] and run['role'] == 'whole' and run['native_interval_start_s'] == 0
        assert track(ROOT/'model/audit_sector_endpoint.py') == run['auditor_sha256']
        cf = case.endswith('_cf')
        fv_name = case + ('_reacting_fine' if cf else '_phase_n640_ms20_mK500')
        fv_path = ROOT/'validation'/('cf_backing_cases' if cf else 'aluminium_backing_cases')/(fv_name+'.json')
        assert track(fv_path) == result['fv_sha256']
        independent = json.loads(fv_path.read_text())['history']
        assert run['terminal_s'] == result['native_end_s']
        cutoff = result['casing_event_bracket_s'][1]
        history = result['history']
        times = [0.] + [r['time_s'] for r in history]
        thickness = [result['initial_mm']] + [r['remaining_mm'] for r in history]
        join = int(np.searchsorted(times,cutoff))
        at_cut = np.interp(cutoff, times, thickness)
        before, after = times[:join]+[cutoff], [cutoff]+times[join:]
        axes[0].plot(before, thickness[:join]+[at_cut], color=color, label=label)
        axes[0].plot(after, [at_cut]+thickness[join:], color=color, ls='--')
        axes[0].plot(cutoff, at_cut, 'o', color=color, ms=3)
        axes[0].plot(times[-1], thickness[-1], 'o', color=color, ms=3, clip_on=False)
        delta = result['common_times']['differences']['remaining_mm']['max_abs']
        ref_t = [r['time_s'] for r in independent]
        ref_y = [r['remaining_mm'] for r in independent]
        axes[0].plot(ref_t, ref_y, ':', color=color, lw=.9)
        temperatures = [22.] + [r['interface_C'] for r in history]
        interface_at_cut = np.interp(cutoff, times, temperatures)
        axes[1].plot(before, temperatures[:join]+[interface_at_cut], color=color)
        axes[1].plot(after, [interface_at_cut]+temperatures[join:], color=color, ls='--')
        axes[1].plot(cutoff, interface_at_cut, 'o', color=color, ms=4)
        axes[1].plot(times[:-1], [22.] + [r['hot_C'] for r in history[:-1]], color=color, lw=1,ls='-.')
        gap = result['event_interval_gap_s']
        rows.append(f"{label} & {cutoff:.2f} & {at_cut:.3f} & {result['native_end_s']:.2f} & "
                    f"{result['independent_end_s']:.2f} & {result['native_minus_independent_s']:+.3f} & {gap:.3f}"+r' \\')
        checks.append(f"{label} & {result['native_blocks']:,} & {1000*delta:.2f} & "
                      f"{result['heat_dose_MJ_m2']['native']:.2f} & {result['peak_sampled_live_face_C']:.0f} & "
                      f"{'Pass' if result['meets_event_and_thickness_targets'] else 'Outside'}"+r' \\')
    axes[0].set(ylabel='Remaining phenolic [mm]', ylim=(0,None))
    axes[1].set_ylabel('Solid temperature [°C]')
    for ax in axes:
        ax.set(xlabel='Time since gas exposure [s]', xlim=(0,None))
    axes[0].legend(fontsize=8, frameon=False)
    plot = ROOT/'docs/analysis/native_whole_exposure.png'
    fig.savefig(plot, dpi=185)
    plt.close(fig)
    track(plot)
    text = r'''\section{Native ANSYS from first exposure to burnthrough}\label{sec:whole}
The entire liner and casing start at 22~$^\circ$C. At zero time, 2504~K gas contacts
bare phenolic and the nominal film and pressure are held until all liner mass
has left the wall. The controller updates chemistry and material removal after
each MAPDL thermal solve. Both bodies evolve from their initial state throughout.
The table gives the audited full-exposure results.

\begin{center}\small\begin{tabular}{lrrrrrr}\toprule
 & Casing & Liner left & ANSYS & Radial & Difference & Interval\\
Motor & event [s] & [mm] & gone [s] & gone [s] & [s] & gap [s]\\\midrule
EVENTS
\bottomrule\end{tabular}\end{center}
The earlier casing event marks all aluminium liquid or the CF casing reaching
1000~$^\circ$C. Liner thickness at that time is interpolated between adjacent
half-second samples. Times use the upper end of each recorded event interval.
The gap is the separation between the two final time-step intervals. A positive
value leaves exact event-interval agreement unresolved.
Molten Al and hot CF residue retain their prescribed geometry in these
calculations. Their ability to contain 800~psi lies outside this thermal model.

\begin{figure}[H]\centering\includegraphics[width=.98\textwidth]{../analysis/native_whole_exposure.png}
\caption{Left, native liner thickness and independent finite-volume
thickness (dotted). Right, native interface and exposed liner (dash-dot)
temperatures. The final surface point precedes liner loss. Dashed lines use the
retained casing model after complete fusion or the CF property limit.}
\end{figure}
\begin{center}\small\begin{tabular}{lrrrrl}\toprule
& Native field & Max.\ thickness & Film dose & Peak live & Time and\\
Motor & solves & diff.\ [$\mu$m] & [MJ/m$^2$] & face [$^\circ$C] & thickness\\\midrule
CHECKS
\bottomrule\end{tabular}\end{center}
Thickness differences use common half-second stations before either liner
vanishes. The peak uses the sampled exposed phenolic surface while mass remains.
Film dose integrates heat entering the moving wall per original hot-face area.
The comparison targets a time difference below 1\% and thickness difference
no greater than the larger of 0.02~mm and 1\% of initial thickness. Both
models use the same assumed heating history and char-removal energy.

Every saved native field was replayed from the initial state using the sealed
controller and an independently assembled radial thermal system. The largest
field discrepancy was ERR~K. The largest absolute net energy residual was
RES of the film energy. The audit distinguishes solver messages during the
calculation from the ten-core performance advisory MAPDL can issue at exit.
\clearpage
'''
    for label,value in [('ERR',max(errors)),('RES',max(residuals))]:
        coeff,exp=f'{value:.1e}'.split('e')
        text=text.replace(label,rf'${coeff}\times10^{{{int(exp)}}}$')
    output = ROOT/'docs/en/continuous_native_whole.tex'
    output.write_text(text.replace('EVENTS', '\n'.join(rows)).replace('CHECKS', '\n'.join(checks)))
    track(output)
    track(Path(__file__).resolve())
    return by_case
