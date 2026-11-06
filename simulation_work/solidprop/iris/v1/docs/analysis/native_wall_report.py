"""Render only accepted native verification results from archived field exports."""
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from continuous_heating_campaign import digest
from ops import ROOT


def terminal_windows(register, read):
    group = read(ROOT/'validation/native_cf_window_refinement.json')
    assert group['passed'] and register(ROOT/'model/audit_native_cf_refinement.py') == group['source_sha256']
    assert register(ROOT/'configs/native_verification/cf_tail_char_smp10_r3/manifest.json') == group['manifest_sha256']
    fig, axes = plt.subplots(1,2,figsize=(7,2.35),layout='constrained')
    rows, differences = [], []
    field_error, energy = [], []
    for motor, color in [('Sustainer','#194b78'),('Booster','#a35635')]:
        case = group['cases'][motor.lower()+'_cf']
        for row in case['jobs']:
            job = row['job']
            evidence = ROOT/f'validation/native_cf_terminal_window_{job}.json'
            assert register(evidence) == row['evidence_sha256']
            field_error.append(row['max_field_error_K'])
            energy.append(row['absolute_energy_error_fraction'])
        times = [row['duration_s'] for row in case['jobs']]
        rows.append(' & '.join([motor, f"{case['start_s']:.2f}", f"{case['initial_mm']:.3f}"]+
                                [f"{t:.5f}" for t in times])+r' \\')
        for label, comparison in case['pairs'].items():
            differences.append(' & '.join([motor, 'Mesh' if label=='mesh' else 'Time step',
                f"{1000*comparison['event_delta_s']:+.3f}",
                f"{1000*comparison['max_thickness_delta_mm']:.3f}", f"{comparison['max_hot_face_delta_K']:.3f}"])+r' \\')
        t, depth, hot = np.array(case['history']).T
        for ax,y in zip(axes,[depth,hot]):
            ax.plot(t,y,label=motor+' CF',color=color)
            ax.plot(t[-1],y[-1],'o',color=color,ms=3)
    for ax in axes:
        ax.set_xlabel('Time since handoff [s]')
        ax.set_xlim(left=0)
    axes[0].set(ylabel='Char remaining [mm]',ylim=(0,None))
    axes[0].legend(fontsize=8)
    axes[1].set_ylabel('Exposed char surface [°C]')
    graph = ROOT/'docs/analysis/native_cf_terminal_windows.png'
    fig.savefig(graph,dpi=190)
    plt.close(fig)
    register(graph)
    text = r'''\section{How long the final char layer lasts in the CF cases}\label{sec:nativecfend}
At the first saved state where the modeled casing reaches $1000\,^\circ$C,
the independent calculation supplies the residual liner thickness, the radial
temperature profile and the subsequent temperature history at the casing.
MAPDL then solves heat conduction and surface recession until the char thickness
reaches zero. Less than six parts per million of the starting liner mass in
either window is still virgin material. We treat this residue as pure char.
If exhaustion takes longer than the supplied history, the interface holds its
last supplied temperature through the final fraction of the window.

\begin{center}\small\begin{tabular}{lrrrrr}\toprule
& Handoff & Char left &\multicolumn{3}{c}{Native duration from handoff [s]}\\
CF case & [s] & [mm] & 20 / 0.010 & 40 / 0.010 & 40 / 0.005\\\midrule
EVENTROWS
\bottomrule\end{tabular}\end{center}
The three column labels give radial cells and the maximum step in seconds.
Each run shortens its last step to the time needed to consume the remaining char.
\begin{figure}[H]\centering\includegraphics[width=.97\textwidth]{../analysis/native_cf_terminal_windows.png}
\caption{Finest native histories under the prescribed interface temperature.
Dots mark exhaustion at the end of each window.}\end{figure}
\begin{center}\small\begin{tabular}{llrrr}\toprule
CF case & Refinement & Event shift [ms] & Max.\ thickness & Max.\ hot face\\
& & & change [$\mu$m] & change [K]\\\midrule
DIFFROWS
\bottomrule\end{tabular}\end{center}
Mesh refinement doubles the cell count at a fixed 0.010~s step ceiling.
Time refinement halves that ceiling at a fixed 40 cells. A positive event
shift means the finer run reaches exhaustion later. For thickness and
temperature we compare every saved step of both runs over their shared duration
and linearly interpolate the other run at that time. The final-step time intervals
overlap for every pair.

The largest nodal discrepancy across the six runs against matched radial heat
solutions was FIELDERR~K. Summed absolute step energy discrepancies stayed
below ENERGYPC\% of the boundary energy exchanged in each run. The native
windows verify final char consumption conditional on the prescribed casing
temperature. A physical firing time also depends on the heat load and casing
response above the temperature covered by the CF properties.
\clearpage
'''
    return (text.replace('EVENTROWS','\n'.join(rows)).replace('DIFFROWS','\n'.join(differences))
            .replace('FIELDERR',f'{max(field_error):.4f}').replace('ENERGYPC',f'{np.ceil(1e5*max(energy))/1e3:.3f}'))


