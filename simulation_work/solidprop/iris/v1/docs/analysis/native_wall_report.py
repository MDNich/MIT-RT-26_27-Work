"""Render only accepted native verification results from archived field exports."""
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from continuous_heating_campaign import digest
from ops import ROOT


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
    pulse = read(ROOT/'validation/native_cf320_handoff.json')
    assert pulse['passed']
    text = r'''\section{What the native ANSYS benchmarks verify}\label{sec:nativebench}
The conduction check begins with a known radial temperature profile above a
22~$^\circ$C baseline. The inner and outer faces are held at 22~$^\circ$C.
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
law. The code computes the face temperature, char mass flux and remaining
radius. Integration of the analytical recession speed gives an independent
reference time. A first implementation distorted connected elements while
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
\paragraph{Separate pulse control.} In the final 320-row CF control, heating
ended at 7~s. The casing continued to warm during cooling and first exceeded
150~$^\circ$C between LOW and HIGH~s. At that point REMAIN~mm of the original
4.7625~mm liner remained. All STEPS accepted steps passed the balance checks.
The largest sampled native versus radial temperature difference was DIFF~K.
The benchmarks on this page test conduction, moving geometry or pulse cooling.
The ignition-to-exhaustion times in the opening table still come from the two
independent radial simulations.
\clearpage
'''
    for key,value in {'MAXERR':f"{receipt['max_nodal_error_K']:.3f}","SNAPERR":f"{1e6*max(snapshot_errors):.2f}"+r"$\times10^{-6}$",'RMSERR':f"{receipt['rms_nodal_error_K']:.3f}",'CHECKS':checks,
                      'LOW':f"{pulse['first_crossing_bracket_s'][0]:.4f}",'HIGH':f"{pulse['first_crossing_bracket_s'][1]:.4f}",
                      'STEPS':f"{pulse['steps']:,}",'REMAIN':f"{pulse['remaining_liner_mm']:.3f}",'DIFF':f"{pulse['max_profile_difference_K']:.4f}"}.items():
        text=text.replace(key,value)
    tex=ROOT/'docs/en/continuous_native_verification.tex'
    tex.write_text(text)
    register(tex)
    register(Path(__file__))
