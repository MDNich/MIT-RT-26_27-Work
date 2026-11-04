"""Report the inherited time-convention diagnosis and separate tolerance test."""
import matplotlib.pyplot as plt


def create(read,out):
    replay=read('validation/native_temperature_convention.json')
    if not replay:return []
    paired=read('validation/native_solver_tolerance_comparison.json')
    inherited=read('validation/reaction_ramp_inherited.json')
    corrected=read('validation/reaction_ramp_midpoint_candidate.json')
    build=read('validation/material_midpoint_build.json')
    parts=[r'\subsection{Reaction-temperature convention and nonlinear tolerance}',
        r'The intended temporal midpoint is $(T_{n+1}+T_n)/2$. The inherited routine instead added half the temperature increment to the ANSYS temperature argument. The \href{https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_prog/Z7K4r1e5lcd.html}{ANSYS UserMatTh interface} supplies the current temperature and its increment. Accepted native-temperature replay identifies the actual evaluation as $T_{n+1}+\Delta T/2$, rather than the intended $T_{n+1}-\Delta T/2$. This affects both conversion and the gas sensible-energy sink.',
        f"Across the completed 20 s control, independent integration driven by every saved native temperature reproduces conversion with maximum absolute error {replay['max_conversion_errors']['end_plus_half_increment']:.2e} for the inherited expression. The intended midpoint expression differs by up to {replay['max_conversion_errors']['midpoint']:.5f}. This isolates the interface convention from differences in the temperature solver.",
        'The earlier isothermal reaction checks could not detect this error: the temperature increment was zero. Their successful constant-temperature results remain valid. The historical native curves elsewhere in this report retain their actual inherited routine and source hashes; they must not be interpreted as verification of the intended midpoint implementation. Earlier independent refinement and sensitivity calculations already use the intended midpoint.']
    if inherited and corrected:
        assert inherited['passed'] and corrected['passed']
        parts += ['Six additional native prescribed-temperature checks include increasing, decreasing and constant temperatures, each over one 0.01 s step. The inherited library matches the shifted expression; the separately rebuilt candidate matches the intended midpoint. Neither check calibrates reaction constants against a real liner.',
            r'\begin{table}[H]\centering\scriptsize\begin{tabular}{rrrrr}\toprule Start [$^\circ$C] & End [$^\circ$C] & Intended conversion & Inherited native & Corrected native\\\midrule',
            '\n'.join(' & '.join([str(a['start_C']),str(a['end_C']),f"{a['predictions']['midpoint']:.6g}",f"{a['native_alpha']:.6g}",f"{b['native_alpha']:.6g}"])+r' \\' for a,b in zip(inherited['results'],corrected['results'])),
            r'\bottomrule\end{tabular}\end{table}',
            'The correction changes only the sign of half the increment in the material routine. A new Intel Fortran x64 library was built in an isolated study folder; archived failed and historical runtimes are unchanged. Fresh packages must pass native audits and independent comparison before their thermal results supersede the inherited histories.']
        if build and build['status']=='NATIVE_RAMP_AND_MOTOR_PILOT_VERIFIED':
            parts += [f"The corrected 80/20-cell sustainer Al motor pilot completed eight audited intervals through 0.1 s. Its largest native/independent temperature-profile difference was {build['motor_pilot_max_profile_difference_K']:.5f} K. This permits longer corrected verification runs; it does not establish convergence of recession or a complete pulse/cooling history."]
    if paired:
        parts += [f"Both separate default/tighter nonlinear-tolerance controls completed 20 s with {paired['native'][0]['accepted_steps']} accepted single-substep intervals each. Persistent layer removal, cooling boundary transfer and native balance checks passed. Their maximum live-temperature difference was {paired['max_native_pair_profile_difference_K']:.3f} K. Tightening the heat-flow tolerance is a separate numerical correction; it cannot repair the reaction-temperature expression."]
        rows=[]
        for entry,kind in zip(paired['independent_comparisons'],['Default','Tighter']):
            same=read('validation/temperature_convention_resolution_'+entry['runtime']+'.json')
            rows.append(' & '.join([kind,f"{entry['max_profile_difference_K']:.3f}",f"{same['maximum_profile_difference_K']:.3f}" if same else 'Pending'])+r' \\')
        parts += [r'\begin{table}[H]\centering\scriptsize\begin{tabular}{lrr}\toprule Native tolerance & Versus intended midpoint [K] & Versus inherited expression [K]\\\midrule',
            '\n'.join(rows),r'\bottomrule\end{tabular}\end{table}',
            'The last column repeats the independent assembly with the inherited shifted temperature solely to diagnose the old native implementation. It does not replace the intended midpoint model, and agreement is not physical validation. Exact row-event scheduling remains a separate check.']
    if inherited and corrected and paired:
        fig,axes=plt.subplots(1,2,figsize=(8.6,3.25),constrained_layout=True)
        for d,label,color,marker in [(inherited,'Inherited routine','#B04A32','o'),(corrected,'Corrected midpoint','#154B8A','x')]:
            x=[a['predictions']['midpoint'] for a in d['results']]
            y=[a['native_alpha'] for a in d['results']]
            axes[0].loglog(x,y,marker,ls='none',label=label,color=color,ms=5)
        lower=min(a['native_alpha'] for a in inherited['results'])*.5
        upper=max(a['native_alpha'] for a in inherited['results'])*2
        axes[0].loglog([lower,upper],[lower,upper],'--',color='.4',lw=.8)
        axes[0].set(xlabel='Intended midpoint conversion',ylabel='Native conversion',title='Prescribed-temperature verification')
        axes[0].legend(fontsize=7)
        h=paired['history'];axes[1].plot([a['time_s'] for a in h],[a['max_live_profile_difference_K'] for a in h],color='#154B8A')
        axes[1].axvline(7,color='.4',ls='--',lw=.8)
        axes[1].set(xlabel='Time [s]',ylabel='Largest native-pair difference [K]',title='Default versus tighter tolerance')
        fig.savefig(out/'temperature_convention_checks.pdf');fig.savefig(out/'temperature_convention_checks.png',dpi=180);plt.close(fig)
        parts += [r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/temperature_convention_checks.pdf}\caption{Separate software checks of the reaction-time convention and nonlinear solver tolerance. The dashed diagonal is exact midpoint agreement; the vertical line marks the imposed seven-second heating pulse. These are numerical verification results, not measured motor behaviour.}\end{figure}']
    return parts
