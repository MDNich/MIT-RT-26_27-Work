"""Present completed combined-input independent studies with explicit limits."""
import json
import matplotlib.pyplot as plt
from latex_style import CASE_COLORS


def create(root,out,read):
    path=root/'validation/combined_pulse_sensitivity.json'
    if not path.exists() or not json.loads(path.read_text()).get('complete'):
        return []
    summary=read('validation/combined_pulse_sensitivity.json')
    fine=[r for r in summary['comparisons'] if r['fine']=='n320']
    if len(fine)!=8:return []
    parts=[r'\subsection{Combined-input pulse scenarios}',
        'Two joint engineering perturbations were calculated for all four configurations, separately from ANSYS. The first doubles the heat-transfer coefficient to 2000 in SI units, raises phenolic conductivity by 20 percent and lowers its heat capacity by 20 percent. The second doubles the same coefficient, lowers phenolic conductivity by 20 percent and halves the effective char-removal cost to 17.5 MJ/kg. Every change comes from the earlier one-at-a-time engineering screen; their combination is neither a measured uncertainty interval nor a demonstrated worst case.',
        'All cases use a hypothetical seven-second heating pulse with the primary ambient-cooling assumptions and property-scope stops. Eight scenarios were each repeated with 80/20, 160/40 and 320/80 phenolic/casing cells. Heating steps scale with radial pitch squared: 0.003125, 0.00078125 and 0.0001953125 s. Later cooling steps are respectively 0.0625, 0.015625 and 0.00390625 s. Intermediate time and mesh effects remain coupled in this additional input screen; the separate native resolution program tests those effects independently.']
    if not all(r['passed'] for r in fine):
        failed=', '.join(r['case'].replace('_',' ')+' / '+r['scenario'].replace('_',' ') for r in fine if not r['passed'])
        return parts+['Some final 160-to-320 comparisons have not met the numerical targets: '+failed+'. Their physical interpretation is withheld pending further resolution. No combined-case lifetime is inferred.']
    data={}
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        for scenario in ['heating_transport','heating_consumption']:
            d=read(f'validation/radial/{case}_combined_pulse7_{scenario}_n320.json')
            assert not d['event_bracket_s']
            data[case,scenario]=d
    peak_delta=max(abs(v) for r in fine if r['peak_differences_K'] for v in r['peak_differences_K'].values())
    scope_delta=max([100*r['scope_time_relative_change'] for r in fine if r['scope_time_relative_change'] is not None] or [0])
    parts += [f'All eight final comparisons meet the stated targets. Complete-history casing maxima change by at most {peak_delta:.3f} K; scope-time changes are at most {scope_delta:.3f} percent. Retained-thickness checks pass separately. These numerical results do not calibrate the joint physical assumptions.']
    fig,axes=plt.subplots(1,2,figsize=(8.4,3.5),constrained_layout=True)
    for ax,scenario,title in zip(axes,['heating_transport','heating_consumption'],
            ['Higher heating + changed conductivity/capacity','Higher heating + changed conductivity/removal cost']):
        for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
            d=data[case,scenario];h=d['history'];name=case.replace('_',' ').title().replace('Cf','CF')
            ax.plot([a['time_s'] for a in h],[a['interface_C'] for a in h],label=name,color=CASE_COLORS[case],lw=1.2)
            if d['property_limit_bracket_s']:
                ax.plot(h[-1]['time_s'],h[-1]['interface_C'],'x',color=CASE_COLORS[case],ms=7)
        ax.axvspan(0,7,color='gray',alpha=.15)
        ax.set(xlabel='Time [s]',ylabel=r'Inner casing temperature [$^\circ$C]',title=title)
        ax.legend(fontsize=7)
    fig.suptitle('Independent joint-input scenarios; x marks a material-scope stop')
    fig.savefig(out/'combined_pulse_sensitivities.pdf');fig.savefig(out/'combined_pulse_sensitivities.png',dpi=180);plt.close(fig)
    parts += [r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/combined_pulse_sensitivities.pdf}\caption{Independent 320-row combined scenarios. The shaded interval is imposed heating. Scope-limited curves do not predict a later casing peak or structural failure.}\end{figure}',
        r'\begin{table}[H]\centering\scriptsize\begin{tabular}{llrrr}\toprule Case & Joint scenario & Through [s] & Inner max [$^\circ$C] & Retained [mm]\\\midrule']
    for (case,scenario),d in data.items():
        parts.append(' & '.join([case.replace('_',' ').title().replace('Cf','CF'),
            'Transport' if scenario=='heating_transport' else 'Consumption',
            f"{d['final']['time_s']:.3f}",f"{d['sampled_maxima']['interface_C']['temperature_C']:.2f}",
            f"{d['final']['remaining_mm']:.4f}"])+r' \\')
    parts += [r'\bottomrule\end{tabular}\end{table}',
        'Changing several assumptions can change both heat admitted to the wall and energy removed by gas generation and char consumption. A larger imposed heat-transfer coefficient therefore need not produce a hotter casing when the other closure parameters also change. This is sensitivity of the chosen equations, not evidence that changing a real liner would improve safety. No scenario here establishes a real-motor burnthrough time.',
        'Four separate bounded native controls have been prepared for higher heating, the published alternative CF tuple and two combined cases. They stop at 20 s or an earlier material flag and test implementation against the same-mesh independent model. Their short horizons cannot establish later cooling maxima.']
    plan=read('validation/native_sensitivity_plan.json')
    accepted=[]
    if plan:
        for entry in plan['cases']:
            a_path=root/'validation'/f"accepted_{entry['runtime']}.json"
            c_path=root/'validation'/f"native_pulse_comparison_{entry['runtime']}.json"
            if not a_path.exists() or not c_path.exists():continue
            a=read(str(a_path.relative_to(root)));c=read(str(c_path.relative_to(root)))
            if not (a['passed'] and c['comparison_passed'] and c['native_control_checks_passed']):continue
            assert c['accepted_native_index']==a['accepted_steps']
            accepted.append((entry,a,c))
    parts.append(f"At this snapshot, {len(accepted)} of those four controls have completed both native audit and independent comparison. Prepared or running controls supply no completed native confirmation.")
    if accepted:
        parts += [r'\begin{table}[H]\centering\scriptsize\begin{tabular}{llrr}\toprule Case & Control & Through [s] & Max profile difference [K]\\\midrule']
        for entry,a,c in accepted:
            parts.append(' & '.join([entry['case'].replace('_',' ').title().replace('Cf','CF'),
                entry['scenario'].replace('_',' '),f"{a['time_s']:.3f}",
                f"{max(v['max_live_profile_difference_K'] for v in c['comparisons']):.3f}"])+r' \\')
        parts += [r'\bottomrule\end{tabular}\end{table}']
    return parts
