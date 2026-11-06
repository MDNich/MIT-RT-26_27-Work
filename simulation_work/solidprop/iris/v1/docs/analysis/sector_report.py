"""Compare the audited radial FE and finite-volume histories on common times."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from continuous_heating_campaign import digest
from ops import ROOT,atomic


def build(cases,inputs):
    def register(path):
        inputs[str(path.relative_to(ROOT))]=digest(path)
        return path
    def read(path):
        return json.loads(register(path).read_text())
    audit=read(ROOT/'validation/sector_exposure_reduction.json')
    for name,sha in audit['sources'].items():
        assert digest(ROOT/f'model/{name}.py')==sha
    assert audit['passed']
    guest=read(ROOT/'validation/sector_guest_preflight.json')
    assert guest['passed'] and len(guest['stations'])==4
    assert digest(ROOT/'model/check_sector_guest.py')==guest['audit_sha256']
    pkg=ROOT/'configs/native_verification/whole_sector_r1'
    assert digest(pkg/'controller.zip')==guest['package_sha256']
    import zipfile
    with zipfile.ZipFile(pkg/'controller.zip') as archive:
        assert archive.read('sector_mapdl.py')==(ROOT/'model/sector_mapdl.py').read_bytes()
    for p in [ROOT/'model/sector_mapdl.py',pkg/'pilotwal.inp',pkg/'manifest.json',ROOT/'model/check_sector_guest.py']:
        register(p)
    slim=ROOT/'validation/sector_exposure_profiles.json'
    if not slim.exists():
        selected={}
        root=ROOT/'ansystmp/sector_reduction'/audit['sources']['check_sector_exposure'][:12]
        for case,_,_ in cases:
            rec=audit['cases'][case]['runs'][-1]
            path=root/(case+'_160_0.02.json')
            assert digest(path)==rec['record_sha256']
            selected[case]=dict(sha256=digest(path),samples=json.loads(path.read_text())['record']['stats']['samples'])
        atomic(slim,selected)
    data=read(slim);rows=[]
    fig,axes=plt.subplots(2,1,figsize=(7.0,3.1),layout='constrained',sharex=True)
    max_thickness=max_interface=0.
    for case,label,color in cases:
        rec=audit['cases'][case];fine=rec['runs'][-1]
        assert data[case]['sha256']==fine['record_sha256']
        cf=case.endswith('cf')
        suffix='_reacting_fine' if cf else '_phase_n640_ms20_mK500'
        mat='cf' if cf else 'aluminium'
        p=ROOT/f'validation/{mat}_backing_cases/{case}{suffix}.json'
        fv=read(p)
        fva=read(ROOT/f'validation/{mat}_backing_audit.json')
        src=fva['records'][case+suffix]
        assert digest(p)==src.get('sha256',src.get('record_sha256'))
        ref=fv['history']
        x=np.array([s['time_s'] for s in ref])
        samples=[s for s in data[case]['samples'] if s['time_s']<x[-1]]
        t=np.array([s['time_s'] for s in samples])
        for ax,key,factor in zip(axes,['remaining_mm','interface_C'],[1000.,1.]):
            d=(np.array([s[key] for s in samples])-np.interp(t,x,[s[key] for s in ref]))*factor
            if key=='remaining_mm': max_thickness=max(max_thickness,max(abs(d)))
            else: max_interface=max(max_interface,max(abs(d)))
            ax.plot(t,d,color=color,lw=1.2,label=label)
        cols=[label,f"{rec['FV_reference_s']:.2f}",*[f"{r['events']['exhaustion'][1]:.2f}" for r in rec['runs']]]
        rows.append(' & '.join(cols)+r' \\')
    axes[0].set_ylabel(r'Liner [$\mu$m]')
    axes[1].set_ylabel(r'Interface [K]')
    axes[1].set_xlabel('Time from first exposure [s]')
    axes[0].legend(ncol=4,fontsize=8)
    for ax in axes: ax.axhline(0,color='#666666',lw=.5,zorder=0)
    img=ROOT/'docs/analysis/sector_method_difference.png'
    fig.savefig(img,dpi=200);plt.close(fig);register(img)
    tex=r'''\section{A second calculation from ignition to liner exhaustion}\label{sec:sectorcheck}
A second implementation places temperature, virgin mass and char mass at the
nodes of a moving finite-element mesh. The preceding finite-volume calculation
stores its material state at cell centres and solves for a separate surface
temperature. Both follow the same assumed heat exposure and backing properties.
The finite-element results below use the radial reduction of the sector equations,
evaluated on the Mac. Sections~\ref{sec:nativebench}--\ref{sec:coupledends} give the separate Windows MAPDL checks.

\begin{table}[H]\centering\begin{tabular}{lrrrr}\toprule
 & Finite volume & \multicolumn{3}{c}{Finite element [s]}\\
Case & 640/160 [s] & 80/20, 0.04 s & 160/40, 0.04 s & 160/40, 0.02 s \\\midrule
ROWS
\bottomrule\end{tabular}\end{table}
The mesh pairs count liner and casing intervals. The solver shortens steps
at rapid reaction, fusion, front motion and output stations. In these twelve
runs, doubling the radial resolution changed the endpoint by at most 0.10 s.
Halving the time step changed it by at most 0.061 s. The largest difference
between the finest two methods was 0.073 s.

\begin{figure}[H]\centering\includegraphics[width=.95\textwidth]{../analysis/sector_method_difference.png}
\caption{Finite element minus finite volume at common exposure times, sampled
every half second before either run ends. The upper panel shows remaining liner
thickness and the lower panel shows liner--casing interface temperature.}
\end{figure}
The largest sampled thickness difference is THICK~$\mu$m and the largest
interface difference is INTER~K. All four cases pass their baseline casing
property limits. Both aluminium walls are wholly liquid in the retained-shape
model before liner exhaustion. Both CF walls pass 1000~$^\circ$C beforehand.
An uncertainty in the imposed heat transfer affects both numerical methods
in the same direction. Their agreement gives no independent calibration of
the actual firing heat or reaction rate.
\clearpage
\section{Thermal step and recession in the moving finite-element sector}
For a radial interval with boundaries $a,b$, the row-summed linear brick
allocates volume per radian and per axial metre $(b-a)(2a+b)/6$ to its inner
node. The outer node receives the remainder of $(b^2-a^2)/2$. The equivalent
dual-volume boundary is $r_d^2=a^2+(b-a)(2a+b)/3$. These volumes carry virgin
mass $m_v$, char mass $m_c$ and sensible enthalpy $m_vh_v+m_ch_c$. At the
liner--casing interface both material contributions enter one temperature equation.
With straight sector faces of angular width $\delta$, radial conductance and the
backward-Euler transport equation are
\[
 G_e=\frac{k_e(a+b)}{2(b-a)\cos^2(\delta/2)},\qquad
 (C/\Delta t+K+H)T^*=C T^n/\Delta t+f.
\]
$C$ is the diagonal secant heat capacity from the change of sensible enthalpy
at fixed composition. It includes heat absorbed in aluminium fusion. $H$ adds
the hot and ambient film terms. The ambient coefficient includes radiation
linearized at the current iterate. $f$ includes the gas and ambient temperature
terms, prescribed incident radiation and the surface energy consumed in
forming and heating the products. The local gas film uses the previous bulk
gas flow and the current surface product flow. Its reference gas temperature
is 2504 K. $T^*$ is the transported field before local reaction.

At the exposed node the reference char kinetics are multiplied by the fraction
$m_c/(m_c+Y m_v)$, where $Y=600/1250$ is the inherited char yield. For surface
flux $j$ and starting radius $r_0$, the step ends at $r_1$ satisfying
\[
 \int_{r_0}^{r_1}(\rho_c+Y\rho_v)\,r\,dr
   = \Delta t\,j\,\frac{r_0+r_1}{2\cos(\delta/2)} .
\]
Swept virgin material releases gas and supplies its char yield for consumption.
The surface ledger includes the sensible enthalpy swept out, the sensible
enthalpy of the exiting products, the heat of pyrolysis and the effective
char-removal cost. The retained mass and sensible enthalpy are distributed
over overlapping dual volumes. The code solves the temperature from enthalpy
again after bulk pyrolysis and after equilibration at the shared interface.
The time step is shortened to the instant the remaining convertible mass
reaches zero. Restarting each short verification path reproduced its complete
terminal state and ledgers. The largest cumulative energy discrepancy in the
twelve full exposures was below $10^{-7}$ of incident film heat.

The native implementation uses SOLID278 for conduction and MASS71
for the nodal thermal capacity beyond the solid element's unit volumetric
capacity. The radial predictor sets material coefficients. MAPDL then solves
the temperatures of all sector nodes with the hot and backing faces free. The
controller checks the returned field before updating chemistry or moving the
surface. The two short native jobs tested this exchange and the saved
fields before the four whole exposures.

An independent three-dimensional assembly on Windows parsed the actual generated
elements, nodal capacities, initial conditions and surface loads. Eight Gauss
points per brick integrated heat capacity and conduction. In addition to
ignition, the checks cover the first cell merge, aluminium fusion or CF above
1000~$^\circ$C, and the final live increment for each motor. The largest
temperature difference from the radial reduction was below $10^{-9}$ K.
These checks ran in the bundled Python interpreter. Running the same input
through the native solver tests an additional software boundary.
\clearpage
'''.replace('ROWS','\n'.join(rows)).replace('THICK',f'{max_thickness:.1f}').replace('INTER',f'{max_interface:.2f}')
    target=ROOT/'docs/en/continuous_sector_comparison.tex'
    target.write_text(tex)
    register(target);register(Path(__file__))
