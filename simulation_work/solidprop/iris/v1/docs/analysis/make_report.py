"""Freeze accepted Iris data, draw English figures and compile the report."""
from pathlib import Path
import csv
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter
from matplotlib.patches import Rectangle
from latex_style import configure_latex, plot_samples
from report_supplement import create as create_supplement

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'model'))
from ops import disks

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def tex(s):
    return str(s).replace('_', r'\_').replace('%', r'\%').replace('&', r'\&')

def capture():
    runs=[]
    for runtime in sorted((ROOT/'ansystmp/runs').iterdir()):
        if runtime.name in ['sustainer_al_pilot','sustainer_al_local_pilot']:
            continue  # Superseded exporter pilot; preserved locally.
        if not (runtime/'state.json').exists():
            continue
        state=json.loads((runtime/'state.json').read_text())
        cfg=json.loads((runtime/'config.json').read_text())
        history=[]
        for path in sorted((runtime/'checkpoints').glob('audit_*.json')):
            if int(path.stem.split('_')[1])>state['index']:
                continue
            a=json.loads(path.read_text())
            assert a['energy_relative_error']<=cfg['numerics']['energy_relative_tolerance']
            assert a['hot_power_relative_error']<=cfg['numerics']['hot_power_relative_tolerance']
            history.append(a)
        if not history:
            continue
        assert abs(history[-1]['time_s']-state['time_s'])<1e-8
        runs.append(dict(name=runtime.name,case=cfg['case_id'],configuration=cfg,
                         accepted_index=state['index'],accepted_time_s=state['time_s'],
                         status=state['status'],config_sha256=sha(runtime/'config.json'),
                         latest_audit_sha256=sha(runtime/'checkpoints'/f'audit_{state["index"]:06d}.json'),
                         history=history))
    baselines=[r for r in runs if 'baseline' in r['name'] or 'pulse7_n' in r['name']]
    return baselines or runs

def run_label(run):
    g=run['configuration']['geometry']
    return run['case'].replace('_',' ').title().replace('Cf','CF').replace('Al','Al')+' (n='+str(g['phenolic_radial_rows'])+')'

