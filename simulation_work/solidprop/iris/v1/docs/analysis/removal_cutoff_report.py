"""Keep numerical cutoff sensitivity distinct from uncertain physical inputs."""
import json


def create(root,read):
    path=root/'validation/removal_cutoff_sensitivity.json'
    if not path.exists() or not json.loads(path.read_text()).get('complete'):return []
    d=read('validation/removal_cutoff_sensitivity.json')
    fine=[a for a in d['comparisons'] if a['phenolic_cells']==320]
    parts=[r'\subsection{Sensitivity to the row-removal cutoff}',
        'The removal threshold is a numerical choice: a row is deactivated when residual solid mass is less than 0.1 percent of its initial virgin mass. Twenty-four paired independent runs tested 0.01, 0.1 and 1 percent cutoffs for all four cases at 160/40 and 320/80 phenolic/casing cells. Physical laws and time settings were fixed within each pair. These are numerical-tolerance perturbations, not material uncertainty.',
        r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrrrr}\toprule Case (320 cells) & Cutoff [\%] & Inner peak change [K] & Scope-time change [\%] & Retained change [mm]\\\midrule']
    for a in fine:
        parts.append(' & '.join([a['case'].replace('_',' ').title().replace('Cf','CF'),
            f"{100*a['cutoff_fraction']:.2g}",
            f"{a['peak_differences_K']['interface_C']:.3f}" if a['peak_differences_K'] else 'Censored',
            f"{100*a['scope_time_relative_change']:.3f}" if a['scope_time_relative_change'] is not None else '--',
            f"{a['remaining_difference_mm']:.4f}"])+r' \\')
    parts += [r'\bottomrule\end{tabular}\end{table}',
        'Changes are relative to the 0.1-percent calculation on the same mesh. At 320 cells, complete-history casing peaks shift by as much as 3.812 K. Sustainer CF scope timing changes by about -7.21 to +16.12 percent, exceeding the five-percent timing target. This sensitivity is separate from radial/time convergence at a fixed cutoff. The queued native cases retain their sealed 0.1-percent rule; their reported times remain conditional on that choice.',
        'The small expelled residual mass does not make this timing effect negligible. A nearly consumed row can remain thermally active while the residual virgin fraction continues reacting, delaying transfer of the hot boundary to the next row. This explains why a mass-ledger check alone does not settle removal discretization. No real-motor lifetime follows from these cutoff-dependent states.',
        r'The chosen equations also explain why a zero cutoff is not a physically validated target. Char consumption cannot exceed the available char, so $m_{\rm solid}/V \geq \rho_v(1-\alpha)$. The first-order conversion law leaves $1-\alpha=(1-\alpha_0)\exp(-\int k\,dt)>0$ at finite integrated reaction exposure. Thus exact zero residual is not reached in finite time in the continuous equations. The finite cutoff approximates ejection or loss of continuity of the residual solid, for which this study has no calibration. Tighter cutoffs test numerical/model dependence; they do not automatically improve physical accuracy.']
    tail_path=root/'validation/removal_cutoff_tail_sustainer_cf.json'
    if tail_path.exists() and json.loads(tail_path.read_text()).get('complete'):
        tail=read('validation/removal_cutoff_tail_sustainer_cf.json')
        last=tail['results'][-1];changes=[abs(100*a['scope_time_relative_change']) for a in tail['comparisons']]
        parts += [f"Additional fixed-640-cell sustainer CF checks at fractional cutoffs 1e-7 and 1e-8 change the scope time by {changes[0]:.3f} and {changes[1]:.3f} percent relative to the preceding decade. The 1e-8 case stops at {last['scope_bracket_s'][1]:.4f} s with {last['remaining_mm']:.4f} mm retained. These smaller successive changes do not erase the difference from the original cutoff or identify a physically correct residual-ejection rule."]
    tight_path=root/'validation/removal_cutoff_resolution.json'
    if not tight_path.exists() or not json.loads(tight_path.read_text()).get('complete'):
        parts += ['Successively tighter fractional cutoffs of 1e-4, 1e-5 and 1e-6 are being checked at 320 and 640 cells. Their unresolved results are not used to revise a native input or declare the default timing converged.']
        return parts
    tight=read('validation/removal_cutoff_resolution.json')
    final=[a for a in tight['comparisons'] if
        (a['comparison']=='cutoff only' and a['fine_cells']==640 and a['fine_cutoff']==1e-6)
        or (a['comparison']=='space and time at fixed cutoff' and a['fine_cutoff']==1e-6)]
    parts += ['Additional independent calculations now compare successive fractional cutoffs of 1e-4, 1e-5 and 1e-6 at 320 and 640 cells. These tests concern the numerical equations, not physical validation of the removal law.',
        r'\begin{table}[H]\centering\scriptsize\begin{tabular}{llrrrl}\toprule Case & Final comparison & Peak change [K] & Scope change [\%] & Retained change [mm] & Pass\\\midrule']
    for a in final:
        parts.append(' & '.join([a['case'].replace('_',' ').title().replace('Cf','CF'),
            'Cutoff' if a['comparison']=='cutoff only' else 'Mesh/time',
            f"{max(abs(v) for v in a['peak_differences_K'].values()):.3f}" if a['peak_differences_K'] else '--',
            f"{100*a['scope_time_relative_change']:.3f}" if a['scope_time_relative_change'] is not None else '--',
            f"{a['remaining_difference_mm']:.4f}",'Yes' if a['passed'] else 'No'])+r' \\')
    parts += [r'\bottomrule\end{tabular}\end{table}',
        'Passing a successive-refinement target does not prove a zero-cutoff limit or remove the difference from the original 0.1-percent choice. Native confirmation and interpretation of the tighter rule remain separate work; no queued sealed configuration is silently replaced.']
    plan_path=root/'validation/native_cutoff_plan.json'
    if plan_path.exists():
        plan=read('validation/native_cutoff_plan.json')
        accepted_path=root/'validation'/f"accepted_{plan['runtime']}.json"
        compare_path=root/'validation'/f"native_pulse_comparison_{plan['runtime']}.json"
        verified=False
        if accepted_path.exists() and compare_path.exists():
            a=read(str(accepted_path.relative_to(root)));c=read(str(compare_path.relative_to(root)))
            verified=a['passed'] and c['comparison_passed'] and c['native_control_checks_passed'] and a['accepted_steps']==c['accepted_native_index']
        if verified:
            parts += [f"The separate native 80/20-row sustainer CF control with fractional cutoff 1e-6 has passed its native audit and same-mesh independent comparison through {a['time_s']:.3f} s. Its largest compared live-profile discrepancy is {max(x['max_live_profile_difference_K'] for x in c['comparisons']):.3f} K. This verifies the conditional implementation, not the physical choice of cutoff."]
        else:
            parts += ['A separate native 80/20-row sustainer CF control with fractional cutoff 1e-6 has been prepared but has not completed both verification gates. Its time schedule matches the 80-row quarter-step default-cutoff reference, allowing a controlled later native comparison. Neither sealed input is changed in place.']
    return parts