def coupled_endpoints(register, read):
    pkg=ROOT/'configs/native_verification/whole_sector_r2'
    proof=read(ROOT/'validation/terminal_brick_geometry.json')
    assert register(ROOT/'model/sector_terminal_step.py')==proof['step_sha256']
    signature=register(pkg/'controller.zip')
    register(pkg/'start2al.inp')
    startup=[]
    for job in ('start2al','start2cf'):
        result=read(ROOT/f'validation/native_sector_r2_{job}.json')
        assert result['passed'] and result['role']=='startup' and result['archive_sha256']==signature
        startup.append(result['max_field_error_K'])
    rows=[]
    max_error=0.
    for suffix,name in [('sa','Sustainer Al'),('sc','Sustainer CF'),('ba','Booster Al'),('bc','Booster CF')]:
        job='end2'+suffix
        result=read(ROOT/f'validation/native_sector_r2_{job}.json')
        settings=read(pkg/(job+'_settings.json'))
        assert result['passed'] and result['role']=='terminal' and result['archive_sha256']==signature
        assert digest(pkg/(job+'_settings.json'))==result['settings_sha256']
        state=settings['donor_record']['state']
        start=result['native_interval_start_s']
        assert start==state['time']
        nodes=state['nodes']
        left=(nodes[-1]-nodes[0])*1e6
        row=proof['cases']['wall'+suffix]
        rows.append(f"{name} & {start:.2f} & {left:.2f} & {result['native_blocks']} & "
                    f"{result['terminal_s']-start:.5f} & {row['candidate_peak_edge_ratio']:.2f}"+r' \\')
        max_error=max(max_error,result['max_field_error_K'])
    text=r'''\section{Native checks with an evolving casing}\label{sec:coupledends}
Here MAPDL solves temperatures through both the liner and the casing.
At the interface the liner and casing share one temperature degree of freedom.
The controller advances the aluminium fusion enthalpy or CF decomposition
after each native field solve. The hot surface moves according to the remaining
solid inventory and the calculated mass flux. Two cold-start pilots also
advanced virgin sustainer walls from ambient temperature through their first
0.1~s. Their largest difference from independently assembled nodal temperatures
was STARTERR~K.

\paragraph{Handoff near exhaustion.} The independent model supplied a complete
state about 0.2~s before its predicted event for each motor. From that state
MAPDL solved both sides of the interface until the last char disappeared. The
casing was already fully liquid in the aluminium models or above the CF
property range at handoff. These tests verify the last few coupled steps. The
elapsed time before handoff belongs to the independent model.

\begin{center}\small\begin{tabular}{lrrrrr}\toprule
& Handoff & Liner at handoff & Native & Native interval & Max. edge\\
Motor & [s] & [$\mu$m] & solves & to loss [s] & ratio$^\dagger$\\\midrule
ROWS
\bottomrule\end{tabular}\end{center}
\noindent $^\dagger$Largest brick edge divided by its shortest edge, screened
over the independent full history using the revised geometry.
All four native terminal checks finished without a solver warning or error.
Across their archived fields the largest nodal difference from the matched
radial system was ENDERR~K.

\paragraph{Why change the final step?} With the original sector the final
brick edge ratios ranged from 176 to 4065 as the wall became extremely thin.
The revised sector spans $0.03^\circ$. It has two cells circumferentially and
two axially, with axial pitch equal to the circumferential arc at the
liner--casing interface. The radial mesh starts with 80 cells through the
liner and 20 through the case. With one liner cell left, the controller
estimates the time to consume the remaining material at the current rate. It
shortens the penultimate step when needed so that the final increment retains
enough physical thickness to mesh. The following solve recomputes the mass
flux, available char and event time. In each independent exposure this
adjustment occurred once, with a maximum shift of 0.00027~s in exhaustion.
\medskip
\lstinputlisting[language=Python]{../../model/sector_terminal_step.py}
\clearpage
'''
    for key,value in [('STARTERR',max(startup)),('ENDERR',max_error)]:
        mantissa,exponent=f'{value:.1e}'.split('e')
        text=text.replace(key,rf'${mantissa}\times 10^{{{int(exponent)}}}$')
    return text.replace('ROWS','\n'.join(rows))