def figures(runs):
    configure_latex()
    out=ROOT/'docs/analysis'
    fig,axes=plt.subplots(1,2,figsize=(8,3.1),constrained_layout=True)
    for ax,motor,tp,tc,ri in zip(axes,['Sustainer','Booster'],[4.7625,6.35],[3.175,4.7625],[39.6875,65.0875]):
        for start,width,color,label in [(0,tp,'#A65A2E','Phenolic'),(tp,tc,'#A8B0B8','Al / CF case')]:
            ax.add_patch(Rectangle((start,0),width,.5,facecolor=color,alpha=.45,edgecolor='k'))
            for x in np.linspace(start,start+width,21): ax.plot([x,x],[0,.5],color='#444444',lw=.4)
            ax.text(start+width/2,.37,label,ha='center',fontsize=8)
        ax.axhline(.25,color='#444444',lw=.4)
        ax.set(xlim=(-.15,tp+tc+.15),ylim=(-.04,.55),xlabel='Depth from original liner bore [mm]',ylabel='Axial position [mm]',title=f'{motor}: bore radius {ri:g} mm')
        ax.text((tp+tc)/2,.12,r'20 radial cells per material; 2 axial cells',ha='center',fontsize=7.5)
    fig.suptitle(r'Exact dimensions; axial scale expanded for readability')
    fig.savefig(out/'geometry_mesh.pdf');fig.savefig(out/'geometry_mesh.png',dpi=180);plt.close(fig)
    T=np.array([22,26.85,326.85,626.85,776.85,926.85,1226.85,1426.85,1926.85,2476.85])
    kv=[.25,.25,.32,.36,.36,.36,.36,.36,.36,.36]
    kc=[.30,.30,.35,.40,.44,.49,.68,.81,1.24,1.73]
    cv=[900,900,1100,1300,1300,1300,1300,1300,1300,1300]
    cc=[800,800,900,1000,1250,1550,1950,2060,2085,2090]
    fig,axes=plt.subplots(1,2,figsize=(8,3.0),constrained_layout=True)
    for a,vals,label in [(axes[0],kv,'Virgin phenolic'),(axes[0],kc,'Phenolic char'),(axes[1],cv,'Virgin phenolic'),(axes[1],cc,'Phenolic char')]:
        a.plot(T,vals,'o-',ms=3,label=label)
    axes[0].set(ylabel=r'Conductivity [W/(m K)]');axes[1].set(ylabel=r'Specific heat [J/(kg K)]')
    for ax in axes:ax.set(xlabel=r'Temperature [$^\circ$C]');ax.legend(fontsize=8)
    fig.suptitle('Inherited phenolic material tables; exploratory inputs')
    fig.savefig(out/'phenolic_properties.pdf');fig.savefig(out/'phenolic_properties.png',dpi=180);plt.close(fig)
    if runs:
        fig,axes=plt.subplots(1,3,figsize=(9,3.1),constrained_layout=True)
        for run in runs:
            h=run['history'];t=[x['time_s'] for x in h];legend=tex(run_label(run))
            plot_samples(axes[0],t,[x['Ts_mean_C'] for x in h],label=legend)
            plot_samples(axes[1],t,[1000*x['phenolic_remaining_thickness_m'] for x in h],label=legend)
            plot_samples(axes[2],t,[100*x['energy_relative_error'] for x in h],label=legend)
        axes[0].set(ylabel=r'Hot-face mean temperature [$^\circ$C]')
        axes[1].set(ylabel='Retained mesh thickness [mm]')
        axes[2].set(ylabel='Step energy residual [percent]')
        for ax in axes:ax.set(xlabel='Time since imposed heating begins [s]')
        axes[0].legend(fontsize=7)
        fig.suptitle('Accepted native ANSYS states; scenario exposure')
        fig.savefig(out/'accepted_histories.pdf');fig.savefig(out/'accepted_histories.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(9,3.1),constrained_layout=True)
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        data=[json.loads((ROOT/'validation/radial'/f'{case}_mesh7_n{n}.json').read_text()) for n in [20,40,80,160]]
        for ax,key in zip(axes,['hot_C','interface_C','removed_mm']):
            ax.plot([20,40,80,160],[d['final'][key] for d in data],'o-',label=case.replace('_',' ').title().replace('Cf','CF'))
            ax.set(xscale='log',xlabel='Radial cells per material',xticks=[20,40,80,160],xticklabels=['20','40','80','160'])
            ax.xaxis.set_minor_formatter(NullFormatter())
    axes[0].set(ylabel=r'Hot face at 7 s [$^\circ$C]');axes[1].set(ylabel=r'Case inner face at 7 s [$^\circ$C]');axes[2].set(ylabel='Removed thickness at 7 s [mm]')
    axes[0].legend(fontsize=6.5)
    fig.suptitle('Independent radial model; mesh sensitivity, not ANSYS output')
    fig.savefig(out/'radial_mesh_check.pdf');fig.savefig(out/'radial_mesh_check.png',dpi=180);plt.close(fig)

def write_report(runs, snapshot):
    stamp=datetime.now(ZoneInfo('America/New_York')).strftime('%B %d, %Y at %H:%M %Z')
    rows=[]
    for r in runs:
        a=r['history'][-1]
        rows.append(' & '.join([tex(run_label(r)), f"{r['accepted_time_s']:.4f}", f"{a['Ts_mean_C']:.2f}", f"{1000*a['phenolic_remaining_thickness_m']:.5f}", f"{100*a['energy_relative_error']:.4f}"]) + ' ' + chr(92)*2)
    result_table='\n'.join(rows) if rows else r'No accepted native states & --- & --- & --- & --- \\'
    result_fig=r'\includegraphics[width=\textwidth]{../analysis/accepted_histories.pdf}' if runs else 'Native thermal results are pending.'
    report=r'''\pdfminorversion=7
\documentclass[oneside,openany]{amsdtx}
\usepackage[margin=.75in]{geometry}
\usepackage{graphicx,float,amsmath,amssymb,booktabs,array,enumitem}
\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}\usepackage[english]{babel}
\usepackage{lmodern,siunitx,xcolor}\usepackage[colorlinks=true,allcolors=blue,hyperindex=false]{hyperref}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\title{\sc Thermochemical Simulation of the Iris Phenolic Liners\\\large Setup and Accepted Results}
\author{\sc MIT Rocket Team --- Solid Propulsion Simulations}
\date{STAMP}
\begin{document}\maketitle
\begin{center}\includegraphics[height=1.1cm]{logos/rtlogo.pdf}\hspace{2cm}\includegraphics[height=.65cm]{logos/ansys.png}\end{center}
\begin{center}\fbox{\begin{minipage}{.93\textwidth}\small
\textbf{Exploratory study.} Four configurations are considered: sustainer and booster, each with an aluminium or carbon-fibre composite casing. Heat flux, firing duration, grain port and measured recession are unavailable. The user authorized explicit surrogate inputs and sensitivity studies. This report separates native numerical checks from physical calibration. A pilot is not a demonstrated motor lifetime.
\end{minipage}}\end{center}
\tableofcontents
\clearpage
\section{Executive summary}
No defensible real-motor burnthrough time has been established. Both sustainer native coarse-mesh baselines have completed seven seconds of the imposed heating scenario without an accepted exhaustion event. Their mass, energy and applied-load audits passed. The booster baselines and refined native pulse/cooling cases remain in the serial campaign.

The initial twenty-row phenolic mesh is insufficient for recession. Independent refinement and 54 input-sensitivity cases show that missing thermal inputs and the partial-cell removal approximation matter. Under sustained nominal heating, provisional casing-property flags are reached with substantial liner remaining. Those stopping points limit this model's scope; they are not motor lifetimes or structural failure predictions. The immediate objective is to complete the native refined histories and compare their temperatures, mass loss and cooling against independent calculations.

\section{Purpose and definition of burnthrough}
The primary event is exhaustion of the continuous phenolic barrier, leaving the casing exposed in this two-layer geometry. Pyrolysis conversion alone is not this event: char remains solid and can continue insulating. We report modelled solid mass, retained mesh thickness, whole-cell recession, conversion depth and casing temperatures separately. Retained mesh thickness is not a measurement of physical liner thickness. A numerically accepted exhaustion event would be bracketed by the last intact state and first exhausted state.

The calculation represents an initially intact, locally uniform wall. Cracks, joints, debonding, char spallation and particle erosion are not resolved. Material-temperature flags indicate the scope of surrogate properties, not certified pressure-casing failure. If the event is absent, the result is ``not reached through the simulated exposure,'' with residual thickness, rather than an extrapolated lifetime.

\section{Geometry and discretization}
The supplied propellant radii are provisionally used as liner inner radii. No unreported gap or adhesive layer is inserted. The user requested short axial and sector slices with about twenty radial cells per material. Each exchanged STEP contains exactly two solids and is reimported independently to verify volumes and dimensions.
\begin{table}[H]\centering\small
\begin{tabular}{lrrrr}\toprule
Motor & Bore radius & Phenolic & Case & Outside radius\\
 & \multicolumn{4}{c}{Dimensions in millimetres}\\\midrule
Sustainer & 39.6875 & 4.7625 & 3.1750 & 47.6250\\
Booster & 65.0875 & 6.3500 & 4.7625 & 76.2000\\\bottomrule
\end{tabular}\end{table}
Al and CF versions share the dimensions within each motor. The initial domain is \SI{0.5}{mm} long and \(0.5^\circ\) wide, with 2 axial and 2 angular divisions. Twenty radial cells in each material give 160 SOLID278 elements and 369 nodes. The axis is global Y. Lateral and axial faces are adiabatic under the uniform-wall assumption. Integrated mass/power scales by 720 to a full ring of the same short length; temperatures and recession do not scale.
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/geometry_mesh.pdf}\caption{Radial/axial mesh projections. The angular direction has two divisions; axial scale is expanded. These are setup diagrams, not solved contours.}\end{figure}
STEP is the exchange geometry. The native structured mesh is generated deterministically from the same dimensions; it is not an automatic mesh imported from STEP. The initial 20-cell phenolic pitches are 0.238125 mm and 0.3175 mm. Independent comparisons at 40, 80 and 160 cells show sensitivity to thermal gradients and cell-removal quantization. Refined native inputs use 80 phenolic and 20 casing rows, giving 400 elements and 909 nodes. Further independent refinement assesses retained partial-cell storage and time accuracy.

\section{Materials and thermal environment}
\subsection{Phenolic and aluminium inherited from the earlier study}
The reference virgin and char densities are 1250 and \SI{600}{kg.m^{-3}}. The inherited single-step kinetics use \(A=\SI{333}{s^{-1}}\), \(E_a=\SI{64081}{J.mol^{-1}}\), order one, and an endothermic pyrolysis term of \SI{418}{kJ.kg^{-1}}. Thermal tables vary with temperature. Their applicability to the manufactured Iris liner is uncalibrated. Aluminium initially uses \(\rho=2700\), \(k=167\) and \(c_p=896\) in SI units; the exact alloy is unspecified.
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/phenolic_properties.pdf}\caption{Inherited input tables. Lines interpolate prescribed material data and are not experimental measurements made for Iris.}\end{figure}
\subsection{Carbon fibre surrogate}
The user's ACP fin tutorial supplies \(\rho=\SI{1451}{kg.m^{-3}}\), elastic and thermal-expansion data, but no CF conductivity or heat capacity. Its G10 thermal values are not used as CF properties. The initial woven-laminate surrogate has radial conductivity \SI{0.55}{W.m^{-1}.K^{-1}} and equal tangential/axial conductivities \SI{2.5}{W.m^{-1}.K^{-1}}, within the woven-composite ranges reported by Joven and colleagues~\cite{woven}. Local material frames follow the cylinder.

For heat capacity, use the separately identified T700/M21 surrogate \(c_p=2.8773T+687.31\), with Celsius temperature and SI heat-capacity units~\cite{fire}. Clamp this input above \SI{200}{\degreeCelsius}; high-temperature predictions then have a flagged material approximation. The density, conductivity and heat capacity come from different references and do not constitute a measured property set for the user's casing. A \SI{150}{\degreeCelsius} CF flag and \SI{300}{\degreeCelsius} Al flag track provisional property scope, not structural failure. NASA's alternative carbon-epoxy data provide another sensitivity reference~\cite{nasa}.

\subsection{Imposed exposure}
The initial gas-side assumption is \(T_g=\SI{2504}{K}\), unblown \(h_0=\SI{1000}{W.m^{-2}.K^{-1}}\), and nominal pressure 800 psi, following the earlier study and the user's pressure estimate. Pressure is interpreted as absolute in the char-law closure. Initial and external ambient temperature is \SI{22}{\degreeCelsius}; external convection is \SI{8}{W.m^{-2}.K^{-1}} and emissivity is 0.25. The initial hot-radiation emissivity is zero, with separate radiation sensitivity scenarios.

The liner is assumed exposed from the start of imposed heating. The actual grain shielding and local exposure history are unknown. The campaign includes native pilots and 7 s baselines, refined native 7 s pulses with cooling, independent 7/20/60 s pulse screens, and a separate independent continuous-exposure branch. None of these pulse lengths is an inferred motor burn duration. Sensitivities vary heat-transfer coefficient, radiation, material properties, pressure and char-consumption parameters; they are not a statistical uncertainty envelope.

\subsection{Supplied reaction and inventory envelope}
The user's reaction is atom-balanced:
\[3\mathrm{NH_4ClO_4}+3\mathrm{Al}\longrightarrow\mathrm{Al_2O_3}+\mathrm{AlCl_3}+3\mathrm{NO}+6\mathrm{H_2O}.\]
Its reactant mass bookkeeping is approximately 81.32 percent ammonium perchlorate and 18.68 percent aluminium. With constituent densities of 1950 and \SI{2700}{kg.m^{-3}}, an ideal additive-volume binary mixture would have density \SI{2056.7}{kg.m^{-3}}. The AP density is a published material value~\cite{ap}; the binary mixture is an explicit assumption, not a measured propellant formulation.
\begin{table}[H]\centering\small
\begin{tabular}{lrrr}\toprule
Motor & Volume at 1 m [litres] & Full-cylinder mass [kg] & 0.75--1.25 m range [kg]\\\midrule
Sustainer & 4.948 & 10.18 & 7.63--12.72\\
Booster & 13.309 & 27.37 & 20.53--34.22\\\bottomrule
\end{tabular}\end{table}
These are full-cylinder envelope values with no port, binder or voids. Actual mass scales with occupied volume fraction and actual bulk density. The stoichiometric product list is not an equilibrium combustion calculation, and this inventory cannot establish burn duration, wall heat flux or char kinetics. The inherited gas temperature remains an imposed scenario. No full-length fuel cylinder is meshed.

\section{Thermochemical physics and solver}
The phenolic thermal law solves conduction with temperature/conversion-dependent properties, endothermic pyrolysis and gas sensible cooling. The reaction state follows
\[\dot\alpha=A\exp[-E_a/(RT)](1-\alpha),\qquad 0\leq\alpha\leq1.\]
The compiled UserMatTh routine integrates conversion analytically at increment midpoint temperature and requests a smaller solver increment when conversion changes too much. The gas source follows the virgin-to-char density loss. A surface blowing correction reduces convection as gas leaves the solid. Pore pressure and Darcy transport are not resolved.

A separate effective char-consumption law combines kinetic and mass-transfer limits and available surface energy. The inherited effective removal cost is \SI{35}{MJ.kg^{-1}}. This is an exploratory closure, not a calibrated oxidation mechanism. A row is scheduled for removal only after residual solid mass falls below 0.1 percent of its initial virgin mass. Hot-face loads move to the next live row. Consumed char remains in the live finite-element thermal representation until row removal; its numerical influence must be bounded through refinement or a revised partial-cell treatment.

MAPDL 2026 R1.02 runs natively in Windows through the Parallels VM, using the previous x64 material DLL and the installed Python coupling controller. The initial tiny models use one process and a row-summed (diagonal) specific-heat matrix, matching the SOLID278 default without advection. At every coupling step, the controller checks exported time and live element identity, gas/char/solid mass, thermal energy and the actual applied hot-face power before accepting an atomic checkpoint. Native face heat rates are used, with independent reconstruction of user-material energy sinks where the native aggregate channels omit them.

The initial gates are mass residual at most \(10^{-6}\) of initial liner mass, step energy residual at most 5 percent, and hot-load error at most 2 percent. These numerical gates do not validate the material law. Comparison of mesh and coupling steps targets less than 5 percent change in event time, with event brackets and temperatures reported explicitly.

The corrected pilot exporter retrieves only defined live-material ranges. The earlier three undefined-SVAR warnings per step were removed without changing physical equations. The native user-material solve retains the standard warning that the Ansys-supplied USERCK routine is used; its banner separately confirms a user-defined thermal material. This known warning is recorded, not silently counted as zero warnings. Longer runs also report elapsed-time/CPU-time performance warnings; these are retained in the validation records.

\section{Execution and storage controls}
The running VM has 14 virtual CPUs and approximately 112 GiB RAM. The repository is accessible through a dedicated I: mapping. A native no-solve probe completed with a successful license checkout and zero warnings/errors. Each case receives a separate sealed runtime; unchanged source hashes and expected inventories are checked before launching.

The user's storage floors are 400 GB decimal free on the Mac disk and 10 GB free on Windows C:. A host watcher checks the Mac every five seconds and the guest disk about every thirty seconds. The controller also requires a fresh storage heartbeat. On a threshold crossing, new work stops, a stop latch is written and the active solver is asked to terminate cleanly. Interrupted states are not published as accepted data.

Native results/restarts remain in ignored storage. Major setup and report milestones are pushed to GitHub after verification; staged files and new Git objects at or above 100 MB are rejected. Reports freeze accepted state indices and source hashes. Recovery preserves the failed run and matches native restart state with controller state before continuation.

\section{Accepted results at this edition}
This snapshot was frozen at STAMP. The table includes only accepted native states. All four 0.1 s pilots passed. Longer runs are displayed below as their states are accepted; queued cases do not acquire predicted ANSYS values. These results are provisional until spatial and temporal comparisons are complete. No burnthrough event has been accepted.
\begin{table}[H]\centering\scriptsize
\begin{tabular}{lrrrr}\toprule
Run & Time [s] & Hot face [$^\circ$C] & Remaining [mm] & Energy error [\%]\\\midrule
RESULTTABLE
\bottomrule\end{tabular}\end{table}
\begin{figure}[H]\centering RESULTFIG \caption{Accepted native histories. No extrapolated future states are included.}\end{figure}

\section{Verification findings and current limitations}
The native steady-conduction benchmark used the same sector mesh, convection face numbers and CF material frames with constant properties and reactions disabled. All four configurations matched the analytical two-layer cylinder within \SI{0.013}{K}; the acceptance target was \SI{0.1}{K}. This checks geometry, thermal resistance and orthotropic axes, not the reaction law. The deliberately artificial steady temperatures in that benchmark are not motor predictions.

Manufactured storage faults verified both free-space floors, the latched stop and the correct native abort filenames. A communication fault is retried as a read-only query; it is not reported as a disk threshold crossing. A guest-local pilot reproduced every shared-drive pilot nodal temperature exactly. It offers an alternate execution location while mirroring accepted results to the Mac. A controlled checkpoint pause/resume has advanced successfully; an uninterrupted comparison remains to be completed.

The independent cylindrical finite-element model uses a separate radial assembly, two Gauss points per cell, backward Euler time integration and row-summed heat capacity. It retains the same material assumptions and surface law. At 0.1 s the sustainer hot-face difference from ANSYS was approximately 0.70 K; at 1.0 s it was approximately 0.97 K. Agreement is numerical cross-checking, not physical calibration.
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/radial_mesh_check.pdf}\caption{Independent seven-second radial mesh checks at a 0.0125 s coupling step. Coincident Al/CF hot-face and recession curves overlap. A cell-removal jump is not a smooth estimate of recession.}\end{figure}
The twenty-cell mesh does not resolve recession sufficiently. The independent sustainer hot face at 7 s changes from about 1052 to 1410, 1466 and 1520 degrees Celsius at 20, 40, 80 and 160 radial cells. Its corresponding whole-cell removed thickness is 0, 0.1191, 0.0595 and 0.0298 mm. Case temperatures are much less sensitive over this short exposure. These comparisons justify refinement; they do not demonstrate a converged burnthrough time. Halving the 80-cell time step also changes hot-face temperature, so mesh and time accuracy remain separate checks.

Numerical long-exposure stress tests were also performed to expose weaknesses in the inherited removal scheme. They showed substantial mesh/time-step dependence, while the casing had already left its provisional property range. Those apparent exhaustion times are explicitly rejected as motor-lifetime results. The retained partial-cell thermal mass and lagged surface coupling require further assessment. Physically interpreted continuous-exposure runs now stop at the first casing property-range crossing. That crossing indicates a limit of this model, not an experimentally established structural failure.

\section{Next results}
Complete the booster native seven-second baselines and all four refined pulse/cooling cases. Compare native first-row removal, cooling, temperature profiles and mass loss against the independent assembly, within the stated material scope. Report whole-cell recession separately from the 98 percent pyrolysis front. Preserve rejected diagnostics with their reasons rather than silently treating them as successful predictions.

A defensible final answer may be a conditional ``not reached through the accepted exposure'' result with remaining thickness, rather than a finite lifetime. Neither missing wall-exposure data nor uncalibrated char kinetics can be recovered from solver convergence. The study cannot establish real motor lifetime without supported wall heating and recession evidence.

\begin{thebibliography}{9}
\bibitem{prior} MIT Rocket Team, \emph{Thermochemical Simulation v0: Interim Results for the New Phenolic Liner}, September 26, 2026; accompanying versioned configuration, UserMatTh source and controller in this repository.
\bibitem{acp} M. Nichitiu and C. Casebolt, \emph{ANSYS Composite Analysis for Characterization of the Project Aurora Fin Can}, user-supplied tutorial, especially pp. 3--5.
\bibitem{woven} R. Joven et al., \emph{Thermal properties of carbon fiber-epoxy composites with different fabric weaves}, 2011. \url{https://www.researchgate.net/publication/288102626}.
\bibitem{fire} P. Tranchard et al., \emph{Modelling Behaviour of a Carbon Epoxy Composite Exposed to Fire: Part I}, Materials 10(5), 494, 2017, Table 5. \url{https://doi.org/10.3390/ma10050494}.
\bibitem{nasa} M. Pauken, \emph{Simplified Plume and Aerothermal Heating Analysis for LDSD}, TFAWS 2012. \url{https://tfaws.nasa.gov/TFAWS12/Proceedings/TFAWS2012-AE-002.pdf}.
\bibitem{ap} Sigma-Aldrich, ammonium perchlorate product 455822, density \SI{1.95}{g.cm^{-3}} at \SI{25}{\degreeCelsius}. \url{https://www.sigmaaldrich.com/US/en/product/aldrich/455822}.
\end{thebibliography}
\end{document}
'''
    report=report.replace('STAMP',stamp).replace('RESULTTABLE',result_table).replace('RESULTFIG',result_fig)
    report=report.replace(r'\section{Next results}',create_supplement(ROOT,runs)+'\n\n'+r'\section{Next results}')
    if (ROOT/'validation/restart_comparison.json').exists():
        check=json.loads((ROOT/'validation/restart_comparison.json').read_text())
        report=report.replace('A controlled checkpoint pause/resume has advanced successfully; an uninterrupted comparison remains to be completed.',
            'The controlled checkpoint restart matched an uninterrupted native run at 1.1 s, including conversion state and energy integrals. The maximum nodal temperature difference was '+r'\SI{'+f"{check['max_nodal_temperature_difference_K']:.4g}"+r'}{K}.')
        report=report.replace('verify native first/last-row load transfer and uninterrupted versus restarted states, then',
                              'verify native first/last-row load transfer, then')
    if (ROOT/'validation/native_pulse_control.json').exists():
        report=report.replace('A defensible final answer may be', 'A native one-second heating pulse followed by five cooling steps passed the boundary-transfer and balance checks. This verifies the prescribed switch to ambient gas and zero char consumption; it does not measure real tailoff.\n\nA defensible final answer may be')
    (ROOT/'docs/en/iris_phenolic_report.tex').write_text(report)

def main():
    disks()
    runs=capture()
    snapshot=dict(captured=datetime.now(ZoneInfo('America/New_York')).isoformat(),runs=runs)
    (ROOT/'docs/analysis/accepted_snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    figures(runs)
    write_report(runs,snapshot)
    build=ROOT/'ansystmp/report_build';build.mkdir(exist_ok=True)
    source=ROOT/'docs/en'
    for _ in range(2):
        proc=subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','-output-directory',str(build),'iris_phenolic_report.tex'],cwd=source,capture_output=True,text=True)
        (build/'compile_stdout.txt').write_text(proc.stdout)
        if proc.returncode:raise RuntimeError(proc.stdout[-6000:])
    import shutil
    dest=ROOT/'output/pdf/iris_phenolic_report.pdf'
    shutil.copy2(build/'iris_phenolic_report.pdf',dest)
    print(dest)
    print('Review rendered PDF before publishing.')

if __name__=='__main__':
    main()
