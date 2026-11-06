"""Build the measured-property surrogate sections from audited case records."""
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def build(inputs):
    def read(name, expected=None):
        p=ROOT/name
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        if expected and sha!=expected: raise ValueError(f'Source hash changed for {name}')
        inputs[name]=sha
        return json.loads(p.read_text())
    a=read('validation/aluminium_backing_audit.json')
    plan=read('configs/aluminium_backing_campaign.json',a['plan_sha256'])
    coupon=read('validation/aluminium_backing_coupon.json',plan['coupon_sha256'])
    cf=read('validation/cf_backing_one_way.json')
    assert cf['model_sha256']==hashlib.sha256((ROOT/'model/diagnose_cf_backing.py').read_bytes()).hexdigest()
    ref=read('validation/moving_surface_campaign_audit.json',cf['moving_audit_sha256'])
    assert all(p['brackets_overlap'] and p['thickness_pass'] and p['event_under_5_percent']
               for g in a['comparisons'].values() for p in g.values())
    fig,axes=plt.subplots(1,2,figsize=(7.4,2.85),layout='constrained')
    alrows=[]
    cfrows=[]
    for case,name,color in [('sustainer','Sustainer','#274e78'),('booster','Booster','#b65b26')]:
        tag=case+'_al_phase_n640_ms20_mK500'
        d=read('validation/aluminium_backing_cases/'+tag+'.json',a['records'][tag]['record_sha256'])
        h,ev=d['history'],d['events']
        t=np.array([r['time_s'] for r in h])
        flag,first,full,end=(ev[k][1] for k in ('property_flag','first_melt','all_liquid','exhaustion'))
        at_full=next(r for r in h if r['time_s']==full)
        alrows.append(f'{name} & {flag:.1f} & {first:.1f} & {full:.1f} & {end:.1f} & {at_full["remaining_mm"]:.2f} '+r'\\')
        cut=np.searchsorted(t,flag)
        for ax,field,factor in [(axes[0],'remaining_mm',1.),(axes[1],'mass_fraction_liquid',100.)]:
            y=np.array([r[field] for r in h])*factor
            ax.plot(t[:cut+1],y[:cut+1],color=color,label=name)
            ax.plot(t[cut:],y[cut:],color=color,ls='--')
            for s,marker in ((first,'o'),(full,'s')):
                i=np.searchsorted(t,s)
                ax.plot(t[i],y[i],marker,color=color,ms=4)
        cfgroup=cf['cases'][case+'_cf']['moving640_time02']
        assert cfgroup['thermal_history_sha256']==ref['records'][case+'_cf_moving640_time02']['record_sha256']
        for k,location in [('interface_C','Liner side'),('outer_C','Outside')]:
            v=cfgroup['outputs'][k];b=v['table5']
            cfrows.append(f"{name} & {location} & {b['0.1']['time_s']:.1f} & {b['0.5']['time_s']:.1f} & "
                          f"{b['0.9']['time_s']:.1f} & {b['0.5']['temperature_C']:.0f} "+r'\\')
    axes[0].set(ylabel='Retained liner [mm]',xlabel='Continuous exposure [s]',ylim=(0,None))
    axes[1].set(ylabel='Liquid backing mass [%]',xlabel='Continuous exposure [s]',ylim=(-3,104))
    axes[0].legend(fontsize=8)
    for ax in axes: ax.grid(alpha=.2)
    plot=ROOT/'docs/analysis/al_backing_phase.png'
    fig.savefig(plot,dpi=190)
    plt.close(fig)
    text=r'''\section{Melting in a retained aluminium backing}\label{sec:almelt}
The original aluminium cases use constant specific heat. The alternative
stores the heat of fusion and allows the backing to become liquid while
retaining its initial mass, shape, radial conductivity of 167 W/(m K) and
density of 2700 kg/m$^3$. Gas loading, liner chemistry and dimensions match the
nominal cases in Table~1. The extra heat absorbed by the casing delays liner
exhaustion by 3.7 s in the sustainer and 5.2 s in the booster.

\begin{table}[H]\centering\begin{tabular}{lrrrrr}\toprule
 & Property & First & All cells & Liner & Liner at full\\
Case & flag [s] & melt [s] & liquid [s] & gone [s] & melt [mm]\\\midrule
ALROWS
\bottomrule\end{tabular}\end{table}
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/al_backing_phase.png}
\caption{Solid curves end at the inherited 300 $^\circ$C property flag. Dashes
continue with the retained pure-Al surrogate. Circles mark the first cell with
liquid and squares mark the first instant when all casing cells are liquid.}\end{figure}
At complete modelled melting the liner still covers the case in both geometries.
Following the liner further assumes the liquid stays in place. Pressure
containment, flow of molten metal, alloy solidus and local wall defects need
separate evidence.

The caloric law uses the crystal and liquid rows on the same
\href{https://janaf.nist.gov/tables/Al-001.html}{NIST-JANAF enthalpy reference}.
At 933.45 K the 10.711 kJ/mol jump corresponds to 397.0 kJ/kg. The solver joins
the two sensible branches across a narrow numerical melting interval, then
recovers liquid fraction from the sharp equilibrium enthalpy. Ten integrations
separate mesh, time-step and interval-width changes. The reported runs use
640/160 cells, a 0.02 s step ceiling and a 0.5 K interval. Across the eight
single-parameter comparisons the greatest liner-event shift was MAXSHIFT s.
All eight satisfy the thickness and final-interval overlap checks. An externally
heated char/Al coupon agrees with an independent sharp-transition enthalpy ODE
to COUPONERR K at the finest setting.

\clearpage\section{Resin reaction on the CF temperature histories}\label{sec:cfdiag}
A separate calculation applies the two competing T700/M21 reactions measured
under nitrogen to the liner-side and outside temperatures of the published
CF cases. The heat histories are prescribed. Heat absorption, gas transport
and the changing composite conductivity would have to feed back into the wall
to revise a CF liner-exhaustion time.

Let $u=1-a_1-a_2$ denote the fraction of the shared reactant still available.
With $T$ in kelvin and $k_j=A_j\exp[-E_j/(RT)]$ in s$^{-1}$, the rates are
\[
 \dot a_1=k_1 u^{1.1125},\qquad \dot a_2=k_2 u^{2.0825}(1+K_{\rm cat} a_2).
\]
The frequency factors are 7.2193 and $5.3309\times10^8$ s$^{-1}$, and the
activation energies are 58.7107 and 146.674 kJ/mol. The table uses
$K_{\rm cat}=7.4886$ from Table 5 of the experimental paper. The model equations
and competitive mass-loss weights are given in its companion paper.
\href{https://doi.org/10.3390/ma10050494}{Tranchard et al., Part I};
\href{https://doi.org/10.3390/ma10050470}{Part II}.

\begin{table}[H]\centering\begin{tabular}{llrrrr}\toprule
 & & \multicolumn{3}{c}{Time to reactant conversion [s]} & At 50\%\\
\cmidrule(lr){3-5}Case & Casing location & 10\% & 50\% & 90\% & [$^\circ$C]\\\midrule
CFROWS
\bottomrule\end{tabular}\end{table}

Here 50\% means half of the common reactive pool has advanced by either
pathway. Reconstructing mass with the paper's density change and pathway
weights gives about 12.3\% loss of the initial composite mass at that point.
The printed $\log_{10} K_{\rm cat}=-0.8744$ in Part I, Table 3 implies
a smaller coefficient. Using that interpretation delays the four 50\% times
by 3.0--4.1 s. The calculations stop at 99.9\% common conversion, 1000
$^\circ$C, or the end of the supplied temperature history, whichever occurs first.

The local rates of temperature rise at 50\% conversion are 492--697
$^\circ$C/min, above the reported nitrogen tests at 5--100 $^\circ$C/min.
The Iris casing resin and layup are unspecified. These times identify when a
reacting backing can affect the heat balance. The following section couples heat storage, radial
conductivity, decomposition energy and escaping gas to both motor geometries.
\clearpage
'''
    shift=max(abs(v['event_difference_s']) for g in a['comparisons'].values() for v in g.values())
    text=text.replace('ALROWS','\n'.join(alrows)).replace('CFROWS','\n'.join(cfrows)).replace('MAXSHIFT',f'{shift:.3f}')
    text=text.replace('COUPONERR',f"{coupon['runs'][-1]['maximum_Al_temperature_error_K']:.2f}")
    tex=ROOT/'docs/en/continuous_backing_results.tex'
    tex.write_text(text)
    for p in (tex,plot,Path(__file__)):
        inputs[str(p.resolve().relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
