"""Report refinement of the independent radial reduction of the sealed R2 equations."""
import json
from pathlib import Path

import matplotlib.pyplot as plt

from check_whole_event_intervals import LEVELS, PACKAGE, WORK
from continuous_heating_campaign import digest
from ops import ROOT


def build(cases, inputs):
    def track(path):
        signature = digest(path)
        inputs[str(path.relative_to(ROOT))] = signature
        return signature

    ledger = ROOT/'validation/whole_event_interval_refinement.json'
    study = json.loads(ledger.read_text())
    assert track(ledger) == json.loads((WORK/'complete.json').read_text())['sha256']
    assert not study['native'] and not study['eligible_for_motor_lifetime']
    assert track(ROOT/'model/check_whole_event_intervals.py') == study['source_sha256']
    archive = track(PACKAGE/'controller.zip')
    labels = {case: (label, color) for case, label, color in cases}
    rows = []
    changes = []
    fig, ax = plt.subplots(figsize=(7, 2.55), layout='constrained')
    for job, case in study['cases'].items():
        label, color = labels[case['case']]
        runs = case['runs']
        settings = track(PACKAGE/(job+'_settings.json'))
        assert [(r['n'], r['dt_s']) for r in runs] == LEVELS
        for row in runs:
            assert row['archive_sha256'] == archive and row['base_settings_sha256'] == settings
            assert row['study_sha256'] == study['source_sha256'] and row['nc'] == row['n']//4
            assert max(map(abs, row['residuals'].values())) < 1e-7
        reference = case['independent_FV_bracket_s'][1]
        ends = [r['event_bracket_s'][1] for r in runs]
        ax.plot(range(len(runs)), [1000*(end-reference) for end in ends],
                marker='o', ms=3.5, label=label, color=color)
        changes.append((abs(ends[-2]-ends[-3]), abs(ends[-1]-ends[-2])))
        rows.append(f"{label} & {ends[0]:.3f} & {ends[-1]:.3f} & {reference:.3f} & "
                    f"{1000*(ends[-1]-reference):+.1f} & {1000*runs[-1]['raw_interval_gap_s']:.1f}"+r' \\')
    ax.axhline(0, color='0.25', lw=.7)
    ax.set_xticks(range(len(LEVELS)), [f'{n}\n{dt*1000:g}' for n, dt in LEVELS])
    ax.set(xlabel='Phenolic radial cells (top) and maximum time step [ms] (bottom)',
           ylabel='Nodal minus FV [ms]')
    ax.legend(ncol=2, frameon=False, fontsize=8)
    figure = ROOT/'docs/analysis/whole_event_refinement.png'
    fig.savefig(figure, dpi=185)
    plt.close(fig)
    track(figure)
    text = r'''\section{How precisely is liner exhaustion resolved?}\label{sec:intervals}
We repeated each continuous exposure eight times using the independently
assembled radial nodal system from the sealed sector controller. All 32
runs started cold and advanced to zero phenolic mass. At each refinement we
held the gas load, geometry, chemistry and evolving casing model fixed.
The casing mesh always had one quarter as many radial cells as the liner.

\begin{center}\small\begin{tabular}{lrrrrr}\toprule
& Coarse nodal & Fine nodal & Reference FV & Difference & Gap\\
Motor & [s] & [s] & [s] & [ms] & [ms]\\\midrule
ROWS
\bottomrule\end{tabular}\end{center}
The coarse column uses the native production settings (80 liner cells,
40~ms maximum step). The fine column uses 640 cells and 2.5~ms. The reference
finite-volume (FV) times use the previously published 640-cell calculation
with a 20~ms maximum step. Each time is the upper end of the final integration
interval. The gap measures the separation between the nearest ends of the two
final intervals. Decimal places here expose differences between calculations.

\begin{figure}[H]\centering\includegraphics[width=.95\textwidth]{../analysis/whole_event_refinement.png}
\caption{Change in predicted exhaustion time relative to the same FV
reference for each motor. Adjacent settings change either space or time resolution.
The temporary dip for the CF sustainer occurs at the coarse 40~ms step.}
\end{figure}
At 320 liner cells, halving the maximum step from 5 to 2.5~ms changes the
endpoint by at most TIME~ms. At 2.5~ms, increasing from 320 to 640 cells
changes it by at most SPACE~ms. The fine nodal and reference FV estimates
support the same whole-second scale. The positive gaps still matter for a
claim of tighter agreement. A comparison at matched mesh and time settings
can distinguish residual differences between the two methods from the effect
of their unequal time steps. Material and firing assumptions limit the
physical interpretation throughout.
\clearpage
'''
    text = text.replace('ROWS', '\n'.join(rows))
    text = text.replace('TIME', f'{1000*max(x[0] for x in changes):.1f}')
    text = text.replace('SPACE', f'{1000*max(x[1] for x in changes):.1f}')
    output = ROOT/'docs/en/continuous_event_intervals.tex'
    output.write_text(text)
    track(output)
    track(Path(__file__).resolve())
