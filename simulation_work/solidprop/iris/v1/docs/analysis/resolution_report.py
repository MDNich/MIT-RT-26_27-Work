"""Report completed independent resolution and cooling evidence."""
import hashlib
import json
import matplotlib.pyplot as plt


def create(root,out,captured):
    parts=[]
    def read(relative):
        p=root/relative
        if not p.exists():return None
        captured.append(dict(file=relative,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        return json.loads(p.read_text())
    def name(case):return case.replace('_',' ').title().replace('Cf','CF')
    def row(values):return ' & '.join(str(v) for v in values)+r' \\'

    d=read('validation/input_sensitivity_refinement.json')
    if d and d['complete']:
        maximum=100*max(x['relative_time_change'] for x in d['results'])
        parts += [r'\subsection{Numerical resolution of the sensitivity screen}',
            f'Ten stronger-heating, lower-phenolic-conductivity and alternative-CF scenarios were repeated with 160 radial cells and half the step ceiling. Their property-scope stopping times changed by at most {maximum:.2f} percent. This checks selected scenarios, not every bar. Changes comparable to percent-level discretization error are not resolved physical differences.',
            'Remaining thickness was checked separately. The initial 80-to-160-cell comparisons exceeded the stated thickness tolerance in three scenarios, despite agreement in stopping time. Those cases received another refinement rather than being declared converged from timing alone.']
        further=read('validation/sensitivity_thickness_refinement.json')
        if further and further['complete']:
            parts += [r'\begin{table}[H]\centering\scriptsize\begin{tabular}{llrrr}\toprule Case & Perturbation & Timing change [\%] & Thickness change [mm] & Target [mm]\\\midrule',
                '\n'.join(row([name(x['case']),'Higher heating' if x['scenario']=='h2000' else 'Lower conductivity',f"{100*x['relative_time_change']:.2f}",f"{abs(x['remaining_difference_mm']):.4f}",f"{x['thickness_tolerance_mm']:.4f}"]) for x in further['results']),
                r'\bottomrule\end{tabular}\end{table}',
                'This table compares 160 with 320 cells, with a further halving of the time step. '+('All listed timing and remaining-thickness targets passed.' if all(x['passed'] for x in further['results']) else 'Some remaining-thickness targets are still unmet; those quantities remain unresolved.')]

    reaction=read('validation/reaction_benchmark.json')
    if reaction and reaction['passed']:
        worst=max(a['max_absolute_error'] for a in reaction['results'])
        parts += [r'\subsection{Native prescribed-temperature reaction check}',
            f'The native user material was held at uniform prescribed phenolic temperatures of 300, 600 and 1000 degrees Celsius. Conversion at 0.1, 1 and 5 s matched the analytical first-order Arrhenius solution within {worst:.2g} absolute conversion. This verifies the implementation under controlled temperature; it does not validate reaction constants against the actual liner. No surface-consumption controller was used in this fixture.']

    convergence=read('validation/pulse_resolution.json')
    if not convergence or not convergence['complete']:return '\n\n'.join(parts)
    files={
        'sustainer_al':'sustainer_al_pulse7_resolved_joint320.json',
        'sustainer_cf':'sustainer_cf_pulse7_resolved_joint640.json',
        'booster_al':'booster_al_pulse7_cooling300_joint320.json',
        'booster_cf':'booster_cf_pulse7_cooling300_joint320.json'}
    data={c:read('validation/radial/'+f) for c,f in files.items()}
    if not all(data.values()):return '\n\n'.join(parts)
    parts += [r'\section{Independent pulse and cooling investigation}',
        'These curves are independent radial calculations, not ANSYS output. Each uses seven seconds of the prescribed hot-gas boundary followed by ambient gas with a heat-transfer coefficient of 8 in SI units, zero hot radiation and zero char consumption. Pyrolysis and conduction continue during heat soak. The pulse duration and cooling conditions are assumed, not measured firing or tailoff histories.',
        'The sustainer Al and both booster references use 320 phenolic and 80 casing cells. Sustainer CF required 640 and 160 cells to bring its property-flag timing change below five percent. Its curve stops at the provisional 150-degree casing flag, so its later peak is unknown within this material model. The other curves end after their sampled casing peaks.']
    fig,axes=plt.subplots(2,1,figsize=(8.4,5.5),constrained_layout=True)
    for case,d in data.items():
        h=d['history'];label=name(case)
        for ax,key in zip(axes,['interface_C','outer_C']):
            line=ax.plot([a['time_s'] for a in h],[a[key] for a in h],label=label,lw=1.3)[0]
            if d['property_limit_bracket_s']:
                ax.plot(h[-1]['time_s'],h[-1][key],'x',color=line.get_color(),ms=7)
        for ax in axes:ax.set(xlabel='Time since imposed heating begins [s]')
    for ax in axes:
        ax.axvspan(0,7,color='gray',alpha=.16);ax.legend(fontsize=8,ncol=2)
    axes[0].set(ylabel=r'Casing inner face [$^\circ$C]');axes[1].set(ylabel=r'Casing outer face [$^\circ$C]')
    fig.suptitle('Independent seven-second pulse and cooling; x marks material-scope stop')
    fig.savefig(out/'independent_cooling.pdf');fig.savefig(out/'independent_cooling.png',dpi=180);plt.close(fig)
    parts += [r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/independent_cooling.pdf}\caption{Independent refined temperature histories. The shaded interval is imposed heating; curves beyond it describe assumed cooling. A scope stop is not a predicted casing failure.}\end{figure}',
        r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrr}\toprule Case & Through [s] & Inner max [$^\circ$C] & Outer max [$^\circ$C] & Retained mesh [mm]\\\midrule',
        '\n'.join(row([name(c),f"{d['final']['time_s']:.2f}",f"{d['sampled_peaks']['interface_C']['temperature_C']:.2f}",f"{d['sampled_peaks']['outer_C']['temperature_C']:.2f}",f"{d['final']['remaining_mm']:.4f}"]) for c,d in data.items()),
        r'\bottomrule\end{tabular}\end{table}',
        'For the complete 127-second histories, the last 160-to-320-cell joint refinement changes sampled casing maxima by at most 1.7 K and remaining mesh thickness by at most 0.015 mm. Sustainer CF instead compares its censored stopping time; the 320-to-640-cell change is about two percent. These checks do not establish convergence of every hot-face temperature or a future exhaustion event.',
        'Both booster cases still had a rising casing temperature at 127 s. Independent extension to 300 s captured their later peaks, so fresh native booster packages were prepared with that longer cooling horizon. The original unstarted packages are preserved. Native confirmation of the refined pulse/cooling histories remains pending.']
    return '\n\n'.join(parts)
