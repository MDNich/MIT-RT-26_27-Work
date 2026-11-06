"""Summarise the audited one-factor input scenarios with evolving casings."""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from backing_film_campaign import read
from evolving_exposure_sensitivities import OUT, PLAN, WORK, SCENARIOS
from ops import ROOT
from continuous_heating_campaign import digest


def build(cases, inputs):
    def track(path):
        fingerprint = digest(path)
        inputs[str(path.relative_to(ROOT))] = fingerprint
        return fingerprint

    results, plan, done = read(OUT), read(PLAN), read(WORK/'complete.json')
    assert not results['native'] and not results['eligible_for_motor_lifetime']
    assert track(OUT)==done['audit_sha256'] and track(PLAN)==done['plan_sha256']==results['plan_sha256']
    assert all(track(ROOT/name)==sha for name,sha in plan['sources'].items())
    assert set(results['cases'])=={job['case']+'_'+job['scenario'] for job in plan['jobs']}
    baseline = ROOT/'validation/liner_exhaustion_energy.json'
    track(baseline)
    energy = read(baseline)
    assert energy['passed']
    summaries = {job['scenario']:job['change'] for job in plan['jobs']}
    gas_K = [summaries['gasdelta90']['heating']['gas_temperature_C']+273.15, 2504.,
             summaries['gasdelta110']['heating']['gas_temperature_C']+273.15]
    table, doses = [], []
    rejected, timing, thickness = [], [], []
    fig, axes = plt.subplots(1,3,figsize=(7.3,2.65),layout='constrained',sharey=True)
    for name, label, color in cases:
        nominal = energy['cases'][name]['1000']['event_s']
        endpoints, radiation = {}, []
        for scenario in SCENARIOS:
            result = results['cases'][name+'_'+scenario]
            if result['numerical_checks_passed']:
                assert all(v['passed'] for v in result['FV_checks'].values())
                assert result['common_history']['differences']['remaining_mm']['max_abs']<=result['thickness_limit_mm']
                assert abs(result['nodal_event_s']/result['FV_event_s']-1) < plan['event_relative']
                for tag, item in result['sources'].items():
                    assert digest(WORK/'cases'/(tag+'.json'))==item['record']
                    assert digest(WORK/(tag+'_checkpoint.json'))==item['checkpoint']
                assert digest(WORK/'cases'/(name+'_'+scenario+'_nodal.json'))==result['nodal_sha256']
                timing.append(abs(result['nodal_event_s']-result['FV_event_s']))
                thickness.append(result['common_history']['differences']['remaining_mm']['max_abs'])
                endpoints[scenario] = result['FV_event_s']
            else:
                rejected.append((label,scenario))
                endpoints[scenario] = float('nan')
            if scenario in ('rad10','rad30'):
                if result['numerical_checks_passed']:
                    film,rad = result['film_dose_MJ_m2'],result['radiation_dose_MJ_m2']
                    radiation += [f'{rad:.1f}',f'{100*rad/(film+rad):.1f}']
                else:
                    radiation += ['---','---']
        table.append(' & '.join([label]+[f'{endpoints[tag]:.1f}' if np.isfinite(endpoints[tag]) else '---'
                                         for tag in SCENARIOS])+r' \\')
        doses.append(' & '.join([label]+radiation)+r' \\')
        for ax, x, y in zip(axes,
                  [[600,800,1000],[0,.1,.3],gas_K],
                  [[endpoints['p600'],nominal,endpoints['p1000']],
                   [nominal,endpoints['rad10'],endpoints['rad30']],
                   [endpoints['gasdelta90'],nominal,endpoints['gasdelta110']]]):
            ax.plot(x,y,'o-',ms=3,lw=1.3,label=label,color=color)
    axes[0].set_ylabel('Time to liner exhaustion [s]')
    axes[0].set(xlabel='Pressure [psi]',xticks=[600,800,1000])
    axes[1].set(xlabel='Hot-side emissivity',xticks=[0,.1,.3])
    axes[2].set(xlabel='Gas temperature [K]',xticks=[2283,2504,2725])
    axes[0].legend(ncol=1,fontsize=6.5,frameon=False)
    figure = ROOT/'docs/analysis/evolving_input_sensitivities.png'
    fig.savefig(figure,dpi=190); plt.close(fig);track(figure)
    text = r'''\section{How do pressure, radiation and gas temperature affect liner loss?}\label{sec:env}
Each column below changes one input from the nominal 800~psi, 2504~K gas
and zero hot-side emissivity. The gas film coefficient before blowing stays
at 1000~W/(m$^2$ K). Each case starts cold with bare continuous phenolic
and its evolving Al or CF casing. Table entries give seconds until liner
exhaustion in the independent finite-volume model.

\begin{center}\small\begin{tabular}{lrrrrrr}\toprule
&\multicolumn{2}{c}{Pressure [psi]}&\multicolumn{2}{c}{Emissivity}&\multicolumn{2}{c}{Gas [K]}\\
Motor&600&1000&0.10&0.30&2283&2725\\\midrule
ROWS
\bottomrule\end{tabular}\end{center}
\begin{figure}[H]\centering\includegraphics[width=.98\textwidth]{../analysis/evolving_input_sensitivities.png}
\caption{Symbols are separate calculations. A line connects runs with
the other physical inputs fixed. These scenarios do not define a statistical
uncertainty interval.}
\end{figure}
Pressure enters the surface char law. Gas temperature sets the convective
driving temperature. The chosen hot and cold gas scenarios scale the initial
gas-to-wall temperature difference by 1.1 and 0.9 respectively. In the
radiative scenarios, the emitting gas is held at 2504~K. Changing emissivity
also changes the wall temperature, convective heating and exposure duration.
The table gives cumulative radiative energy per original exposed area and
its fraction of total convective plus radiative input.

\begin{center}\small\begin{tabular}{lrrrr}\toprule
&\multicolumn{2}{c}{Emissivity 0.10}&\multicolumn{2}{c}{Emissivity 0.30}\\
Motor & [MJ/m$^2$] & Share [\%]& [MJ/m$^2$] & Share [\%]\\\midrule
DOSES
\bottomrule\end{tabular}\end{center}
CHECKS The heat load and char chemistry still require measurements on the
actual firing and liner. Each reported endpoint assumes that the casing
keeps its prescribed geometry after its material limit.
\clearpage
'''
    if not timing:
        checks = 'No scenario met all the numerical acceptance criteria.'
    else:
        checks = (f'{len(timing)} of {len(results["cases"])} scenarios passed the inventory and separate time-step and mesh '
                  f'checks. Across those runs the largest independent nodal endpoint difference was {max(timing):.2f}~s '
                  f'and the largest sampled thickness difference was {1000*max(thickness):.1f}~$\\mu$m.')
    if rejected:
        checks += ' A dash marks a case that did not pass every numerical check.'
    output = ROOT/'docs/en/continuous_evolving_inputs.tex'
    output.write_text(text.replace('ROWS','\n'.join(table)).replace('DOSES','\n'.join(doses)).replace('CHECKS',checks))
    track(output)
    track(Path(__file__).resolve())
