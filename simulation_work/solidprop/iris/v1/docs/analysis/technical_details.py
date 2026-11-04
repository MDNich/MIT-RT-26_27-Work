"""Document the executed laws and source; never modify or launch a native run."""
from pathlib import Path
import gzip
import hashlib
import json
import shutil
import numpy as np
import matplotlib.pyplot as plt
from latex_style import CASE_COLORS, configure_latex


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def title(case):
    return case.replace('_', ' ').title().replace('Cf', 'CF')


def temperature_section(root, runs):
    """Freeze existing audited hot-face results, not future or radial predictions."""
    configure_latex()
    out = root/'docs/analysis'
    records = []
    fig, axes = plt.subplots(2, 2, figsize=(8.4, 5.5), constrained_layout=True)
    profiles, pax = plt.subplots(1, 2, figsize=(8.4, 3.1), constrained_layout=True)
    for col, motor in enumerate(('sustainer', 'booster')):
        axes[0, col].axhline(2230.85, color='black', ls='--', label='Imposed gas: 2230.85 C')
        for run in [r for r in runs if r['case'].startswith(motor)]:
            c = run['configuration']; g = c['geometry']; h = run['history']
            native = json.loads((root/'validation'/f'accepted_{run["name"]}.json').read_text())
            assert native['passed'] and native['accepted_steps'] == run['accepted_index']
            heating = [a for a in h if a['time_s'] <= 7+1e-8]
            end = heating[-1]; assert abs(end['time_s']-7)<1e-8
            peak = max(heating, key=lambda a: a['Ts_mean_C'])
            casepeak = max(h, key=lambda a: a['case_inner_max_C'])
            t = [0.] + [a['time_s'] for a in heating]
            style = dict(color=CASE_COLORS[run['case']], ls='--' if run['case'].endswith('cf') else '-')
            axes[0, col].plot(t, [22.] + [a['Ts_mean_C'] for a in heating], label=title(run['case'])+' hot face', **style)
            axes[1, col].plot(t, [22.] + [a['case_inner_max_C'] for a in heating], label=title(run['case'])+' casing', **style)
            idx = int(end['native_load_step'])
            path = root/'ansystmp/runs'/run['name']/'checkpoints'/f'state_{idx:06d}.json.gz'
            with gzip.open(path, 'rt') as stream:
                s = json.load(stream)
            plane = (g['axial_divisions']+1)*(g['angular_divisions']+1)
            nphe = g['phenolic_radial_rows']; ncase = g['aluminium_radial_rows']
            depth = np.r_[np.linspace(0,1000*g['phenolic_thickness_m'],nphe+1),
                          np.linspace(1000*g['phenolic_thickness_m'],1000*(g['outer_radius_m']-g['inner_radius_m']),ncase+1)[1:]]
            temp = [np.mean([s['temperatures'][str(1+j*plane+k)] for k in range(plane)]) for j in range(nphe+ncase+1)]
            temp[:end['rows_removed']] = [float('nan')]*end['rows_removed']
            pax[col].plot(depth, temp, label=title(run['case']), **style)
            assert max(abs(end['hot_power_expected_W']-end['hot_power_actual_W']),0)<1e-5
            # Endpoint convection evaluated with the actual applied coefficient.
            flux = end['h_W_m2_K']*(end['gas_temperature_C']-end['Ts_mean_C'])
            assert abs(flux-end['hot_power_actual_W']/end['area_m2'])/flux<1e-5
            records.append(dict(case=run['case'],runtime=run['name'],config_sha256=run['config_sha256'],
                accepted_record_sha256=sha(root/'validation'/f'accepted_{run["name"]}.json'),
                seven_second_checkpoint_sha256=sha(path), gas_temperature_C=end['gas_temperature_C'],
                hot_surface_mean_at_7s_C=end['Ts_mean_C'],hot_surface_mean_at_7s_K=end['Ts_mean_C']+273.15,
                sampled_heating_hot_surface_mean_peak_C=peak['Ts_mean_C'],sampled_hot_peak_time_s=peak['time_s'],
                casing_inner_max_at_7s_C=end['case_inner_max_C'],
                sampled_casing_inner_max_C=casepeak['case_inner_max_C'],sampled_casing_max_time_s=casepeak['time_s'],
                horizon_completed=run['status']=='COMPLETED_HORIZON',
                film_coefficient_at_7s_W_m2_K=end['h_W_m2_K'],convective_flux_at_7s_W_m2=flux,
                flux_terms_at_7s_W_m2={k:end[k]/end['area_m2'] for k in
                    ['pyrolysis_sink_W','gas_sensible_sink_W','ablation_sink_W','storage_W']},
                heating_samples=[dict(time_s=a['time_s'],Ts_mean_C=a['Ts_mean_C'],case_inner_max_C=a['case_inner_max_C']) for a in heating],
                depth_at_7s_mm=depth.tolist(),radial_temperature_at_7s_C=[v if np.isfinite(v) else None for v in temp]))
        axes[0,col].set(title=motor.title()+': gas and exposed phenolic', xlim=(0,7),ylim=(0,2400),ylabel=r'Temperature [$^\circ$C]')
        axes[1,col].set(title=motor.title()+': casing behind the liner',xlim=(0,7),ylim=(21.5,31),xlabel='Time since start of heating [s]',ylabel=r'Temperature [$^\circ$C]')
        for ax in axes[:,col]: ax.legend(fontsize=7.7,loc='best')
        thickness=4.7625 if motor=='sustainer' else 6.35
        pax[col].axvline(thickness,ls=':',color='#444444',label='Phenolic / case interface')
        pax[col].set(title=motor.title()+': native field at 7 s',xlabel='Depth from original bore [mm]',ylabel=r'Temperature [$^\circ$C]',ylim=(0,1600))
        pax[col].legend(fontsize=7.7)
    fig.suptitle('Heating interval only: exposed liner and casing are different surfaces')
    fig.savefig(out/'temperature_locations_heating.pdf');fig.savefig(out/'temperature_locations_heating.png',dpi=170);plt.close(fig)
    profiles.savefig(out/'temperature_profiles_7s.pdf');profiles.savefig(out/'temperature_profiles_7s.png',dpi=170);plt.close(profiles)
    (out/'temperature_interpretation.json').write_text(json.dumps(dict(qualification='Audited native primary 80/20-row states. Surface means and casing maxima are distinct. No physical calibration or completed spatial convergence is implied.',records=records),indent=2,allow_nan=False)+'\n')
    rows=[]
    for d in records:
        rows.append(f"{title(d['case'])} & {d['sampled_heating_hot_surface_mean_peak_C']:.2f} & {d['sampled_hot_peak_time_s']:.4f} & {d['hot_surface_mean_at_7s_C']:.2f} & {d['casing_inner_max_at_7s_C']:.2f} "+r'\\')
    budget=[]
    for d in records:
        if not d['case'].endswith('_al'):continue
        terms=d['flux_terms_at_7s_W_m2']
        values=[d['convective_flux_at_7s_W_m2']]+[terms[k] for k in ['pyrolysis_sink_W','gas_sensible_sink_W','ablation_sink_W','storage_W']]
        budget.append(title(d['case'])+' & '+' & '.join(f'{v/1e6:.4f}' for v in values)+r'\\')
    text=r'''\section{Interpreting the temperatures: gas, liner surface and casing}
\label{sec:temperature-locations}
\textbf{The exposed phenolic is already at thousands of degrees in absolute temperature.} The accepted primary runs reach approximately 1480--1488 degrees Celsius (1753--1761 K) at their exposed phenolic surface. The much lower 85--150-degree values discussed in the casing results belong to the metal/composite behind the liner, generally during subsequent heat soak. They are not chamber-gas temperatures or peak exposed-liner temperatures. A cool final point on a 127 or 300 s history is not the maximum during the seven-second heating interval.

Moving radially outward, the temperature locations are
\begin{center}
\fbox{Gas $T_g$ (prescribed)} $\ \longrightarrow\ $
\fbox{Exposed phenolic $T_s$ (solved)}\\[5pt]
$\underbrace{\hspace{4cm}}_{\text{4.7625 or 6.35 mm initial liner}}$
$\ \longrightarrow\ $\fbox{Inner casing $T_{ci}$}
$\ \longrightarrow\ $\fbox{Outer casing $T_{co}$}.
\end{center}
The gas is a thermal reservoir at 2504 K (2230.85 degrees Celsius), coupled through a finite heat-transfer coefficient. It is not a temperature constraint applied to the solid. $T_s$ is the area-weighted mean on the currently exposed row, whereas $T_{ci}$ in the tables is the maximum nodal temperature at the fixed liner/casing interface. They differ in location and averaging definition. The sector uniformity checks quantify the small axial/angular spreads.
\begin{table}[H]\centering\small
\begin{tabular}{lrrrr}\toprule
 & Peak $T_s$ & Time of peak & $T_s$ at 7 s & $T_{ci}$ at 7 s\\
Case & $^\circ$C & s & $^\circ$C & $^\circ$C\\\midrule
TEMPERATURE_ROWS
\bottomrule\end{tabular}\caption{Accepted primary native 80/20-row values. Hot-surface peaks are sampled area-weighted means during heating, not the prescribed gas temperature. Spatial convergence remains in progress.}\end{table}
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/temperature_locations_heating.pdf}\caption{The same heating interval plotted at the exposed phenolic and the liner/casing interface. The lower panels deliberately use a much smaller temperature scale. Al/CF hot-face curves nearly coincide during the short exposure.}\end{figure}
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/temperature_profiles_7s.pdf}\caption{Native radial-station averages at the last heated state. Inactive original-bore nodes are excluded. The steep temperature gradient lies inside the phenolic; the casing remains much cooler during firing and warms later. These are finite-mesh fields, not measured temperatures.}\end{figure}

\subsection{Why a 2504 K gas does not impose a 2504 K liner}
At 7 s, the sustainer hot surface is about 1466 degrees Celsius and its applied film coefficient is about 923 W/(m$^2$ K). Their product $h_{\rm eff}(2230.85-T_s)$ gives approximately 0.706 MW/m$^2$ of convection into the surface. Booster values give about 0.717 MW/m$^2$. This was checked against the actual native face heat rates. The small absolute powers in the short-sector records are a consequence of the small area, not a weak heat flux.
\begin{table}[H]\centering\small
\begin{tabular}{lrrrrr}\toprule
 & Convection & Pyrolysis & Gas sensible & Char cost & Capacity\\
 & inward & sink & sink & sink & rate\\
Case & \multicolumn{5}{c}{MW/m$^2$ of exposed hot area, at 7 s}\\\midrule
BUDGET_ROWS
\bottomrule\end{tabular}\caption{Whole-domain power terms divided by current hot area. Volumetric sinks and capacity are integrated through the domain; this table is not a local partition at one integration point. Exterior losses and the small discrete residual complete the balance.}\end{table}
Heat is consumed by decomposition and the specified gas/char sinks while the remaining energy heats the solid and conducts outward. A rough initial virgin diffusivity is $k/(\rho c_p)=0.25/(1250\times900)=2.22\times10^{-7}\ \mathrm{m^2/s}$; its seven-second diffusion length $\sqrt{at}$ is about 1.25 mm, compared with 4.76 or 6.35 mm of initial liner. This is only an order-of-magnitude explanation of the delayed casing response: properties and the thermal front evolve, so it is not a substitute for the nonlinear calculation.

\subsection{Comparison with the attached earlier documentation}
The September 18 report~\cite{phenolicseptember}, Table 6 on page 11, reports a hot-surface maximum of 1755.39 degrees Celsius at 6.3856 s while the aluminium maximum remains 22.0012 degrees Celsius. Its Simulation 2 reports a 1644.11-degree maximum at 6.45 s. Thus the earlier documentation also separates a very hot exposed liner from a much cooler casing. Those cases used a different four-layer construction, and Simulations 1 and 2 used the documented oversized radial geometry. Simulation 1 also lacked the later outgassing/consumption terms. They are not same-geometry temperature benchmarks for Iris.

The corrected thin-sector Simulation 3 in that report reached a peak of 1400.50 degrees Celsius and ended at 435.36 degrees after row transfers; those historical quantities use their own deletion rule and do not calibrate the present model. The later September 26 two-layer v0 study is the principal implementation ancestor of Iris. The current source uses its density/char formulation with explicit numerical corrections, not a verbatim reuse of every earlier model.

The present hot face is therefore not accidentally set to approximately 100 degrees Celsius. However, this does not demonstrate that its predicted temperature is physically correct. Actual heating, hot radiation, propellant shielding, tailoff, material properties and char removal remain uncalibrated. The retained hot-surface peaks and row-transfer jumps are also mesh/time dependent. The current 80-row primary fields should not be called final converged surface temperatures. The refinement and input-sensitivity sections quantify what has been checked without forcing a temperature to match an expectation.
'''
    text=text.replace('TEMPERATURE_ROWS','\n'.join(rows)).replace('BUDGET_ROWS','\n'.join(budget))
    # A passing casing time check must not conceal a hot-face discrepancy.
    resolution=[]
    for run in runs:
        name=run['case']+'_pulse7_midpoint_time_quarter'
        ap=root/'validation'/f'accepted_{name}.json'
        cp=root/'validation'/f'native_pulse_comparison_{name}.json'
        if not ap.exists() or not cp.exists():continue
        accepted=json.loads(ap.read_text());comparison=json.loads(cp.read_text())
        if not accepted['passed'] or not comparison['comparison_passed']:continue
        assert accepted['accepted_steps']==comparison['accepted_native_index']
        fine=[json.loads(p.read_text()) for p in sorted((root/'ansystmp/runs'/name/'checkpoints').glob('audit_*.json'))
              if int(p.stem.split('_')[-1])<=accepted['accepted_steps']]
        coarse=[a for a in run['history'] if a['time_s']<=7+1e-8]
        fine=[a for a in fine if a['time_s']<=7+1e-8]
        assert abs(fine[-1]['time_s']-7)<1e-8
        lookup={round(a['time_s'],8):a for a in fine}
        diffs=[(abs(a['Ts_mean_C']-lookup[round(a['time_s'],8)]['Ts_mean_C']),a['time_s']) for a in coarse]
        maxdiff,when=max(diffs)
        resolution.append(dict(case=run['case'],fine_runtime=name,accepted_sha256=sha(ap),comparison_sha256=sha(cp),
            primary_Ts_at_7s_C=coarse[-1]['Ts_mean_C'],quarter_Ts_at_7s_C=fine[-1]['Ts_mean_C'],
            difference_at_7s_K=fine[-1]['Ts_mean_C']-coarse[-1]['Ts_mean_C'],
            primary_hot_peak_C=max(a['Ts_mean_C'] for a in coarse),quarter_hot_peak_C=max(a['Ts_mean_C'] for a in fine),
            max_matched_heating_difference_K=maxdiff,max_difference_time_s=when))
    if resolution:
        text+=r'''\subsection{Completed native time check: the hot face still needs refinement}
The completed quarter-step comparisons keep the same 80/20-row geometry and physical inputs. Each passes the native audits and its same-mesh independent check. The separate casing-peak or material-scope timing criteria do not establish a time-converged hot-face history.
\begin{table}[H]\centering\small
\begin{tabular}{lrrrr}\toprule
 & \multicolumn{2}{c}{$T_s$ at 7 s [$^\circ$C]} & Change & Maximum matched\\
Case & Primary & Quarter step & K & heating difference [K]\\\midrule
'''
        for d in resolution:
            text+=f"{title(d['case'])} & {d['primary_Ts_at_7s_C']:.2f} & {d['quarter_Ts_at_7s_C']:.2f} & {d['difference_at_7s_K']:.2f} & {d['max_matched_heating_difference_K']:.2f} "+r'\\'+'\n'
        text+=r'''\bottomrule\end{tabular}\caption{Native-to-native time-resolution evidence. Matching means the same sampled physical times; a different row-transfer time can change the represented exposed surface. This table does not compare ANSYS with experimental measurements.}\end{table}
'''
        for d in resolution:
            text+=f"For {title(d['case'])}, the sampled hot-face peak changes from {d['primary_hot_peak_C']:.2f} to {d['quarter_hot_peak_C']:.2f} degrees Celsius, although its temperature at the end of heating changes more. The largest matched heating-history difference occurs at {d['max_difference_time_s']:.5f} s. "
        text+='The remaining refinement must assess surface temperatures and transfer events as well as casing temperatures. The thousands-of-degrees scale is present in both native solutions; the exact hot-face history remains provisional.\n'
    (out/'native_hot_surface_time_comparison.json').write_text(json.dumps(dict(records=resolution,qualification='Audited native time-only comparisons; passing casing criteria does not establish surface-temperature convergence.'),indent=2)+'\n')
    return text


