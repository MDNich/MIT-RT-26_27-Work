"""Build the four-case summary and the thermal consequences of CF decomposition."""
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def build(inputs, film_ranges):
    def track(p):
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        inputs[str(p.relative_to(ROOT))]=sha
        return sha
    def read(name,wanted=None):
        p=ROOT/name
        actual=track(p)
        if wanted and actual!=wanted: raise ValueError('Evidence fingerprint mismatch: '+name)
        return json.loads(p.read_text())
    audit=read('validation/cf_backing_audit.json')
    plan=read('configs/cf_backing_campaign.json',audit['plan_sha256'])
    coupon=read('validation/cf_backing_coupon.json',plan['coupon_sha256'])
    al=read('validation/aluminium_backing_audit.json')
    assert all(v[key] for case in audit['comparisons'].values() for n,v in case.items() if n in ('mesh','time')
               for key in ('brackets_overlap','thickness_pass','event_under_5_percent'))
    fig,axes=plt.subplots(1,2,figsize=(7.5,2.85),layout='constrained')
    rows,summary=[],[]
    for stage,label,color in [('sustainer','Sustainer','#264e78'),('booster','Booster','#a85527')]:
        case=stage+'_cf'
        tag=case+'_reacting_fine'
        d=read('validation/cf_backing_cases/'+tag+'.json',audit['records'][tag]['sha256'])
        hist,ev=d['history'],d['events']
        half_i,half_o,ceiling,end=(ev[k][1] for k in ('inner_pool_half','outer_pool_half','first_1000C','exhaustion'))
        left=next(r['remaining_mm'] for r in hist if r['time_s']==ceiling)
        rows.append(f'{label} & {half_i:.1f} & {half_o:.1f} & {ceiling:.1f} & {left:.2f} & {end:.1f} '+r'\\')
        al_tag=stage+'_al_phase_n640_ms20_mK500'
        al_event=al['records'][al_tag]['events']
        summary.extend([f'{label} Al & {hist[0]["remaining_mm"]:.2f} & {al_event["exhaustion"][1]:.1f} & All Al liquid at {al_event["all_liquid"][1]:.1f} s '+r'\\',
                        rf'{label} CF & {hist[0]["remaining_mm"]:.2f} & {end:.1f} & Casing reaches 1000 $^\circ$C at {ceiling:.1f} s '+r'\\'])
        t=np.array([r['time_s'] for r in hist])
        i=np.searchsorted(t,ceiling)
        data=[100*(1.-np.array([r['backing_retained_kg_per_rad_m'] for r in hist])/hist[0]['backing_retained_kg_per_rad_m']),
              np.array([r['remaining_mm'] for r in hist])]
        for ax,values in zip(axes,data):
            ax.plot(t[:i+1],values[:i+1],color=color,label=label)
            ax.plot(t[i:],values[i:],color=color,ls='--')
            ax.plot(t[i],values[i],'o',color=color,ms=4)
    axes[0].set_ylabel('Casing mass lost [%]')
    axes[1].set_ylabel('Remaining phenolic [mm]')
    for ax in axes:
        ax.set_xlabel('Continuous heating [s]')
        ax.grid(alpha=.23)
        ax.legend(frameon=False,fontsize=8)
    plot=ROOT/'docs/analysis/cf_backing_response.png'
    fig.savefig(plot,dpi=180)
    plt.close(fig)
    track(plot)
    executive=r"""
\section*{How long until the gas reaches the casing?}
For the sustained nominal load, the independent moving-wall calculation
exposes the casing after about 104--111 s in the sustainer and 138--148 s in
the booster. The clock starts when hot gas first reaches bare phenolic.
Burnthrough occurs when the moving char surface reaches the casing.
\begin{table}[H]\centering
\begin{tabular}{lrrl}\toprule
Motor & Liner [mm] & Liner gone [s] & Earlier casing event \\\midrule
SUMMARY
\bottomrule\end{tabular}
\end{table}
The calculation applies 2504 K gas continuously at 800 psi with an initial
film coefficient of 1000 W/(m$^2$ K), gas blowing and zero hot-side radiation.
The Al comparison follows pure-metal fusion and retains the molten metal in
place. The CF comparison follows oxygen-free T700/M21 resin decomposition
and holds the residue in place. The study has no measured Iris wall heat flux
or fired-liner recession. All four times therefore describe the stated thermal
scenarios. The casing can lose pressure capacity while phenolic remains.

\paragraph{What most affects the estimate.}
Halving and doubling the nominal film coefficient gives SUSTAINERRANGE s for
the sustainers and BOOSTERRANGE s for the boosters with the evolving casings.
Section~\ref{sec:film} gives all twelve times and the heat flux entering the
liner. These are sustained-load scenarios. A measured firing heat-flux history
and liner recession would constrain the physical estimate.

\paragraph{Verification.}
The four nominal burnthrough times come from a conservative radial finite-volume
solver. A second finite-element calculation from ignition gives endpoints within
0.073 s for all four cases (Section~\ref{sec:sectorcheck}). Both use the same
gas exposure and material inputs. Continuous-exposure verification in native
ANSYS remains open.
\clearpage
""".replace('SUMMARY','\n'.join(summary))
    executive=executive.replace('SUSTAINERRANGE',film_ranges[0]).replace('BOOSTERRANGE',film_ranges[1])
    body=r"""
\section{CF casing heat, gas loss and liner exposure}\label{sec:coupledcf}
The backing now feeds its changing mass, heat storage and through-thickness
conductivity back into the thermal solution. Gas at 2504 K continues to heat
the liner. The resin's two competing rates follow Section~\ref{sec:cfdiag}.
Each casing cell releases gas at its own temperature into an assumed separate
vent. This leaves the liner-side blowing calculation dependent on phenolic
gas alone. The radial model holds the decomposed casing in its original shape.

\begin{table}[H]\centering\begin{tabular}{lrrrrr}\toprule
 & \multicolumn{2}{c}{Half reactive pool [s]} & Casing at & Liner then & Liner gone \\
Motor & Inner cell & Outer cell & 1000 $^\circ$C [s] & [mm] & [s] \\\midrule
ROWS
\bottomrule\end{tabular}\end{table}
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/cf_backing_response.png}
\caption{Gas release as a percentage of initial casing mass and remaining liner for the nominal reacting CF
cases. Dots show the first backing temperature of 1000 $^\circ$C. Dashed
segments hold the upper-end residue and gas properties beyond this limit.
Virgin-property fits reach their own limits at lower temperatures.}
\end{figure}
At liner exhaustion the surrogate releases 24.6\% of the sustainer casing
mass and 22.7\% of the booster casing mass. The detailed backing changes the
nominal liner time by +0.32 and +0.28 s respectively relative to the inert
CF baseline. Changing the catalyst coefficient alone shifts these results by
+0.084 and +0.122 s. The local resin, bond and layup in Iris are unknown.
No structural failure time is inferred.

\paragraph{Local thermodynamics.}
For competing extents $a_1,a_2$, define $x=0.554a_1+0.9479a_2$,
$\rho=1575-410x$ in kg/m$^3$ and $\Delta g_i=410\chi_i\Delta a_i V$ in kg.
The remaining cell mass is $m=\rho V$. With sensible enthalpies measured
from 22 $^\circ$C, the reaction substep closes
\[
 (mh_s)_{j+1}-(mh_s)_j=\sum_i Q_i\Delta g_i-h_g(T_{1/2})\sum_i\Delta g_i.
\]
Here $Q_1=+259.54$ and $Q_2=-152.22$ kJ per kg of generated gas, following
the density-loss source in Tranchard et al., Part II. Positive $Q_i$ adds heat.
The model mixes virgin and degraded sensible enthalpies by $x$. Differentiating
this stored energy includes its composition dependence.
\clearpage
\section{CF transport properties and numerical checks}
The model mixes normal conductivity and specific heat between virgin and
degraded states using $x$. For temperature $T$ in $^\circ$C the virgin
fits are $c_v=687.31+2.8773T$ and $k_v=0.61391+0.0011113T$.
The corresponding upper fit limits are 300 and 150 $^\circ$C. The frozen
endpoint value is used outside either fit. The degraded and gas fits below
use a 20--1000 $^\circ$C interval, also with endpoint continuation:
\begin{align*}
 c_d &=662.53+2.599T-2.0761\,10^{-3}T^2+5.1327\,10^{-7}T^3,\\
 k_d &=0.077211+2.3397\,10^{-4}T-4.1903\,10^{-7}T^2+7.4228\,10^{-10}T^3,\\
 c_g &=1256.6+1.0610T-9.2485\,10^{-4}T^2+3.5977\,10^{-7}T^3 .
\end{align*}
Specific heats use J/(kg K) and conductivities W/(m K). Integrating each
bounded heat-capacity function gives its sensible enthalpy. Local radial
conductances include the logarithmic resistance of both adjacent annular
half-cells. The thermal substep iterates conductivity with temperature.
The adiabatic reaction substep advances both pathways against a common
reactant pool and solves for temperature from the open-system energy
equation. A trial repeats at a smaller time step if the reaction fails to
converge or if either cell's total channel advance exceeds 0.04.
The backing vent removes gas enthalpy once at generation. Gas pressure,
internal transport work, swelling and delamination are outside this closure.
\href{https://doi.org/10.3390/ma10050494}{Material measurements, Part I};
\href{https://doi.org/10.3390/ma10050470}{thermal model, Part II}.

\paragraph{Checks.}
A two-cell coupon with a constant outside heat input compares this split solver
against an independent temperature-form ODE. Over 28 s the finest 0.01 s step
gives at most 0.032 K temperature error and 0.0011 absolute error in either
pathway. Both nominal motor pairs pass their mesh and time checks on the
event brackets and remaining thickness. The finest comparisons use 640/160
liner/casing cells and a 0.02 s ceiling. Across the eight runs, each recorded
profile independently reconstructs casing mass and total sensible enthalpy.
An interrupted warm coupon recovered both reaction channels and produced
identical final files after restart. These checks test the specified equations.
Quantitative prediction for Iris still depends on a measured heat load,
recession calibration and material-specific validation.
\clearpage
""".replace('ROWS','\n'.join(rows)).replace("either cell's","any cell's")
    for file,content in [('continuous_executive.tex',executive),('continuous_coupled_cf.tex',body)]:
        p=ROOT/'docs/en'/file
        p.write_text(content)
        track(p)
    track(Path(__file__).resolve())
