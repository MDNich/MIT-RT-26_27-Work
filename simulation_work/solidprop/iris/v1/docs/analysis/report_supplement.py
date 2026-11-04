"""Evidence-driven report additions; native and independent plots stay separate."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from resolution_report import create as create_resolution
from native_field_report import create as create_native_fields
from native_field_report import corrected_fields
from latex_style import CASE_COLORS

CASES=['sustainer_al','sustainer_cf','booster_al','booster_cf']
def title(case):return case.replace('_',' ').title().replace('Cf','CF')
def row(values):return ' & '.join(str(v) for v in values)+r' \\'

def create(root,runs):
    out=root/'docs/analysis';parts=[];captured=[]
    if runs:
        fig,axes=plt.subplots(1,2,figsize=(8.4,3.0),constrained_layout=True)
        rows=[];massrows=[];balancerows=[];balance_records=[]
        for run in runs:
            h=run['history'];c=run['configuration'];name=title(run['case'])+' (n='+str(c['geometry']['phenolic_radial_rows'])+', midpoint)'
            for ax,key in zip(axes,['case_inner_max_C','case_outer_max_C']):
                ax.plot([a['time_s'] for a in h],[a[key] for a in h],label=name,color=CASE_COLORS[run['case']],lw=.9 if c['geometry']['phenolic_radial_rows']==20 else 1.8)
                if run['status']=='CASE_PROPERTY_LIMIT_REACHED':
                    ax.plot(h[-1]['time_s'],h[-1][key],'x',color=CASE_COLORS[run['case']],ms=7)
            rows.append(row([name,f"{h[-1]['time_s']:.3f}",f"{max(a['case_inner_max_C'] for a in h):.3f}",f"{max(a['case_outer_max_C'] for a in h):.3f}"]))
            a=h[-1];m0=sum(a[k] for k in ['solid_remaining_kg','gas_cumulative_kg','char_cumulative_kg','residual_ejected_kg'])
            massrows.append(row([name]+[f"{100*a[k]/m0:.3f}" for k in ['solid_remaining_kg','gas_cumulative_kg','char_cumulative_kg','subcell_mass_still_in_FE_kg']]))
            g=c['geometry'];initial=c['material']['virgin_reference_density_kg_m3']*(g['phenolic_outer_radius_m']**2-g['inner_radius_m']**2)/2*math.radians(g['angle_deg'])*g['length_m']
            signed=math.fsum(x['energy_residual_W']*x['dt_s'] for x in h)
            absolute=math.fsum(abs(x['energy_residual_W'])*x['dt_s'] for x in h)
            scale=math.fsum(max(abs(x['storage_W']),abs(x['convection_out_W']),abs(x['body_generation_W'])+abs(x['nodal_net_W']),1e-6)*x['dt_s'] for x in h)
            mass=max(abs(initial-sum(x[k] for k in ['solid_remaining_kg','gas_cumulative_kg','char_cumulative_kg','residual_ejected_kg']))/initial for x in h)
            assert mass<1e-6,(run['name'],mass)
            balancerows.append(row([name,f"{100*signed/scale:.4f}",f"{100*absolute/scale:.4f}",f"{mass:.2g}"]))
            balance_records.append(dict(runtime=run['name'],through_s=a['time_s'],signed_residual_J=signed,absolute_residual_sum_J=absolute,integrated_scale_J=scale,max_mass_ledger_relative_error=mass,topology_sensible_energy_diagnostic_J=a['topology_sensible_energy_scheduled_est_J']))
        axes[0].set(ylabel=r'Casing inner-face temperature [$^\circ$C]');axes[1].set(ylabel=r'Casing outer-face temperature [$^\circ$C]')
        for ax in axes:ax.set(xlabel='Time since imposed heating begins [s]');ax.legend(fontsize=7)
        fig.suptitle('Accepted native ANSYS casing temperatures')
        fig.savefig(out/'native_casing_temperatures.pdf');fig.savefig(out/'native_casing_temperatures.png',dpi=180);plt.close(fig)
        parts += [r'\section{Casing temperatures in accepted native states}',
            'The maxima below apply only through each accepted time shown. A running case is not assigned a future peak. Inner and outer casing temperatures are kept separate because thermal resistance can delay outside heating while the liner-facing side becomes hotter.',
            r'\begin{table}[H]\centering\small\begin{tabular}{lrrr}\toprule Case & Through [s] & Inner maximum [$^\circ$C] & Outer maximum [$^\circ$C]\\\midrule',
            '\n'.join(rows),r'\bottomrule\end{tabular}\end{table}',
            r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/native_casing_temperatures.pdf}\caption{Native accepted casing-temperature histories. An x marks a provisional material-scope stop, not predicted failure. These are thermal calculations, not pressure-casing strength or qualification results.}\end{figure}']
        parts += [r'\subsection{Mass bookkeeping and retained partial cells}',
            'The next table uses fractions of the initial liner mass at each run\'s final accepted time above. Gas and consumed char are separate cumulative losses. The last column measures consumed char that remains represented thermally until its cell is removed; it is a numerical storage discrepancy, not extra physical material.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrr}\toprule Case & Solid left [\%] & Gas loss [\%] & Char loss [\%] & Retained in FE [\%]\\\midrule',
            '\n'.join(massrows),r'\bottomrule\end{tabular}\end{table}',
            'A zero whole-cell recession does not mean zero mass loss. Conversely, pyrolysis conversion alone is not a hole through the liner. Refinement is needed to bound the effect of the retained partial-cell storage on temperature and recession.']
        parts += [r'\subsection{Accumulated numerical balance checks}',
            'The signed residual below checks accumulated bias; the absolute residual sum avoids cancellation of positive and negative step errors. Both are normalized by the time integral of the step balance scale. The independent mass check recomputes remaining solid plus gas, consumed char and expelled residual against the initial geometric inventory.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrr}\toprule Case & Signed energy [\%] & Absolute energy [\%] & Mass relative error\\\midrule',
            '\n'.join(balancerows),r'\bottomrule\end{tabular}\end{table}',
            r'The scale is $\max(|\dot U_{\rm FE}|,|Q_{\rm conv}|,|Q_{\rm body}|+|Q_{\rm nodal}|,10^{-6}\,\mathrm W)$ integrated over time. These residuals check the solved equations. They are not an independent physical enthalpy balance for departing material. Energy assigned to removed cells remains a separate diagnostic because the inherited capacity law is not a conservative enthalpy remap.']
        (out/'accumulated_native_balances.json').write_text(json.dumps(balance_records,indent=2)+'\n')
    parts.append(corrected_fields(root,out,captured,runs))
    parts.append(create_native_fields(root,out,captured))
    comparisons=[]
    for case in CASES:
        path=root/'validation'/f'native_radial_comparison_{case}.json'
        if path.exists():
            data=json.loads(path.read_text());comparisons.append(data)
            captured.append(dict(file=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if comparisons:
        parts += [r'\section{Independent numerical checks and scope limits}',
            'The following historical checks compare a separate cylindrical finite-element assembly with the original coarse ANSYS profiles at 0.1, 1, 2, 5 and 7 seconds. These native baselines used the inherited reaction-temperature expression. Passing the coarse-mesh comparison did not expose that defect; these records remain historical verification evidence, not corrected-model predictions. Numerical agreement cannot establish physical accuracy.',
            r'\begin{table}[H]\centering\small\begin{tabular}{lrr}\toprule Case & Maximum profile difference [K] & Maximum conversion difference\\\midrule',
            '\n'.join(row([title(d['case']),f"{d['max_temperature_difference_K']:.4f}",f"{d['max_conversion_difference']:.5f}"]) for d in comparisons),r'\bottomrule\end{tabular}\end{table}']
        fig,axes=plt.subplots(1,2,figsize=(8.4,3.1),constrained_layout=True)
        for d in comparisons:
            a=d['comparisons'][-1];rad=np.asarray(a['radius_m']);x=(rad-rad[0])*1000;n=len(a['native_mean_conversion'])
            ln=axes[0].plot(x,a['independent_temperature_C'],label=title(d['case']),lw=1.3)[0];color=ln.get_color()
            axes[0].plot(x,a['native_temperature_C'],'o',ms=2.5,mfc='none',color=color)
            xc=(x[:n]+x[1:n+1])/2
            axes[1].plot(xc,a['independent_mean_conversion'],color=color,lw=1.3)
            axes[1].plot(xc,a['native_mean_conversion'],'o',ms=2.5,mfc='none',color=color)
        axes[0].set(ylabel=r'Temperature [$^\circ$C]');axes[1].set(ylabel='Mean pyrolysis conversion',ylim=(-.03,1.03))
        for ax in axes:ax.set(xlabel='Depth from original liner bore [mm]')
        axes[0].legend(fontsize=7);fig.suptitle('Historical coarse profiles: inherited ANSYS circles, midpoint reference lines')
        fig.savefig(out/'native_radial_profiles.pdf');fig.savefig(out/'native_radial_profiles.png',dpi=180);plt.close(fig)
        parts.append(r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/native_radial_profiles.pdf}\caption{Accepted coarse-mesh native profiles and independent calculations. Temperatures are averaged over each uniform radial station. Agreement on the same mesh is not a mesh-convergence test.}\end{figure}')
    path=root/'validation/property_limit_convergence.json'
    if path.exists():
        d=json.loads(path.read_text());captured.append(dict(file=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        parts += [r'\subsection{Refined continuous-exposure stopping points}',
            'Under the nominal constant-heating assumptions, the independent model reaches the provisional casing property-range flag while a substantial liner remains. The table uses 320 cells per material and a 0.00078125 s step ceiling. These are model-scope stopping times, not burnthrough times, material failure temperatures or approved operating durations.',
            r'\begin{table}[H]\centering\small\begin{tabular}{lrrr}\toprule Case & Property flag [$^\circ$C] & Scope ends near [s] & Retained mesh [mm]\\\midrule',
            '\n'.join(row([title(a['case']),a['threshold_C'],f"{a['refined_crossing_bracket_s'][1]:.3f}",f"{a['retained_mesh_thickness_mm']:.4f}"]) for a in d['results']),r'\bottomrule\end{tabular}\end{table}',
            'The 160-to-320-cell joint refinement changes these stopping times by less than one percent. Separate 80-cell time-step comparisons change them by at most 3.6 percent. Remaining-thickness differences between the finest spatial cases are at most 0.020 mm. These numerical checks concern the property-scope event; they do not validate a later exhaustion event.']
    path=root/'validation/topology_benchmark.json'
    if path.exists():
        d=json.loads(path.read_text());assert d['passed']
        captured.append(dict(file=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        maximum=max(a['max_temperature_error_K'] for a in d['results'])
        parts += [r'\subsection{Native layer-removal verification}',
            f'Sixteen manufactured steady states cover all four configurations with zero rows removed, the first row removed, only the final phenolic row remaining, and the entire phenolic removed. Exact live-element counts, moving hot-face powers and analytical cylinder temperatures passed; the largest temperature discrepancy was {maximum:.5f} K. The final stage applies heating to the exposed casing. These are controlled software checks, not a calculated motor recession history.',
            'The first static fixture omitted the required full Newton option and was rejected by MAPDL. The corrected fixture passed; production transient inputs already contained that option. Static load-factor warnings and unused zero outputs for dead-element heat-table entries are retained in the native log. A separate controller fixture verified one-time residual-mass ejection and termination at the final row, without indexing a nonexistent next liner row.']
    variants=[('h500','Heat coefficient 500'),('h2000','Heat coefficient 2000'),('radiation0.1','Hot emissivity 0.1'),('radiation0.3','Hot emissivity 0.3'),('charcost0.5','Removal cost x0.5'),('charcost2','Removal cost x2'),('phenolic_k_0.8','Phenolic conductivity x0.8'),('phenolic_k_1.2','Phenolic conductivity x1.2'),('phenolic_cp_0.8','Phenolic heat capacity x0.8'),('phenolic_cp_1.2','Phenolic heat capacity x1.2'),('pressure600','Pressure 600 psi'),('pressure1000','Pressure 1000 psi')]
    all_variants=variants+[('cf_radial_k0.5','CF radial conductivity 0.5'),('cf_radial_k0.6','CF radial conductivity 0.6'),('cf_nasa_reference','Alternative NASA CF tuple')]
    available={};complete=True
    for case in CASES:
        selected=all_variants if case.endswith('_cf') else variants
        for tag,label in selected:
            p=root/'validation/radial'/f'{case}_fine_{tag}.json'
            if not p.exists():complete=False;continue
            d=json.loads(p.read_text());available[(case,tag)]=d
            captured.append(dict(file=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),final=d['final'],scope_bracket=d['property_limit_bracket_s']))
    if complete:
        fig,axes=plt.subplots(2,2,figsize=(10.6,8.2),constrained_layout=True)
        for ax,case in zip(axes.flat,CASES):
            baseline=json.loads((root/'validation/radial'/f'{case}_property_refined_n80_dt0.003125.json').read_text())['final']['time_s']
            selected=all_variants if case.endswith('_cf') else variants
            labels=[];changes=[]
            for tag,label in selected:
                d=available[(case,tag)]
                if d['property_limit_bracket_s'] is None:continue
                labels.append(label);changes.append(100*(d['final']['time_s']/baseline-1))
            colors=['#8C351F' if x<0 else '#1D587A' for x in changes]
            ax.barh(np.arange(len(labels)),changes,color=colors,height=.65);ax.axvline(0,color='#333333',lw=.8)
            ax.set(yticks=np.arange(len(labels)),yticklabels=labels,title=title(case),xlabel='Change in time to property-range flag [percent]')
            ax.invert_yaxis();ax.tick_params(axis='y',labelsize=7);ax.tick_params(axis='x',labelsize=8)
        fig.suptitle('Independent one-at-a-time input sensitivities; not burnthrough predictions')
        fig.savefig(out/'input_sensitivities.pdf');fig.savefig(out/'input_sensitivities.png',dpi=180);plt.close(fig)
        parts += [r'\subsection{Input sensitivities within the provisional material scope}',
            'Each bar changes one input at 80 radial cells per material and a 0.003125 s step ceiling. The reference is the same-resolution nominal independent calculation. This is a sensitivity screen, not a probability distribution or a combined worst case. The twenty-percent phenolic perturbations and factor-two removal-cost range are engineering choices, not measured confidence bounds.',
            r'Pressure changes affect only the assumed char-reaction closure here; imposed gas temperature and heat-transfer coefficient remain fixed. A small pressure effect in this model does not imply that real motor pressure is unimportant. The NASA alternative uses its slide-14 carbon-epoxy thermal-model tuple: density 1596, conductivity 0.3832 and specific heat 886 in SI units, with a resistance model based on 39 percent resin and 61 percent fibre by volume~\cite{nasa}. It is a different composite, not an identification of the Iris casing.',
            r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/input_sensitivities.pdf}\caption{Changes in the duration of prescribed constant heating before the provisional property-range flag. Red bars reach the flag sooner, blue bars later. These bars are not safe firing durations or burnthrough margins.}\end{figure}']
    parts.append(create_resolution(root,out,captured))
    (out/'auxiliary_snapshot.json').write_text(json.dumps(dict(sensitivity_matrix_complete=complete,sources=captured),indent=2)+'\n')
    return '\n\n'.join(parts)