def source_appendix(root, runs):
    """Publish exact small input copies and line-numbered listings from sealed cases."""
    target=root/'docs/analysis/source_listings';target.mkdir(exist_ok=True)
    copied=[]
    names=['model_base.inp','material_v0.apdl','run_v0.inp','resume_v0.inp','export_fields.mac',
           'couple.cmd','coupler.py','usermatth.F','config.json','launch_v0.ps1','preflight_v0.inp']
    for run in runs:
        source=root/'ansystmp/runs'/run['name'];manifest=json.loads((source/'input_manifest.json').read_text())
        destination=target/run['case'];destination.mkdir(exist_ok=True)
        for name in names:
            p=source/name
            assert sha(p)==manifest[name], f'Changed sealed source: {p}'
            shutil.copy2(p,destination/name)
            assert sha(destination/name)==manifest[name]
            copied.append(dict(case=run['case'],runtime=run['name'],file=f'{run["case"]}/{name}',sha256=manifest[name],bytes=p.stat().st_size,lines=len(p.read_text().splitlines())))
    for name in ['build_material.cmd','prepare_model.py']:
        shutil.copy2(root/'model'/name,target/name)
        copied.append(dict(file=name,sha256=sha(target/name),bytes=(target/name).stat().st_size,provenance='Current source used to build or generate the sealed inputs; printed input decks govern the executed cases.'))
    # Print the CF material and coordinate construction with original line numbers.
    cf=(target/'sustainer_cf/model_base.inp').read_text().splitlines()
    start=cf.index('MPDELE,ALL,2')+1
    end=next(i for i in range(start,len(cf)) if cf[i].startswith('E,'))
    (target/'source_manifest.json').write_text(json.dumps(dict(qualification='Exact copies of all four audited primary input decks; no runtime or solver mutation. Full nodal/element decks are archived for all four cases; the PDF prints sustainer Al completely and the CF material/orientation differences.',files=copied),indent=2)+'\n')
    def listing(name,heading,description='',options=''):
        p=target/name
        if not options: options=''
        return '\n'+r'\clearpage\subsection{'+heading+'}\n'+description+'\n\n'+r'{\footnotesize\noindent Source: \path{'+name+r'}.\par\noindent SHA-256: \texttt{'+sha(p)+r'}.\par}'+'\n'+r'\lstinputlisting[style=iriscode'+options+r']{../analysis/source_listings/'+name+'}\n'
    text=r'''\clearpage\appendix\renewcommand{\thesection}{\Alph{section}}
\section{Executed source listings and reproducible input decks}
These listings are actual source and generated MAPDL inputs, not pseudocode. The source archive alongside the report contains complete model decks and configuration files for all four corrected primary runs. Each archived file was checked against its sealed runtime manifest. The main listing uses sustainer Al as the representative 80/20-row case; its complete 909-node/400-element deck is printed at the end. The CF property/orientation block is printed separately with its original line numbers. Booster radii and all case-specific paths are preserved in the accompanying complete input copies.

The listings retain historical names such as \texttt{v0} in commands and titles because they are exact copies of the executed inputs. They do not refer to a request to rerun the previous study. The report source archive's \texttt{source\_manifest.json} records full hashes for all four cases. The material DLL is a compiled artifact already versioned in \texttt{model/}; its source and build commands are printed below. Only the existing serial queue controls execution.
'''
    text+=listing('sustainer_al/material_v0.apdl','Complete phenolic material definition',
        'All ten temperature points, fifteen user properties and five state variables. This block is also embedded in the complete mesh deck.')
    text+=listing('sustainer_al/usermatth.F','Complete Fortran UserMatTh routine',
        'The corrected temporal midpoint is explicit in the listing. The routine contains the constitutive response and gas sensible sink; surface consumption and topology changes are in the controller.')
    text+=listing('sustainer_al/run_v0.inp','Complete MAPDL transient driver',
        'This driver calls the controller before and after each native solve. The accepted-step gate, rather than a zero solver exit alone, determines whether the next interval may start.')
    text+=listing('sustainer_al/resume_v0.inp','Complete MAPDL resume driver',
        'Only a matching accepted native/controller checkpoint is a valid restart. A restart does not authorize pairing an earlier controller record with a later native state.')
    text+=listing('sustainer_al/export_fields.mac','Complete MAPDL field and energy exporter',
        'The exporter records actual native time and substep identity, retrieves defined live phenolic state variables, and keeps raw energy channels for diagnosis.')
    text+=listing('sustainer_cf/model_base.inp','CF material and local-coordinate block',
        'This is the complete CF property/orientation definition extracted from its larger mesh deck. Line numbers refer to the original deck. The first following element command and later connectivity are in the archived full file.',
        f',firstline={start},lastline={end},firstnumber={start}')
    text+=listing('sustainer_al/coupler.py','Complete surface and acceptance controller',
        'Included because the Fortran routine alone does not perform ablation. This controller supplies the explicit surface law, blowing, removal scheduling, balance checks and accepted-state persistence.')
    text+=listing('build_material.cmd','Complete compiler and linker command file',
        r'The isolated build also contains an export definition with the two lines \texttt{EXPORTS} and \texttt{USERMATTH}. Compilation is not performed during report generation.')
    text+=listing('sustainer_al/couple.cmd','MAPDL-to-Python bridge')
    text+=listing('sustainer_al/model_base.inp','Complete representative MAPDL mesh and setup',
        'Every material, node and element command is printed, without omitted connectivity. Dimensions are in metres and the initial temperature is in degrees Celsius. The conformal interface shares nodes; no hidden contact mesh is added.')
    return text


def create(root,runs):
    temperatures=temperature_section(root,runs)
    physics=(root/'docs/en/thermochemical_details.tex').read_text()
    appendix=source_appendix(root,runs)
    return temperatures,physics,appendix