def build(inputs):
    def register(path):
        sha = digest(path)
        inputs[str(path.relative_to(ROOT))] = sha
        return sha

    def read(path):
        register(path)
        return json.loads(path.read_text())

    receipt = read(ROOT/'validation/native_annular_mode64_smp10.json')
    assert receipt['passed']
    package = ROOT/'configs/native_verification/annular_mode64_smp10'
    expected = read(package/'expected.json')
    assert digest(package/'expected.json') == receipt['expected_sha256']
    field = ROOT/'validation/native_annular_field.txt.gz'
    register(field)
    assert hashlib.sha256(gzip.decompress(field.read_bytes())).hexdigest() == receipt['exports']['mode_end.txt']
    assert register(ROOT/'model/audit_native_conduction_mode.py') == receipt['reader_sha256']
    data = np.loadtxt(field)
    assert np.array_equal(data[:,0], np.arange(1, receipt['nodes']+1))
    reference = np.array([expected['expected_final_C'][str(int(n))] for n in data[:,0]])
    error = data[:,1]-reference
    assert np.isclose(max(abs(error)), receipt['max_nodal_error_K'])
    g = expected['geometry']
    ring = (g['angular_divisions']+1)*(g['axial_divisions']+1)
    radius = np.linspace(1000*g['inner_radius_m'],1000*g['outer_radius_m'],len(reference)//ring)
    fig, axes = plt.subplots(1,2,figsize=(7,2.15),layout='constrained')
    axes[0].plot(radius,reference[::ring],color='#194b78',label='Exact solution')
    axes[0].plot(radius[::4],data[::4*ring,1],'o',ms=3,mfc='white',color='#a35635',label='MAPDL')
    axes[0].set_ylabel('Terminal temperature [°C]')
    axes[0].legend(fontsize=8)
    axes[1].plot(radius,error.reshape(-1,ring),color='#194b78',lw=.9)
    axes[1].set_ylabel('MAPDL minus exact [K]')
    for ax in axes: ax.set_xlabel('Radius [mm]')
    graph = ROOT/'docs/analysis/native_annular_comparison.png'
    fig.savefig(graph,dpi=190)
    plt.close(fig)
    register(graph)

    pure = []
    for n in (8,16):
        p = ROOT/f'validation/native_moving_char_r4_mvchar{n}.json'
        if p.exists():
            result = read(p)
            assert result['passed']
            assert register(ROOT/'model/audit_native_moving_char.py') == result['reader_sha256']
            assert register(ROOT/f'configs/native_verification/moving_char_log_smp10_r4/mvchar{n}.json') == result['expected_sha256']
            pure.append(f"{n} & {result['steps']} & {result['event_s']:.4f} & {result['analytic_s']:.4f} & {100*result['event_relative_error']:.3f}"+r' \\')
    checks = r'''\begin{center}\begin{tabular}{rrrrr}\toprule
Radial cells & Steps & MAPDL [s] & Exact [s] & Error [\%]\\\midrule
'''+ '\n'.join(pure)+r'''
\bottomrule\end{tabular}\end{center}''' if pure else ''
    snapshot_errors = []
    for case in ('sustainer_al','sustainer_cf','booster_al','booster_cf'):
        snapshot = read(ROOT/f'validation/native_snapshot_r2_{case}.json')
        assert snapshot['passed'] and snapshot['case']==case and snapshot['fields']==10
        snapshot_errors.append(snapshot['max_nodal_error_K'])
    end = read(ROOT/'validation/native_cf_terminal_window_tails20x10.json')
    config = ROOT/'configs/native_verification/cf_tail_char_smp10_r3/tails20x10.json'
    window = read(config)
    assert end['passed'] and digest(config) == end['comparison_sha256']
    pulse = read(ROOT/'validation/native_cf320_handoff.json')
    assert pulse['passed']
    text = r'''\section{What the native ANSYS benchmarks verify}\label{sec:nativebench}
Both cylindrical faces are held at 22~$^\circ$C.
For a homogeneous hollow cylinder the first radial diffusion mode has the form
$T(r,t)-22=\phi(r)\exp[-kt\lambda^2/(\rho c_p)]$, where $\phi$ vanishes at
both boundaries. After one decay time the temperature rise is $1/e$ of its
initial value everywhere. MAPDL advanced 256 substeps over 21.135~s on a sector
of 256 bricks with 585 nodes. The largest nodal error was MAXERR~K against a
predeclared limit of 0.25~K. The root-mean-square error was RMSERR~K.
\begin{figure}[H]\centering\includegraphics[width=.95\textwidth]{../analysis/native_annular_comparison.png}
\caption{At left, the native solution and analytical profile after one decay time.
At right, the signed error over all nine axial and angular node lines.}
\end{figure}
\paragraph{Receding char.} A second benchmark uses a 0.6~mm pure-char wall
with a prescribed logarithmic temperature profile and a corresponding heating
law. Integrating the analytical recession speed gives the reference time. A first implementation distorted connected elements while
moving nodes and also produced oscillating temperatures under a lagged
surface heat sink. The revised calculation rebuilds each brick after moving
all nodes and uses the local derivative of net incident flux to couple heating
and char consumption. Narrower transverse dimensions and a shared final time
interval control the aspect ratio as the remaining char becomes thin.
CHECKS
\paragraph{Motor field checks.} For each of the four geometries, MAPDL advanced
a frozen 30~s state through ten increments spanning 0.05~s. Across all four
cases the largest nodal difference from a separate brick assembly was SNAPERR~K.
These comparisons test heat storage and transport with the material state and
loads held fixed over that interval.
\paragraph{First CF liner-loss event.} For the sustainer CF, MAPDL consumed the last
TAILMM~mm of char in TAILSEC~s on 20 radial cells. The starting temperature and
the casing temperature history came from the independent model at and after
STARTSEC~s of continuous exposure. The maximum nodal difference from the matched
calculation was TAILDIFF~K. Native verification from first exposure remains open.

\paragraph{Separate pulse control.} In the final 320-row CF control, heating
ended at 7~s. The casing continued to warm during cooling and first exceeded
150~$^\circ$C between LOW and HIGH~s. At that point REMAIN~mm of the original
4.7625~mm liner remained. All STEPS accepted steps passed the balance checks.
The largest sampled native versus radial temperature difference was DIFF~K.

\clearpage
'''
    for key,value in {'TAILMM':f"{1000*(window['radius_m'][1]-window['radius_m'][0]):.3f}",
                      'TAILSEC':f"{end['remaining_time_s']:.3f}",'STARTSEC':f"{window['start_s']:.2f}",
                      'TAILDIFF':f"{end['max_all_node_error_K']:.4f}",'MAXERR':f"{receipt['max_nodal_error_K']:.3f}","SNAPERR":f"{1e6*max(snapshot_errors):.2f}"+r"$\times10^{-6}$",'RMSERR':f"{receipt['rms_nodal_error_K']:.3f}",'CHECKS':checks,
                      'LOW':f"{pulse['first_crossing_bracket_s'][0]:.4f}",'HIGH':f"{pulse['first_crossing_bracket_s'][1]:.4f}",
                      'STEPS':f"{pulse['steps']:,}",'REMAIN':f"{pulse['remaining_liner_mm']:.3f}",'DIFF':f"{pulse['max_profile_difference_K']:.4f}"}.items():
        text=text.replace(key,value)
    tex=ROOT/'docs/en/continuous_native_verification.tex'
    tex.write_text(text+terminal_windows(register,read)+coupled_endpoints(register,read))
    register(tex)
    register(Path(__file__))
