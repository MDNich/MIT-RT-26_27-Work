"""Explain the order of magnitude using the audited terminal energy inventory."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from continuous_heating_campaign import digest
from ops import ROOT


def build(cases, inputs):
    def register(path):
        sha = digest(path)
        inputs[str(path.relative_to(ROOT))] = sha
        return sha

    proof_path = ROOT/'validation/liner_exhaustion_energy.json'
    register(proof_path)
    proof = json.loads(proof_path.read_text())
    assert proof['passed']
    assert register(ROOT/'model/audit_liner_energy.py') == proof['source_sha256']
    assert register(ROOT/'validation/evolving_backing_film_audit.json') == proof['film_audit_sha256']
    assert register(ROOT/'validation/sector_exposure_reduction.json') == proof['sector_audit_sha256']
    nominal = [proof['cases'][case]['1000'] for case,_,_ in cases]
    groups = [
        ('Char removal', '#365c77', ['char_removal']),
        ('Pyrolysis', '#be782f', ['pyrolysis']),
        ('Expelled liner products', '#7caaad', ['liner_products']),
        ('Heat stored in casing', '#a55650', ['stored_in_case']),
        ('Casing gas and reaction', '#887399', ['casing_gas','casing_net_reaction']),
        ('Heat lost to ambient', '#b7b9ae', ['ambient_loss'])]
    fig, ax = plt.subplots(figsize=(7.1,2.4),layout='constrained')
    left = np.zeros(len(nominal)); pos = np.arange(len(nominal))
    for label,color,keys in groups:
        values = [sum(r['FV']['partition_MJ_m2'][key] for key in keys) for r in nominal]
        ax.barh(pos,values,left=left,color=color,label=label,height=.57)
        left += values
    ax.set_yticks(pos,labels=[label for _,label,_ in cases])
    ax.invert_yaxis()
    ax.set_xlim(0,1.13*max(left))
    ax.set_xlabel('Heat per original exposed liner area [MJ/m²]')
    ax.yaxis.grid(False)
    ax.set_axisbelow(True)
    ax.legend(loc='lower left',bbox_to_anchor=(0,1.01),ncol=3,fontsize=8,frameon=False)
    for i, total in enumerate(left):
        ax.text(total+1,i,f'{total:.1f}',va='center',fontsize=8)
    image = ROOT/'docs/analysis/liner_energy_inventory.png'
    fig.savefig(image,dpi=190); plt.close(fig); register(image)
    data = [r for group in proof['cases'].values() for r in group.values()]
    ranges = {}
    for h in ('500','1000','2000'):
        temperatures = [group[h]['hottest_sampled_live_face_C'] for group in proof['cases'].values()]
        ranges[h] = f'{min(temperatures):.0f}--{max(temperatures):.0f}'
    sa, _, ba, _ = nominal
    text = r'''\section{Why the model gives minutes to liner loss}\label{sec:caloric}
When the liner disappears, every kilogram of initial phenolic has passed through
pyrolysis. In the specified chemistry, a fraction $y=0.48$ of that mass becomes
char and eventually leaves through the hot surface. For original hot radius $r_i$,
thickness $d$ and exposed area $A_0$, the original virgin mass per area follows
from the volume of the annulus. The model's total chemical energy cost is then
\[
  \frac{m_0}{A_0}=\rho_v d\left(1+\frac{d}{2r_i}\right),\qquad
  \frac{E_{\rm chem}}{A_0}=\frac{m_0}{A_0}(L_p+yL_c).
\]
The assumed costs are $L_p=0.418$ MJ per kg of virgin phenolic and $L_c=35$ MJ
per kg of expelled char. They give CHEMS and CHEMB MJ/m$^2$ for the sustainer
and booster, respectively. The calculation accounts separately for the sensible
heat leaving with reaction products, the heat retained by the casing and the
heat lost to ambient. For CF it also includes gas enthalpy and net resin reaction
energy.
\begin{figure}[H]\centering\includegraphics[width=0.97\textwidth]{../analysis/liner_energy_inventory.png}
\caption{Energy delivered by the film through complete liner loss at nominal heating.
The Al storage term includes fusion. The four bar totals use the same original-area
basis as the chemical energy calculation. Both backing surrogates retain their shape.}
\end{figure}
For the sustainer Al example, the computed film delivers DOSE MJ/m$^2$ at
a time-average rate of RATE MW/m$^2$ on the original area. Their ratio is
SECONDS s. The mean on the moving area in the preceding section is smaller
because that area grows. This division explains the solved duration. Both the
dose and the incident power come from the transient solution.

Across all twelve cases, CHARLOW--CHARHIGH\% of incident energy pays the assumed
char-removal cost. The two numerical methods agree on total dose to within
DOSEERR\%. A measured mass-loss and recession history under a known heat load
would test the effective cost and the prescribed char yield. Their product sets
the largest term in this estimate.

\paragraph{Gas and solid temperature.} The prescribed gas temperature is
2504 K (2231 $^\circ$C). Across the four motors the highest saved live hot-face
temperatures are LOWTEMP, MIDTEMP and HIGHTEMP $^\circ$C at the weaker, nominal
and stronger film coefficients respectively. These are maxima of the saved surface
samples. The burning gas, the exposed char and the casing interface have separate
temperatures.
\clearpage
'''
    fields = dict(CHEMS=f"{sa['analytic_reaction_MJ_m2']:.1f}",CHEMB=f"{ba['analytic_reaction_MJ_m2']:.1f}",
                  DOSEERR=f"{max(abs(r['FE_minus_FV_film_percent']) for r in data):.3f}",
                  DOSE=f"{sa['FV']['film_MJ_m2']:.1f}",RATE=f"{sa['mean_film_per_original_area_MW_m2']:.3f}",
                  SECONDS=f"{sa['event_s']:.1f}",CHARLOW=f"{min(r['FV']['char_percent'] for r in data):.1f}",
                  CHARHIGH=f"{max(r['FV']['char_percent'] for r in data):.1f}",
                  LOWTEMP=ranges['500'],MIDTEMP=ranges['1000'],HIGHTEMP=ranges['2000'])
    for name,value in fields.items():
        text = text.replace(name,value)
    path = ROOT/'docs/en/continuous_liner_energy.tex'
    path.write_text(text); register(path); register(Path(__file__).resolve())
