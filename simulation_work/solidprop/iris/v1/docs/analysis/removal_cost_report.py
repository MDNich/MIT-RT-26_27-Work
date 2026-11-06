"""Describe a change to the assumed removal enthalpy at fixed exposure."""
import json
from pathlib import Path

import matplotlib.pyplot as plt

from continuous_heating_campaign import digest
from ops import ROOT


def build(cases,inputs):
    def track(path):
        value=digest(path)
        inputs[str(path.relative_to(ROOT))]=value
        return value
    path=ROOT/'validation/evolving_removal_cost.json'
    track(path)
    record=json.loads(path.read_text())
    plan_path=ROOT/'configs/evolving_removal_cost.json'
    assert track(plan_path)==record['plan_sha256']
    plan=json.loads(plan_path.read_text())
    assert all(track(ROOT/name)==fingerprint for name,fingerprint in plan['inputs'].items())
    assert not record['native'] and not record['eligible_for_motor_lifetime']
    assert set(record['cases'])=={f"{j['case']}_cost{j['cost_J_kg']/1e6:g}" for j in plan['jobs']}
    baseline=ROOT/'validation/liner_exhaustion_energy.json'
    track(baseline)
    nominal=json.loads(baseline.read_text())['cases']
    rows=[]
    fig,ax=plt.subplots(figsize=(6.7,2.5),layout='constrained')
    for name,label,color in cases:
        endpoints=[]
        table=[]
        for x in (17.5,35,70):
            if x==35:
                event=nominal[name]['1000']['event_s']
                passed=True
            else:
                item=record['cases'][f'{name}_cost{x:g}']
                assert item['cost_J_kg']==1e6*x
                passed=item['numerical_checks_passed']
                event=item['event_s']
            endpoints.append(event if passed else float('nan'))
            table.append(f'{event:.1f}' if passed else 'Unresolved')
        ax.plot([17.5,35.,70.],endpoints,'o-',color=color,label=label,lw=1.4,ms=4)
        rows.append(' & '.join([label]+table)+r' \\')
    ax.set(xlabel='Assumed energy to remove char [MJ/kg of char]',ylabel='Exposure to liner loss [s]',
           xticks=[17.5,35,70])
    ax.legend(ncol=2,fontsize=8,frameon=False)
    plot=ROOT/'docs/analysis/evolving_removal_cost.png'
    fig.savefig(plot,dpi=185);plt.close(fig);track(plot)
    text=r'''\section{How strongly does the char-removal assumption affect time?}\label{sec:removal}
The local surface law charges an effective energy $L_c$ for each kilogram of
char removed. The earlier energy inventory shows why this coefficient matters.
To vary it in isolation, we keep the gas at 2504~K and 800~psi, the nominal
film coefficient at 1000~W/(m$^2$~K), and the same kinetics, char yield,
case geometry and casing response. We solve again with half and twice the
inherited $35$~MJ/kg. These values bracket an assumption. No Iris sample
measurement establishes a probability distribution or physical bounds.

\begin{center}\begin{tabular}{lrrr}\toprule
&\multicolumn{3}{c}{Independent time from exposure to liner loss [s]}\\
Motor & 17.5 MJ/kg & 35 MJ/kg & 70 MJ/kg\\\midrule
ROWS
\bottomrule\end{tabular}\end{center}
\begin{figure}[H]\centering\includegraphics[width=.96\textwidth]{../analysis/evolving_removal_cost.png}
\caption{The symbols are separate finite-volume simulations. Lines join the
sampled settings. The Al and CF backings evolve during every case.}
\end{figure}

An increased removal cost leaves less of the incoming heat available to
consume char at the surface. Temperature, heat transfer from the gas,
and the available char also change during each run. The time therefore need
not scale in direct proportion to $L_c$. The time-step and radial mesh checks
use separate refinements. Each published value passes the time, thickness and
mass/energy checks, and has a separate nodal finite-element comparison.

A useful calibration would measure the applied heat flux, time-resolved
surface recession and remaining char for a specimen of the actual liner.
A residual thickness alone cannot separate excessive heating from an
underestimated removal cost. The film study varies the heat load separately.
\clearpage
'''
    out=ROOT/'docs/en/continuous_removal_cost.tex'
    out.write_text(text.replace('ROWS','\n'.join(rows)))
    track(out)
    track(Path(__file__).resolve())
