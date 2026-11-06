"""Render the independent continuous-exposure results and candidate balance derivation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'model'))
from ops import disks, atomic
from moving_surface_report import build as build_moving_results
from backing_report import build as build_backing_results
from sector_report import build as build_sector_results
from native_wall_report import build as build_native_verification
from liner_energy_report import build as build_liner_energy
from backing_film_report import build as build_film_results
from coupled_cf_report import build as build_coupled_cf_results

CASES = [('sustainer_al','Sustainer Al','#194b78'), ('sustainer_cf','Sustainer CF','#af6030'),
         ('booster_al','Booster Al','#357b53'), ('booster_cf','Booster CF','#82518e')]
SUFFIX = ['scout_n160','time_half_n160','joint_n320']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chart(records):
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.8), sharex=True, layout='constrained')
    for case, name, color in CASES:
        r = records[case][2]
        samples = r['history']
        t = np.array([x['time_s'] for x in samples])
        threshold = r['property_limit_bracket_s'][1]
        cut = np.searchsorted(t, threshold)
        assert t[cut] == threshold
        for ax, field in zip(axes, ['remaining_mm','interface_C']):
            y = [x[field] for x in samples]
            style = 'steps-post' if field == 'remaining_mm' else 'default'
            ax.plot(t[:cut+1], y[:cut+1], color=color, label=name, lw=1.5, drawstyle=style)
            ax.plot(t[cut:], y[cut:], color=color, ls=':', lw=1.7, drawstyle=style)
            ax.plot(t[cut], y[cut], 'o', color=color, ms=4)
    axes[0].set(ylabel='Retained liner thickness [mm]', ylim=(0,6.65))
    axes[1].set(xlabel='Continuous imposed heating [s]', ylabel='Liner–casing interface [°C]')
    axes[0].legend(ncol=2, fontsize=9)
    for ax in axes:
        ax.set_xlim(left=0)
    path = ROOT/'docs/analysis/continuous_heating_refinement'
    fig.savefig(path.with_suffix('.pdf'))
    fig.savefig(path.with_suffix('.png'), dpi=180)
    plt.close(fig)


def main():
    disks()
    audit_path = ROOT/'validation/continuous_heating_refinement_audit.json'
    audit = json.loads(audit_path.read_text())
    assert audit['records_audited'] and not audit['eligible_for_motor_lifetime']
    assert audit['audit_source_sha256'] == digest(ROOT/'model/audit_continuous_refinement.py')
    inputs = {str(audit_path.relative_to(ROOT)):digest(audit_path)}
    for kind in ['thermochemistry','boundary','conduction']:
        path = ROOT/f'validation/moving_surface_{kind}_verification.json'
        verification = json.loads(path.read_text())
        assert verification['passed']
        for source, sha in verification['sources'].items():
            assert digest(ROOT/source) == sha
        inputs[str(path.relative_to(ROOT))] = digest(path)
    restart = ROOT/'validation/continuous_checkpoint_verification.json'
    checked = json.loads(restart.read_text())
    assert checked['passed'] and checked['terminal_checkpoint_byte_equal']
    assert digest(ROOT/'model/continuous_heating_campaign.py') == checked['runner_sha256']
    assert digest(ROOT/'model/radial_model.py') == checked['reference_model_sha256']
    assert digest(ROOT/'model/check_continuous_checkpoint.py') == checked['test_sha256']
    inputs[str(restart.relative_to(ROOT))] = digest(restart)
    records = {}
    event_rows, diff_rows = [], []
    for case, name, _ in CASES:
        group = []
        for suffix in SUFFIX:
            tag = f'{case}_continuous_{suffix}'
            path = ROOT/f'validation/continuous_heating/{tag}.json'
            assert digest(path) == audit['records'][tag]['record_sha256']
            group.append(json.loads(path.read_text()))
        records[case] = group
        ends = [r['model_exhaustion_bracket_s'][1] for r in group]
        event_rows.append(' & '.join([name, *[f'{t:.2f}' for t in ends],
                                     f"{group[-1]['property_limit_bracket_s'][1]:.2f}"]) + r' \\')
        pairs = list(audit['comparisons'][case].values())
        diff_rows.append(' & '.join([name, *[f"{p['event_change_s']:+.2f}" for p in pairs],
                                    *[f"{p['half_second_max_thickness_difference_mm']:.4f}" for p in pairs],
                                    f"{pairs[0]['thickness_threshold_mm']:.4f}"]) + r' \\')
    pairs = [p for group in audit['comparisons'].values() for p in group.values()]
    t_pass = sum(p['half_second_thickness_pass'] for p in pairs)
    bracket_pass = sum(p['event_brackets_overlap'] for p in pairs)
    largest_pct = max(p['event_abs_percent_finer'] for p in pairs)
    plt.rcParams.update({'font.family':'serif','font.size':10,'axes.grid':True,'grid.alpha':.25})
    chart(records)
    build_moving_results(CASES,inputs)
    build_backing_results(inputs)
    film_ranges = build_film_results(CASES, inputs)
    build_coupled_cf_results(inputs, film_ranges)
    build_sector_results(CASES,inputs)
    build_liner_energy(CASES, inputs)
    build_native_verification(inputs)
    date = datetime.now(ZoneInfo('America/New_York')).strftime('%B %d, %Y, %H:%M %Z')
    text = r'''\documentclass[11pt]{article}
\usepackage[margin=22mm]{geometry}
\usepackage{amsmath,newtxtext,newtxmath,graphicx,booktabs,float,hyperref,listings,xcolor}
\hypersetup{colorlinks=true,urlcolor=blue,linkcolor=blue,pdftitle={Iris phenolic liners under continuous heating},pdfauthor={MIT Rocket Team}}
\lstset{basicstyle=\ttfamily\scriptsize,breaklines=true,numbers=left,numberstyle=\tiny,frame=single}
\title{Iris Phenolic Liners\\Continuous Heating to Model Exhaustion}
\author{MIT Rocket Team}
\date{DATE}
\begin{document}\maketitle
\input{continuous_executive.tex}
\input{continuous_moving_results.tex}
\input{continuous_backing_results.tex}
\input{continuous_coupled_cf.tex}
\input{continuous_sector_comparison.tex}
\input{continuous_backing_film.tex}
\input{continuous_liner_energy.tex}
\input{continuous_native_verification.tex}
\section{Comparison with the preceding finite-row model}
For a continuously exposed liner, the inherited independent model reaches
the casing after roughly two minutes for the sustainer and two and a half
minutes for the booster. Each event occurs after the casing reaches the limit
of its property evidence. Actual firing heat flux, local exposure duration
and measured liner loss are unknown. The times below describe a hypothetical
intact backing under sustained heating. Physical motor burnthrough remains open.

\begin{table}[H]\centering
\begin{tabular}{lrrrr}\toprule
 & \multicolumn{3}{c}{Time to final liner-row loss [s]} & Property flag [s]\\
\cmidrule(lr){2-4}
Case & 160, full step & 160, half step & 320, half step & 320, half step\\\midrule
EVENTROWS
\bottomrule\end{tabular}
\caption{Independent radial calculations. The initial thicknesses are 4.7625 mm
for the sustainer and 6.3500 mm for the booster. A flag marks the first
150~$^\circ$C CF or 300~$^\circ$C Al interface crossing. The table separates
this evidence limit from complete liner-row loss.}
\end{table}

The gas stays at 2504 K (2230.85~$^\circ$C), with nominal pressure 800 psi and
uncorrected film coefficient 1000 W/(m$^2$ K). Outgassing modifies convection.
Effective hot-side emissivity is zero. The outside sees 22~$^\circ$C, a film
coefficient of 8 W/(m$^2$ K) and emissivity 0.25. The hot surface temperature
evolves as the wall absorbs heat. The local liner face is exposed from time
zero until exhaustion. Sustained heating is a chosen scenario.

The three columns use 160/40, 160/40 and 320/80 radial cells in the liner
and casing. The full step ceiling is 0.0015625 s and the half step is
0.00078125 s. In all twelve records the final row disappears within that
run's time increment. Resolution changes move the event by more than an
individual time increment, so digits beyond those shown carry little meaning.

\clearpage
\section{Liner remaining and casing temperature}
\begin{figure}[H]\centering
\includegraphics[width=.94\textwidth]{../analysis/continuous_heating_refinement.pdf}
\caption{Independent 320/80 finite-row results. Dots mark the first casing-property
flag. The dotted continuation assumes an intact casing with the inherited
surrogate properties. Thickness includes retained char and is distinct from
the thickness of virgin material. Similar curves overlap near ignition.}
\end{figure}
Al uses the inherited constant properties. The CF backing uses its radial
conductivity and a heat-capacity correlation clamped to the inherited interval.
The plotted temperatures can exceed the materials' supported range by hundreds
of degrees. Integrity of a hot pressurized case, resin decomposition, bond
failure and local cracks require additional evidence.
The previous 7 s pulse and cooling results, native ANSYS verification and
complete MAPDL and Fortran listings are in the
\href{https://github.com/MDNich/MIT-RT-26_27-Work/blob/main/simulation_work/solidprop/iris/v1/output/pdf/iris_phenolic_report.pdf}{companion native report}.
Earlier rejected endurance jobs are excluded from every comparison here.

\clearpage
\section{What changes with time step and mesh?}
Time comparisons halve the time step at fixed 160/40 mesh. Mesh comparisons
double the number of cells in both materials at the same half step.
All other physics inputs match between each pair. A signed time change is
the finer result minus the coarser result.
\begin{table}[H]\centering
\begin{tabular}{lrr rrr}\toprule
 & \multicolumn{2}{c}{Event change [s]} & \multicolumn{3}{c}{Remaining thickness [mm]}\\
\cmidrule(lr){2-3}\cmidrule(lr){4-6}
Case & Time & Mesh & Time diff. & Mesh diff. & Target\\\midrule
DIFFROWS
\bottomrule\end{tabular}
\caption{Thickness columns give the largest absolute difference on a shared
0.5 s grid up to the first exhaustion. Every row transition was archived, so
sampling uses the retained row count at each comparison time.}
\end{table}
The largest change in event time is MAXPCT percent of the finer calculation.
THICKPASS of eight comparisons meet the intermediate-thickness target and
BRACKETPASS of eight pairs have overlapping final-event brackets.
Both sustainer pairs miss the 0.047625 mm target. Both booster pairs meet
their 0.0635 mm target on the shared grid and over the full common history.
Halving the step advances the event in all four cases, while doubling the
mesh count delays it. Comparing only the first and third columns would
partially cancel those effects. Each row retains its full thermal capacity during partial consumption
until its residual-mass criterion removes it. The moving-wall treatment instead tracks the face continuously.

A separate thin-coupon test paused the independent worker after the second row
loss and casing flag. A fresh controller then recovered the same complete
history, final-event bracket and byte-identical terminal checkpoint as uninterrupted
integration. The audit reconstructs final mass from the saved states, checks each row
transition, and matches source and input fingerprints across all twelve records.
Maximum cumulative relative mass error is MASSERR. Maximum relative residual
of the inherited discrete step energy equation is ENERGYERR. The new material
and wall equations below use a separate open-system energy ledger.
The 585-node native conduction results and moving-wall benchmarks appear in Section~\ref{sec:nativebench}. Whole-exposure MAPDL verification is ongoing.
Measured heating and recession, high-temperature backing data and sensitivity
to surface chemistry remain necessary for the physical interpretation.

\clearpage
\input{continuous_moving_balance.tex}
\paragraph{Reference for the method.}
Chen and Milos describe a moving-grid treatment of decomposition, energy and
surface balances for a charring ablator. Their PICA data apply to a different
material and environment.
\href{https://ntrs.nasa.gov/citations/20130014432}{NASA NTRS 20130014432}.

\clearpage\appendix\section{Conservative geometry and remapping code}
Below is the complete independent geometry kernel. The accompanying
\href{https://github.com/MDNich/MIT-RT-26_27-Work/tree/main/simulation_work/solidprop/iris/v1/model}{model directory}
contains the bulk reaction, boundary and conduction implementations and
their verification programs.
\lstinputlisting[language=Python]{../../model/moving_surface_remap.py}
\clearpage\section{Native continuous-exposure inputs}
The complete entry deck for the aluminium pilot below checks the controller
and configuration before transferring control to the solver's embedded Python
interpreter. The four complete exposures use the same controller archive.
Each macro-step generates a conventional MAPDL input file, solves one transient
thermal field and exports every node for replay. The previous pulse study's
full Fortran material routine and MAPDL listings are printed in the
\href{https://github.com/MDNich/MIT-RT-26_27-Work/blob/main/simulation_work/solidprop/iris/v1/output/pdf/iris_phenolic_report.pdf}{companion native report}.
Here the Python controller advances chemistry and recession between finite-element
thermal steps.
\lstinputlisting{../../configs/native_verification/whole_sector_r1/pilotwal.inp}
\medskip\noindent\textbf{Sector weights used by the command generator.}\par\smallskip
\lstinputlisting[language=Python,firstline=18,lastline=30,firstnumber=18]{../../model/sector_mapdl.py}
The ANSYS command and element references document the
\href{https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/ans_cmd/Hlp_C_PYTHON_a.html}{in-process Python interface},
\href{https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_SOLID278.html}{SOLID278 heat and film options}, and
\href{https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_MASS71.html}{MASS71 thermal capacitance}.
\clearpage
\subsection*{Complete generator for one thermal step}
\lstinputlisting[language=Python,firstline=33,lastline=86,firstnumber=33]{../../model/sector_mapdl.py}
\end{document}
'''
    fields = dict(DATE=date, EVENTROWS='\n'.join(event_rows), DIFFROWS='\n'.join(diff_rows),
                  MAXPCT=f'{largest_pct:.2f}', THICKPASS=str(t_pass), BRACKETPASS=str(bracket_pass),
                  MASSERR=f"{max(e['cumulative_mass_relative_residual'] for e in audit['records'].values()):.3g}",
                  ENERGYERR=f"{max(e['max_step_equation_energy_residual'] for e in audit['records'].values()):.3g}")
    for key, value in fields.items():
        text = text.replace(key, value)
    source = ROOT/'docs/en/iris_continuous_heating_progress.tex'
    source.write_text(text)
    build = ROOT/'ansystmp/continuous_report_build'
    build.mkdir(exist_ok=True)
    for _ in range(2):
        subprocess.run(['/Library/TeX/texbin/pdflatex','-interaction=nonstopmode','-halt-on-error',
                       '-output-directory',str(build),source.name], cwd=source.parent,check=True,stdout=subprocess.DEVNULL)
    target = ROOT/'output/pdf/iris_continuous_heating_progress.pdf'
    target.write_bytes((build/target.name).read_bytes())
    for path in [source, ROOT/'docs/en/continuous_moving_balance.tex',Path(__file__),
                 ROOT/'model/moving_surface_remap.py',ROOT/'docs/analysis/continuous_heating_refinement.pdf']:
        inputs[str(path.resolve().relative_to(ROOT))] = digest(path)
    atomic(ROOT/'validation/continuous_report_inputs.json',dict(built_at=date,inputs=inputs,pdf_sha256=digest(target),
           qualification='Independent moving-wall numerical and assumed-input comparisons plus historical finite-row evidence; visual review pending.'))
    print(target)


if __name__ == '__main__':
    main()
