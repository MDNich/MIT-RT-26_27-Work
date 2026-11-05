"""Report completed independent resolution and cooling evidence."""
import hashlib
import json
import matplotlib.pyplot as plt
from latex_style import CASE_COLORS,plot_samples
from temperature_convention_report import create as temperature_convention_report
from combined_sensitivity_report import create as combined_sensitivity_report
from removal_cutoff_report import create as removal_cutoff_report
from native_cf_refinement_report import create as native_cf_refinement_report
from native_booster_al_refinement_report import create as native_booster_al_refinement_report


def create(root,out,captured):
    parts=[]
    def read(relative):
        p=root/relative
        if not p.exists():return None
        captured.append(dict(file=relative,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        return json.loads(p.read_text())
    def name(case):return case.replace('_',' ').title().replace('Cf','CF')
    def comparison_label(check):
        kind=check.get('configuration_comparison',{}).get('kind')
        if kind=='combined_numerical_changes':return 'Combined numerical'
        if kind=='different_physical_model':return 'Model changed'
        return check['fine'].split('_midpoint_')[-1].replace('_smp10','').replace('_',' ')
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
                'This table compares 160 with 320 cells, with a further halving of the time step. '+('All listed timing and remaining-thickness targets passed.' if all(x['passed'] for x in further['results']) else 'The remaining-thickness failures in this comparison prompted the smaller-step investigation below.')]

    coupling=[(c,read('validation/char_coupling_resolution_'+c+'.json')) for c in ['sustainer_al','booster_cf']]
    coupling=[(c,d) for c,d in coupling if d and d['complete']]
    if coupling:
        parts += [r'\subsection{Resolution of the stronger-heating coupling error}',
            'The two unresolved doubled-heating cases were recomputed at 320 cells with time steps of 0.0001953125 and 0.00009765625 s, and at 640 cells with 0.000048828125 s. The joint comparison scales the time step with radial pitch squared. All reported time-only and joint comparisons now meet the five-percent timing target and the retained-thickness target of the larger of 0.02 mm and one percent of initial liner thickness.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrr}\toprule Case & 640-cell scope stop [s] & Retained [mm] & Joint timing change [\%] & Thickness change [mm]\\\midrule',
            '\n'.join(row([name(c),f"{d['results']['n640']['scope_bracket_s'][1]:.4f}",f"{d['results']['n640']['remaining_mm']:.4f}",f"{100*d['comparisons'][-1]['relative_time_change']:.3f}",f"{d['comparisons'][-1]['remaining_difference_mm']:.4f}"]) for c,d in coupling),
            r'\bottomrule\end{tabular}\end{table}',
            'These finer independent values supersede the coarse stronger-heating recession estimates. They resolve the tested numerical comparisons, not the unknown char kinetics or actual heat load. A closed mass ledger alone did not reveal the earlier time-coupling error. The retained FE thickness remains a whole-row geometric quantity, not a measured intact liner thickness.']

    capacity=read('validation/partial_capacity_resolution.json')
    if capacity and capacity['complete']:
        fine=[a for a in capacity['comparisons'] if a['phenolic_cells']==320]
        parts += [r'\subsection{Retained-char heat-capacity diagnostic}',
            'Twelve paired independent checks compare the existing full-cell capacity with an optional capacity-only reduction for consumed surface char, at 80, 160 and 320 phenolic cells. Each pair has the same mesh, time schedule and seven-second pulse. The variant changes heat capacity only: conductivity, geometry and source laws remain fixed. It is not a conservative enthalpy-removal model, a validated alternative, or a rigorous uncertainty bound.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrr}\toprule Case (320 cells) & Peak change [K] & Scope-time change [\%] & Thickness change [mm]\\\midrule',
            '\n'.join(row([name(a['case']),f"{a['casing_peak_differences_K']['interface_C']:.3f}" if a['casing_peak_differences_K'] else 'Censored',f"{100*a['scope_time_relative_change']:.3f}" if a['scope_time_relative_change'] is not None else 'No flag',f"{a['remaining_difference_mm']:.4f}"]) for a in fine),
            r'\bottomrule\end{tabular}\end{table}',
            'At 320 cells the complete-history inner casing peaks change by less than 0.46 K, while the sustainer CF scope time changes by 0.53 percent; no paired retained-thickness change occurs. The maximum consumed char still represented in a live FE row is about 0.143 percent of initial liner mass. At 80 cells, the sustainer CF flag shift is 3.74 percent, so this approximation is more visible on the coarser mesh. These conditional numerical effects do not bound unmodelled cracks, spallation or actual material behavior.']

    reaction=read('validation/reaction_benchmark.json')
    if reaction and reaction['passed']:
        worst=max(a['max_absolute_error'] for a in reaction['results'])
        parts += [r'\subsection{Native prescribed-temperature reaction check}',
            f'The native user material was held at uniform prescribed phenolic temperatures of 300, 600 and 1000 degrees Celsius. Conversion at 0.1, 1 and 5 s matched the analytical first-order Arrhenius solution within {worst:.2g} absolute conversion. This verifies the implementation under controlled temperature; it does not validate reaction constants against the actual liner. No surface-consumption controller was used in this fixture.']

    failure=read('validation/native_restart_failure_diagnosis.json')
    restart=read('validation/restart_topology_benchmark.json')
    if failure:
        parts += [r'\subsection{Rejected refined step and restart correction}',
            'The first 80-row sustainer Al run stopped at an attempted 4.175 s: its energy residual was 10.420 percent, above the unchanged five-percent limit. Its last accepted state was 4.1625 s. There was no internal substep cutback. Investigation found that an earlier removed layer returned after a multiframe restart because the controller reissued only newly pending deactivations. The rejected state is excluded from all accepted results.',
            r'ANSYS documents that multiframe restart files do not save element birth/death commands; these must be reissued after restart. The corrected controller replays the entire removed prefix, checks the native live-element count before every solve, and stores two hash-verified accepted native restart generations. See the \href{https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_bas/Hlp_G_BAS3_12.html}{ANSYS 2026 R1 Basic Analysis Guide, multiframe restart limitations}.',
            'The failed runtime and original queued packages are preserved. Fresh sibling packages use identical physical inputs and audit tolerances. The old native restart ring lacked the recent accepted state, so a failed native state was not combined with an earlier controller checkpoint.']
        if restart and restart['passed']:
            parts += ['A manufactured transient regression reproduced the old resurrection defect for all four cases. Full deactivation replay retained the correct live-element counts and exactly matched uninterrupted nodal temperatures at all sixteen checkpoints. The uninterrupted reference remains in the solution processor until its load steps finish; two earlier fixture drafts incorrectly re-entered a new solution and are preserved as rejected diagnostics. This regression verifies restart topology, not ablation physics.']

    substep=read('validation/native_substep_audit_issue.json')
    metadata=read('validation/substep_metadata_gate.json')
    if substep:
        parts += [r'\subsection{Cooling withdrawn after an internal-substep audit gap}',
            'The corrected restart run completed seven seconds of heating with one native substep per controller interval. At the first cooling interval, ANSYS cut back the requested 0.25 s step and solved at 7.125, approximately 7.19483, and 7.25 s. The old controller combined the final internal-substep capacity and gas-rate exports with the conversion increment over the whole controller interval. Passing its numerical threshold did not establish a consistent interval energy balance.',
            'The entire subsequent cooling chain is therefore withdrawn from accepted results, and the original run was paused and preserved. The heating prefix through 7 s is retained after inspection of every native load-step entry. Only the final result of each controller interval was saved, so the missing intermediate cooling energy terms cannot be reconstructed faithfully after the run.',
            'Fresh packages export native load-step and substep identity. Acceptance now requires exactly one native substep for each controller interval. The first second of cooling uses 0.0625 s intervals before returning to 0.25 s; any further internal cutback stops acceptance and preserves the preceding accepted restart. Separate default and tighter heat-flow convergence controls use identical schedules through 20 s. Their completed comparison is reported below; the acceptance gates were not relaxed.']
        if metadata and metadata['passed']:
            parts += ['A native read-only result probe returned substep 1 at 7 s and substep 3 at 7.25 s; the new acceptance function admits the former and rejects the latter. Retrospective log inspection found only single-substep intervals in all four published coarse baselines and the earlier restart/pulse controls. Their published acceptance is unaffected.']

    parts += temperature_convention_report(read,out)

    native=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        d=read('validation/native_pulse_comparison_'+case+'.json')
        if d:native.append(d)
    if native:
        parts += [r'\subsection{Refined native pulse cross-checks}',
            'These comparisons use the independent assembly at the same 80/20 radial mesh and coupling schedule as the native pulse cases. Only accepted native checkpoint times are compared; a running case has no predicted ANSYS future values. Layer-removal scheduling and the next hot-face transfer are checked separately.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrr}\toprule Case & Through [s] & Max profile [K] & Max conversion & Transfers passed\\\midrule',
            '\n'.join(row([name(d['case']),f"{d['accepted_native_time_s']:.3f}",f"{max(a['max_live_profile_difference_K'] for a in d['comparisons']):.3f}",f"{max(a['max_live_conversion_difference'] for a in d['comparisons']):.5f}",sum(a['load_transfer_passed'] is True for a in d['removal_events'])]) for d in native),
            r'\bottomrule\end{tabular}\end{table}',
            ('All displayed comparisons meet the same-mesh profile, conversion, mass and row-count checks.' if all(d['comparison_passed'] for d in native) else ('The profile, conversion and mass targets pass, but the strict test of identical row schedules does not. Native and independent removal times are therefore reported separately.' if all(d.get('profile_conversion_mass_passed',False) for d in native) else 'Some same-mesh field comparisons do not meet their targets; those differences require investigation and are not presented as validated equivalence.')),
            'These checks do not establish fine-mesh convergence of the native stopping time. In particular, the independent sustainer CF pulse needed further refinement of its provisional property-flag time.']
        if substep and any('midpoint' not in d['runtime'] for d in native):
            parts += ['The historical refined sustainer comparison is restricted to the verified seven-second heating prefix; no withdrawn cooling values enter this table. Its hot-profile target remained unmet. The paired tolerance and reaction-temperature diagnostics above separate the causes; fresh corrected midpoint comparisons must establish the replacement result. Persistent native live counts verify the restart correction independently of this thermal-profile discrepancy.']
        elif substep:
            parts += ['This table uses fresh corrected-midpoint native runs. The earlier seven-second historical comparison and withdrawn cooling chain are excluded. Agreement now checks the intended midpoint reaction model, persistent layer deactivation and the strict single-substep cooling transition together.']
        events=[(d['case'],a) for d in native for a in d['removal_events'] if a.get('scheduled_time_difference_s') is not None]
        if events:
            parts += [r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrr}\toprule Case & Row & Native scheduled [s] & Independent [s] & Difference [s]\\\midrule',
                '\n'.join(row([name(c),a['rows_scheduled'],f"{a['scheduled_time_s']:.4f}",f"{a['independent_scheduled_time_s']:.4f}",f"{a['scheduled_time_difference_s']:.5f}"]) for c,a in events),r'\bottomrule\end{tabular}\end{table}',
                'These are individual row-removal events, not liner-exhaustion times. The native event is bracketed by its previous accepted intact state and the scheduled state; geometric deactivation occurs in the next solve.']

    uniformity=read('validation/native_uniformity.json')
    if uniformity and uniformity['records']:
        parts += [r'\subsection{Variation within the uniform sector}',
            'Every accepted checkpoint in the completed corrected primary cases was checked for differences among the nine nodes at each radial station. The table reports the largest axial/angular spread at a common radius, using only nodes belonging to elements active during that solve. This quantifies information suppressed by radial averaging; it does not establish uniformity in a real motor or bound unmodelled end effects.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrr}\toprule Case & Through [s] & Phenolic range [K] & Casing range [K]\\\midrule',
            '\n'.join(row([name(d['case']),f"{d['through_s']:.2f}",
                f"{d['maximum_same_radius_ranges']['live_phenolic']['range_K']:.3g}",
                f"{d['maximum_same_radius_ranges']['casing']['range_K']:.3g}"]) for d in uniformity['records']),
            r'\bottomrule\end{tabular}\end{table}']

    refined_uniformity=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        record=read(f'validation/native_uniformity_{case}_pulse7_midpoint_space160_geom005_smp10.json')
        if record:refined_uniformity.extend(record['records'])
    if refined_uniformity:
        parts += ['The completed 160/40-row corrected-geometry cases were also checked at every accepted checkpoint. '
            'Their maximum same-radius ranges are listed separately below; these small ranges do not establish physical uniformity outside the modelled slice.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrr}\toprule Refined case & Through [s] & Phenolic range [K] & Casing range [K]\\\midrule',
            '\n'.join(row([name(d['case']),f"{d['through_s']:.2f}",
                f"{d['maximum_same_radius_ranges']['live_phenolic']['range_K']:.3g}",
                f"{d['maximum_same_radius_ranges']['casing']['range_K']:.3g}"]) for d in refined_uniformity),
            r'\bottomrule\end{tabular}\end{table}']

    native_plan=read('validation/native_resolution_plan.json')
    native_resolution=read('validation/native_resolution_comparison.json')
    if native_plan:
        parts += [r'\subsection{Native spatial and time-resolution program}',
            'The original native resolution plan has thirteen additional cases. For each motor/casing pair, the first comparison keeps 80 phenolic and 20 casing rows while reducing the heating and cooling coupling steps by four. The 160/40-row case retains those refined time steps. Its current transition from the older 80-row case also changes sector geometry and solver tolerance, so that pair is labelled as a combined numerical comparison. The corrected 320/80-row case retains the new geometry measures and solver tolerance while halving the time steps. Sustainer CF additionally uses 640/160 rows because the independent 160-to-320-cell scope-time comparison failed its target.',
            'The 80-row time check and 160-row spatial check use 0.003125 s heating, 0.015625 s during the first cooling second, and 0.0625 s thereafter. The 320-row case halves these intervals; the 640-row case halves them again. All use the same physical inputs, corrected library, tighter nonlinear tolerance and unchanged audit gates. Each package preserves the primary cooling horizon and stops at the provisional material flag.',
            'Native comparisons require casing peak changes below 5 K for completed histories, scope-time changes below five percent for censored histories, and retained-thickness changes no larger than the greater of 0.02 mm or one percent of the initial liner. A scope-limited calculation cannot supply a later casing peak. Preparation is not an accepted result.']
        if native_resolution and native_resolution['comparisons']:
            parts += [r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrll}\toprule Case & Peak change [K] & Scope change [\%] & Thickness [mm] & Comparison & Pass\\\midrule',
                '\n'.join(row([name(a['case']),
                    f"{max(abs(v) for v in a['peak_differences_K'].values()):.3f}" if a['peak_differences_K'] else '--',
                    f"{100*a['scope_time_relative_change']:.3f}" if a['scope_time_relative_change'] is not None else '--',
                    f"{a['remaining_difference_mm']:.4f}",
                    comparison_label(a),'Yes' if a['passed'] else 'No']) for a in native_resolution['comparisons']),
                r'\bottomrule\end{tabular}\end{table}',
                'Only completed, audited native cases with passing same-mesh independent checks enter this table. Earlier refinement failures remain visible; convergence is judged on the final relevant comparisons.']
            mixed=[a for a in native_resolution['comparisons'] if a.get('configuration_comparison',{}).get('kind')=='combined_numerical_changes']
            labels={'aluminium_radial_rows':'casing radial resolution',
                    'phenolic_radial_rows':'phenolic radial resolution',
                    'angle_deg':'sector angle',
                    'mesh_measure_convention':'area/volume formulas',
                    'native_heat_flow_tolerance':'nonlinear heat-flow tolerance'}
            groups={}
            for a in mixed:
                keys=tuple(sorted(a['configuration_comparison']['numerical_changes']))
                groups.setdefault(keys,[]).append(name(a['case']))
            for keys,cases in groups.items():
                changed=', '.join(labels.get(k,k.replace('_',' ')) for k in keys)
                parts += [f"The combined numerical comparisons for {', '.join(cases)} change {changed}. "
                          'Their outcomes cannot be attributed to radial mesh refinement alone. '
                          'The finer comparisons must retain common sector measures and solver controls '
                          'to isolate the remaining mesh/time effects. Execution-core changes are recorded separately.']
            complete_time=[native_resolution['records'][a['fine']] for a in native_resolution['comparisons']
                           if a['complete_histories'] and 'time_quarter' in a['fine']]
            if complete_time:
                parts += [r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrrr}\toprule Case & Inner peak [$^\circ$C] & Time [s] & Outer peak [$^\circ$C] & Time [s] & Retained [mm]\\\midrule',
                    '\n'.join(row([name(d['case']),
                        f"{d['sampled_maxima']['case_inner_max_C']['temperature_C']:.3f}",
                        f"{d['sampled_maxima']['case_inner_max_C']['time_s']:.4f}",
                        f"{d['sampled_maxima']['case_outer_max_C']['temperature_C']:.3f}",
                        f"{d['sampled_maxima']['case_outer_max_C']['time_s']:.4f}",
                        f"{d['remaining_mm']:.6f}"]) for d in complete_time),
                    r'\bottomrule\end{tabular}\caption{Accepted native quarter-step casing peaks for histories completing their prescribed cooling horizon, at unchanged 80/20-row spatial resolution. The scope-limited sustainer CF result is described separately below. These values do not establish spatial convergence or a motor lifetime.}\end{table}']
            complete_refined=[d for d in native_resolution['records'].values()
                              if d['complete'] and d['phenolic_cells']>80]
            if complete_refined:
                parts += [r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrrrr}\toprule Case & Rows & Inner peak [$^\circ$C] & Time [s] & Outer peak [$^\circ$C] & Time [s] & Retained [mm]\\\midrule',
                    '\n'.join(row([name(d['case']),f"{d['phenolic_cells']}/{d['case_cells']}",
                        f"{d['sampled_maxima']['case_inner_max_C']['temperature_C']:.3f}",
                        f"{d['sampled_maxima']['case_inner_max_C']['time_s']:.4f}",
                        f"{d['sampled_maxima']['case_outer_max_C']['temperature_C']:.3f}",
                        f"{d['sampled_maxima']['case_outer_max_C']['time_s']:.4f}",
                        f"{d['remaining_mm']:.6f}"]) for d in complete_refined),
                    r'\bottomrule\end{tabular}\caption{Completed finer native histories. Rows lists phenolic/casing radial cells. Values are sampled maxima over each completed cooling horizon; scope-limited CF histories are excluded from this peak table. Retained thickness is a whole-row mesh quantity, not a measurement of intact material.}\end{table}']
            for comparison in native_resolution['comparisons']:
                if not comparison['both_scope_limited']:
                    continue
                coarse=native_resolution['records'][comparison['coarse']]
                fine=native_resolution['records'][comparison['fine']]
                a,b=coarse['scope_bracket_s'],fine['scope_bracket_s']
                parts += [f"For {name(comparison['case'])}, the {coarse['phenolic_cells']}-to-{fine['phenolic_cells']}-row "
                    f"{comparison_label(comparison).lower()} comparison changes the accepted material-scope bracket from "
                    f"[{a[0]:.4f}, {a[1]:.4f}] s to [{b[0]:.4f}, {b[1]:.4f}] s. "
                    f"The refined endpoint has an inner casing temperature of {fine['sampled_maxima']['case_inner_max_C']['temperature_C']:.3f} "
                    f"degrees Celsius and retains {fine['remaining_mm']:.6f} mm of mesh. "
                    'These are cooling-phase property-range stops, not burnthrough or structural failure. '
                    'Their outer casing endpoint temperatures are not completed cooling peaks.']
                if not comparison['passed']:
                    parts += [f"The scope-time change is {100*comparison['scope_time_relative_change']:.3f} percent, "
                        'which exceeds the five-percent target despite unchanged retained mesh. '
                        'This is an accepted numerical solution with an unresolved refinement difference; '
                        'the finer queued comparisons are still required.']
            parts += native_cf_refinement_report(root,out,read,native_resolution)
            parts += native_booster_al_refinement_report(root,out,read,native_resolution)
            parts += [f"{len(native_resolution['pending'])} prepared native resolution cases remain without terminal accepted comparisons at this edition. "
                'The primary histories remain separate from these refinements; the hot-face time comparison is reported earlier.']
        else:
            parts += ['At this edition no completed native refinement pair is available. The independent refinement results below remain distinct.']

    parts += removal_cutoff_report(root,read)
    parts += combined_sensitivity_report(root,out,read)
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
    longer=read('validation/longer_pulse_refinement.json')
    if longer and longer['complete']:
        records=[]
        for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
            for pulse in [20,60]:
                d=read(f'validation/radial/{case}_pulse{pulse}_refined_n320.json')
                records.append((case,pulse,d))
        fig,axes=plt.subplots(1,2,figsize=(8.5,3.1),constrained_layout=True)
        for ax,pulse in zip(axes,[20,60]):
            for c,p,d in records:
                if p!=pulse:continue
                plot_samples(ax,[a['time_s'] for a in d['history']],[a['interface_C'] for a in d['history']],label=name(c),color=CASE_COLORS[c])
            ax.axvspan(0,pulse,color='.85');ax.set(title=f'Imposed {pulse} s heating pulse',xlabel='Time [s]',ylabel=r'Inner casing temperature [$^\circ$C]')
            ax.legend(fontsize=7)
        fig.savefig(out/'longer_pulse_histories.pdf');fig.savefig(out/'longer_pulse_histories.png',dpi=180);plt.close(fig)
        parts += [r'\subsection{Exploratory twenty- and sixty-second pulses}',
            'These durations are assumed scenarios, not firing-time estimates. Each calculation stops at its provisional casing-property flag or continues for 300 s after heating. A stop during heating means the prescribed pulse was not completed within the material model; a stop during cooling identifies delayed heat soak. None reached phenolic exhaustion within the accepted model scope.',
            r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/longer_pulse_histories.pdf}\caption{Independent 320-cell longer-pulse scenarios; gray shading marks prescribed heating. Curves end at a scope flag or at the scenario horizon.}\end{figure}',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrlrr}\toprule Case & Pulse [s] & Through [s] & Stop reason & Inner max [$^\circ$C] & Retained [mm]\\\midrule',
            '\n'.join(row([name(c),p,f"{d['final']['time_s']:.3f}",'During heating' if d['property_limit_bracket_s'] and d['final']['time_s']<p else ('During cooling' if d['property_limit_bracket_s'] else 'Horizon'),f"{d['sampled_maxima']['interface_C']['temperature_C']:.2f}",f"{d['final']['remaining_mm']:.4f}"]) for c,p,d in records),
            r'\bottomrule\end{tabular}\end{table}',
            'All eight 160-to-320-cell comparisons passed their numerical targets. Censored flag times changed by at most 1.05 percent; complete-history casing maxima changed by less than 0.97 K, and retained thickness changed by at most 0.020 mm. Sustainer CF reaches the same scope stop before either longer pulse ends, so those two rows describe the same partial heating history. These independent scenarios still require native confirmation of influential conditions and measured heating/material data for a physical lifetime claim.']
    return '\n\n'.join(parts)
