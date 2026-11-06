"""Compare the last finite-volume and nodal increments at matched resolution."""
from pathlib import Path

import matplotlib.pyplot as plt

from backing_film_campaign import read
from continuous_heating_campaign import digest
from ops import ROOT
from recover_matched_intervals import OUT, PACKAGE, PLAN, WORK, PARENT, NODAL


def build(cases, inputs):
    def track(path):
        value = digest(path)
        inputs[str(path.relative_to(ROOT))] = value
        return value

    record = read(OUT)
    done = read(WORK/'complete.json')
    assert track(OUT)==done['audit_sha256'] and not record['native'] and not record['eligible_for_motor_lifetime']
    assert track(PLAN)==done['plan_sha256']==record['plan_sha256']
    plan = read(PLAN)
    assert track(PARENT)==plan['parent_sha256']
    assert track(NODAL)==record['nodal_study_sha256']==plan['nodal_sha256']
    assert track(ROOT/'model/recover_matched_intervals.py')==plan['runner_sha256']
    for material, value in plan['drivers'].items():
        assert track(PACKAGE/(material+'_driver.py'))==value
    levels = read(PARENT)['levels']
    assert set(record['cases'])=={name for name, _, _ in cases}
    fig, ax = plt.subplots(figsize=(7.1,2.55), layout='constrained')
    rows = []
    max_delta, max_thickness, max_temperature, positive_gaps = 0., 0., 0., 0
    for index, (name, label, _) in enumerate(cases):
        results = record['cases'][name]
        assert [[row['n'],row['dt_s']] for row in results]==levels
        endpoints = [row['FV_interval_s'][1] for row in results]
        fine = results[-1]
        ref = endpoints[-1]
        for key, offset, color, desc in [('FV_interval_s',-.13,'#194b78','Finite volume'),
                                         ('FE_interval_s',.13,'#ab542b','Nodal finite element')]:
            lo,hi = fine[key]
            assert 0 < hi-lo < fine['dt_s']+1e-8
            ax.plot([1000*(lo-ref),1000*(hi-ref)], [index+offset]*2, '|-',
                    color=color, label=desc if index==0 else None, ms=8, lw=2)
        max_delta = max(max_delta, abs(fine['end_FE_minus_FV_s']))
        positive_gaps += fine['raw_interval_gap_s']>0
        field = fine['common_stations']['differences']
        max_thickness = max(max_thickness, field['remaining_mm']['max_abs'])
        max_temperature = max(max_temperature,field['interface_C']['max_abs'])
        rows.append(f"{label} & {ref:.4f} & {fine['FE_interval_s'][1]:.4f} & "
                    f"{1000*(endpoints[1]-endpoints[0]):+.2f} & {1000*(endpoints[2]-endpoints[1]):+.2f} & "
                    f"{1000*fine['raw_interval_gap_s']:.2f}"+r' \\')
    ax.axvline(0,color='.45',lw=.6)
    ax.set_yticks(range(len(cases)), [label for _, label, _ in cases])
    ax.set_ylim(len(cases)-.6,-.55)
    ax.set_xlabel('Time relative to the fine finite-volume endpoint for each case [ms]')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,1.18),ncol=2,fontsize=8,frameon=False)
    figure = ROOT/'docs/analysis/matched_final_intervals.png'
    fig.savefig(figure,dpi=185)
    plt.close(fig)
    track(figure)
    text = r'''\section{Final time intervals at matched resolution}\label{sec:matched}
Both independent methods use the same number of radial cells and the same
maximum time step in each comparison. We first halve the step at 320 liner
cells (5 to 2.5~ms), then double the liner mesh to 640 cells at 2.5~ms.
The casing has one quarter the liner cell count. All runs impose the same
continuous nominal heating and evolve the casing from ambient temperature.

\begin{center}\small\begin{tabular}{lrrrrr}\toprule
& Fine FV & Fine nodal & FV time-step & FV mesh & Final gap\\
Motor & [s] & [s] & change [ms] & change [ms] & [ms]\\\midrule
ROWS
\bottomrule\end{tabular}\end{center}
The time columns give the upper ends of the last integration intervals. Each
change column subtracts the previous finite-volume endpoint while varying
just the indicated setting. At the finest common resolution, the largest
difference between method endpoints is DELTA~ms. At common half-second stations,
the largest thickness difference is THICK~$\mu$m and the largest casing-interface
temperature difference is TEMP~K.

\begin{figure}[H]\centering\includegraphics[width=.96\textwidth]{../analysis/matched_final_intervals.png}
\caption{Each segment runs from the last saved step with liner present to the
numerical exhaustion event. The origin in each row is its own FV endpoint.
The clear space between segments is the gap reported in the table.}
\end{figure}
The final numerical intervals are separated in COUNT.
Their width reflects the integration step alone. The unknown firing heat flux,
recession chemistry and post-limit casing response introduce separate physical
uncertainties.

\paragraph{Output-time recovery.}
One FV run approached the 142~s sample to about $1.0\times10^{-10}$~s and
attempted a separate step of that duration. Its energy check rejected the step.
The successor splits the preceding interval into two comparable steps whenever
the next sample would otherwise leave a remainder below 5\% of a normal step.
It resumed the Al booster from its saved 126.235~s state, retaining its mass and
heat histories. The seven already completed FV paths kept their original
records. All twelve comparisons use the original balance tolerances.
\clearpage
'''
    for token, value in [('ROWS','\n'.join(rows)),('DELTA',f'{1000*max_delta:.2f}'),
                         ('THICK',f'{1000*max_thickness:.2f}'),('TEMP',f'{max_temperature:.2f}'),
                         ('COUNT','all four cases' if positive_gaps==4 else f'{positive_gaps} of four cases')]:
        text = text.replace(token,value)
    output = ROOT/'docs/en/continuous_matched_intervals.tex'
    output.write_text(text)
    track(output)
    track(Path(__file__).resolve())
