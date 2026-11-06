"""Render audited coupled numerical results, sensitivities, fields and ledgers."""
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(names,inputs):
    def read(file,sha=None):
        path=ROOT/file; actual=digest(path)
        if sha is not None: assert actual==sha
        inputs[file]=actual
        return json.loads(path.read_text())
    nominal=read('validation/moving_surface_campaign_audit.json')
    screen=read('validation/moving_surface_sensitivity_audit.json')
    endpoint=read('validation/moving_surface_endpoint_audit.json')
    for key,path in [(nominal,'configs/moving_surface_campaign.json'),(screen,'configs/moving_surface_sensitivities.json'),
                     (endpoint,'configs/moving_surface_sensitivity_endpoints.json')]:
        read(path,key['plan_sha256'])
    tested=read('validation/moving_surface_transient_verification.json')
    restarted=read('validation/moving_surface_checkpoint_verification.json')
    assert tested['passed'] and restarted['terminal_record_byte_equal']
    for key,sha in tested['sources'].items(): assert digest(ROOT/f'model/{key}.py')==sha
    data={}; rows=[]; variations=[]; errors=[]
    for case,name,color in names:
        tag=f'{case}_moving640_time02'
        r=read(f'validation/moving_surface_cases/{tag}.json',nominal['records'][tag]['record_sha256'])
        data[case]=r
        lo,hi=screen['extreme_scenarios'][case]
        assert (lo,hi)==('h2000','h500')
        def refined(scenario):
            return endpoint['records'][f'{case}_moving_sens_{scenario}_640_02']['event_bracket_s'][1]
        rows.append(f"{name} & {r['history'][0]['remaining_mm']:.4f} & {r['event_bracket_s'][1]:.1f} & "
                    f"{r['scope_bracket_s'][1]:.1f} & {refined(lo):.1f}--{refined(hi):.1f} "+r'\\')
        pulls = screen['records'][case]
        pair=lambda a,b: f"{pulls[a]['event_bracket_s'][1]:.0f} / {pulls[b]['event_bracket_s'][1]:.0f}"
        variations.append(' & '.join([name,pair('p600','p1000'),pair('rad10','rad30'),pair('cost17.5','cost70'),
                                      pair('gasdelta90','gasdelta110')])+r' \\')
        space,time = [nominal['comparisons'][case][k] for k in ('320_0.04_to_640_0.04','640_0.04_to_640_0.02')]
        errors.append(' & '.join([name,f"{space['event_difference_s']:+.4f}",f"{time['event_difference_s']:+.4f}",
                      f"{max(p['remaining_mm']['difference'] for p in (space,time)):.5f}",
                      f"{space['hot_face_including_initial_K']['difference']:.1f}",
                      f"{space['hot_face_from_half_second_K']['difference']:.1f}"])+r' \\')
    # Nominal histories, with range crossing drawn on each curve.
    fig,ax=plt.subplots(2,1,figsize=(7.2,5.55),layout='constrained',sharex=True)
    for case,name,color in names:
        r=data[case]; history=r['history']; t=np.array([v['time_s'] for v in history])
        cut=np.searchsorted(t,r['scope_bracket_s'][1])
        for axis,key in zip(ax,('remaining_mm','interface_C')):
            y=np.array([v[key] for v in history])
            axis.plot(t[:cut+1],y[:cut+1],color=color,label=name,lw=1.5)
            axis.plot(t[cut:],y[cut:],color=color,ls=':',lw=1.6)
            axis.plot(t[cut],y[cut],'o',ms=4,color=color)
    ax[0].set(ylabel='Remaining liner [mm]',ylim=(0,6.65));ax[0].legend(ncol=2,fontsize=9)
    ax[1].set(ylabel='Liner–casing interface [°C]',xlabel='Sustained exposure [s]',xlim=(0,None))
    fig.savefig(ROOT/'docs/analysis/moving_nominal.png',dpi=190);plt.close(fig)
    # Distinguish both inner temperatures; overlay conserved species and powers.
    fig,axes=plt.subplots(2,2,figsize=(7.35,5.85),layout='constrained')
    a,b,c,d=axes.flat
    sa=data['sustainer_al']; h=sa['history']; t=np.array([x['time_s'] for x in h]); cut=np.searchsorted(t,sa['scope_bracket_s'][1])
    for key,name,color in [('face_C','Hot phenolic','#ac5b2d'),('interface_C','Casing interface','#275e78'),('outer_C','Outer casing','#487950')]:
        y=np.array([r[key] for r in h]);a.plot(t[:cut+1],y[:cut+1],label=name,color=color,lw=1.2)
        a.plot(t[cut:],y[cut:],ls=':',color=color,lw=1.4)
    a.set(ylabel='Temperature [°C]',xlabel='Exposure [s]');a.legend(fontsize=7)
    r0=sa['profiles'][0]['liner_edges_m'][0]
    for p in sa['profiles']:
        time=p['time_s']
        if not any(abs(time-z)<1e-8 for z in (1.,7.,30.,60.,90.)): continue
        rr=np.array(p['liner_edges_m']); centres=rr[:-1]+np.diff(rr)*(rr[:-1]+2*rr[1:])/(3*(rr[:-1]+rr[1:]))
        b.plot(1000.*(centres-r0),p['liner_temperature_C'],label=f'{time:.0f} s',
               ls=':' if time>sa['scope_bracket_s'][1] else '-',lw=1.35)
    b.set(ylabel='Liner cell temperature [°C]',xlabel='Depth from original hot face [mm]');b.legend(fontsize=7,ncol=2)
    ledger=h[-1]['ledger']
    initial=h[0]['solid_mass_kg_per_rad_m']
    component=lambda key: np.array([v['ledger'][key] for v in h])
    c.stackplot(t,np.array([v['virgin_kg_per_rad_m'] for v in h])/initial,
                 np.array([v['char_kg_per_rad_m'] for v in h])/initial,
                 (component('bulk_gas')+component('face_gas'))/initial,component('char_products')/initial,
                 labels=['Virgin','Retained char','Pyrolysis gas','Char products'],
                 colors=['#9fbda6','#685d59','#a3c4d7','#d8b184'])
    c.set(xlabel='Exposure [s]',ylabel='Fraction of original liner mass',ylim=(0,1.04));c.legend(fontsize=6.7,ncol=2,loc='center')
    for name,values,color in [('Film input',component('film_heat'),'#2b5e80'),('Face reactions',component('face_reaction'),'#a6552c'),
                              ('Solid storage',np.array([v['solid_sensible_J_per_rad_m'] for v in h]),'#388160'),
                              ('Other sinks',sum(component(k) for k in ['bulk_reaction','bulk_gas_heat','face_products_heat','outer_loss']),'#776293')]:
        d.plot(t,values/1e6,label=name,color=color,lw=1.4)
    for axis in (c,d): axis.axvline(sa['scope_bracket_s'][1],color='#333333',ls='--',lw=.85)
    d.set(xlabel='Exposure [s]',ylabel='Cumulative MJ per radian per m');d.legend(fontsize=7)
    fig.savefig(ROOT/'docs/analysis/moving_fields.png',dpi=190);plt.close(fig)
    native=read('validation/native_pulse_comparison_sustainer_al_pulse7_midpoint_joint320_geom005_smp10.json')
    assert native['comparison_passed'] and native['native_control_checks_passed']
    at7=next(x for x in native['comparisons'] if x['time_s']==7.)
    j=at7['native_rows_removed_during_solve']
    new7=next(x for x in h if abs(x['time_s']-7.)<1e-9)
    ep=[p for g in endpoint['comparisons'].values() for p in g.values()]
    assert all(p['event_under_5_percent'] and p['thickness_pass'] for p in ep)
    text=r'''\section{Continuous exposure until the casing is uncovered}
The moving-wall calculation gives about 104--107 s for the sustainer and
138--142 s for the booster under the nominal continuous load. It advances the
gas-facing radius until it reaches the casing. Char can remain after the
virgin resin has decomposed, so conversion and casing exposure occur at
different times. This is an independent finite-volume calculation. ANSYS
verification of this coupled moving wall remains open.
\begin{table}[H]\centering
\begin{tabular}{lrrrr}\toprule
Case & Initial liner & Nominal event & Property flag & Film scenarios\\
 & [mm] & [s] & [s] & [s]\\\midrule
EVENTS
\bottomrule\end{tabular}
\caption{Nominal and film endpoints use 640 liner and 160 casing cells with
a 0.02 s step ceiling. Film scenarios change the uncorrected coefficient from
2000 to 500 W/(m$^2$ K), respectively. The other inputs retain nominal values.
The property flag in this table belongs to the nominal case.}
\end{table}
All events occur after the assumed intact casing exceeds its provisional
property range. The nominal gas temperature is 2504 K, nominal chamber pressure
is 800 psi, and the nominal uncorrected film coefficient is 1000 W/(m$^2$ K).
The calculation exposes the liner at ignition and sustains heating until full
local loss. Zero hot-side radiation is assumed at nominal conditions. The
outside sees a 22~$^\circ$C environment, an 8 W/(m$^2$ K) film and emissivity 0.25.
The extent of actual in-motor exposure is unknown.

The largest one-factor changes in this study come from wall heat transfer and
the assumed energy cost of char removal. The times in the last column compare
two specified heat-transfer scenarios. They do not quantify firing-to-firing
variability or a safe firing interval. Firing heat flux versus time and
recession measurements on the manufactured liner would directly constrain
the two inputs driving this spread. Section~\ref{sec:almelt} shows how accounting
for aluminium melting changes the liner times and when the backing melts.

\clearpage\section{Remaining thickness and casing heat-up}
\begin{figure}[H]\centering
\includegraphics[width=.96\textwidth]{../analysis/moving_nominal.png}
\caption{Moving-wall calculation at the finest nominal setting. Dots mark the
first 150~$^\circ$C CF or 300~$^\circ$C Al property flag. Dotted lines continue
with the inherited backing properties. The horizontal axis measures continuous
exposure of the local wall.}
\end{figure}
The two casings give similar early surface recession because the heat initially
penetrates only partway through the liner. The model separates them more
clearly later as the casing absorbs heat. Each property flag denotes the
limit adopted for using those casing data. It does not identify loss of
pressure containment.

\clearpage\section{Temperatures, mass and energy in the sustainer Al calculation}
\begin{figure}[H]\centering
\includegraphics[width=\textwidth]{../analysis/moving_fields.png}
\caption{Upper panels show the three wall temperatures and the spatial
temperature profiles of the surviving liner. Profiles start at the first cell
centre. Lower panels account for the original liner mass and cumulative
energy. Dashed vertical lines mark the casing property flag; subsequent values
use surrogate continuation.}
\end{figure}
At 7 s the coupled wall gives NEWTEMP~$^\circ$C at the hot phenolic face and
NEWLOSS mm removed. At the same exposure time the accepted earlier native
320-row sustainer Al calculation gives OLDTEMP~$^\circ$C at its live face and
OLDLOSS mm of removed mesh. The gas is 2230.85~$^\circ$C in both cases.
The native calculation uses finite-row removal and its inherited reaction and
energy equations. This difference therefore includes changes to the model
as well as discretization; matching one final event time could conceal a
substantial difference in surface behaviour.

At nominal exhaustion the surface reaction terms account for FRACTION percent
of integrated film input in this case. The provisional 35 MJ/kg char cost
therefore warrants a direct sensitivity check. Swept sensible heat appears on
both sides of the interface accounting and cancels from the whole-wall ledger.

\clearpage\section{Numerical checks and open questions}
Twenty nominal calculations isolate the time step at 160 cells, double the
liner and casing radial counts twice at the same step, then halve the step on
the 640/160 mesh. The last two comparisons below use 320 to 640 liner cells at
0.04 s and 0.04 to 0.02 s at 640 cells.
\begin{table}[H]\centering\begin{tabular}{lrr r rr}\toprule
 & \multicolumn{2}{c}{Event shift [s]} & Thickness & \multicolumn{2}{c}{Mesh $\Delta T_s$ [K]}\\
\cmidrule(lr){2-3}\cmidrule(lr){5-6}
Case & Mesh & Time & diff. [mm] & All samples & From 0.5 s\\\midrule
ERRORS
\bottomrule\end{tabular}
\caption{Thickness difference is the largest across both comparisons at shared
times. The temperature columns give the greatest hot-face difference between
the two spatial resolutions, including or excluding the initial transient.}
\end{table}
All eight finest pairs meet the 5 percent event-time target and the
remaining-thickness target. Their final accepted time intervals overlap.
Three coarser pairs have disjoint intervals. A load applied instantaneously
to a massless reconstructed face gives a mesh-sensitive initial temperature.
The 640-cell result still requires a separate comparison with ANSYS under
matching equations, even where independent refinement differences are small.

The coupled implementation closes each cell energy equation before moving the
front. The accepted step limits conversion growth to 0.05 and surface travel
to 40 percent of the first-cell width while multiple cells remain. A remnant
below half the original pitch merges conservatively with its neighbour.
The last event is localized by solving for the step duration that brings
the radius to the interface. A manufactured isothermal char front reproduces
its analytical time to within $10^{-8}$ s at two resolutions. A nonuniform
reacting coupon, interrupted after mesh mergers and a property flag, gives
a byte-identical final state and history on restart. All twenty nominal
integrations close the cumulative open-system energy and mass ledgers to
relative residuals below ENERGY and MASS, respectively.

\clearpage\section{One-factor sensitivity to assumed inputs}
Forty-two additional calculations each change one named input or one backing
material tuple at 320/80 cells and a 0.04 s step ceiling. The columns show
paired event times in the same order as their listed inputs, in seconds.
\begin{table}[H]\centering\begin{tabular}{lrrrr}\toprule
Case & Pressure & Radiation & Removal cost & Gas excess\\
 & 600 / 1000 psi & 0.1 / 0.3 & 17.5 / 70 MJ/kg & 0.9 / 1.1\\\midrule
VARIATIONS
\bottomrule\end{tabular}\end{table}
Radiation entries specify effective hot-side emissivity at the inherited gas
radiative temperature. Gas excess scales the 2208.85 K difference between
nominal gas and the initial wall, with convection coefficient and all other
parameters fixed. The gas probes measure local sensitivity. Pressure enters
the empirical consumption law; the film coefficient stays independent.

For each case, doubling and halving the film coefficient produce respectively
the earliest and latest event in this screen. Both endpoints were rerun at
640/160 and 0.04 s, then 0.02 s (sixteen checks). The largest individual time
shift is EPDELTA s; EPOVERLAP of sixteen pairs have overlapping final
intervals. All sixteen satisfy the event-change and shared-thickness criteria.
Individual endpoint intervals and the material crossings are recorded with
the cases. An alternative inherited carbon-composite property tuple shifts the
CF event by CFSHIFT s for the sustainer and CFBOOST s for the booster. The
resin, layup, bond and grade used on the actual cases remain unspecified.

Sections~\ref{sec:almelt} and~\ref{sec:cfdiag} examine aluminium fusion and
CF resin decomposition with separate material surrogates.
\clearpage
'''
    fields={'EVENTS':'\n'.join(rows),'VARIATIONS':'\n'.join(variations),'ERRORS':'\n'.join(errors),
            'NEWTEMP':f"{new7['face_C']:.0f}",'NEWLOSS':f"{h[0]['remaining_mm']-new7['remaining_mm']:.3f}",
            'OLDTEMP':f"{at7['native_temperature_C'][j]:.0f}",'OLDLOSS':f"{1000*(at7['radius_m'][j]-r0):.3f}",
            'FRACTION':f"{100*ledger['face_reaction']/ledger['film_heat']:.1f}",
            'EPDELTA':f"{max(abs(p['event_difference_s']) for p in ep):.3f}",
            'EPOVERLAP':str(sum(p['brackets_overlap'] for p in ep)),
            'CFSHIFT':f"{screen['records']['sustainer_cf']['alternate_cf']['departure_from_same_mesh_nominal_s']:+.2f}",
            'CFBOOST':f"{screen['records']['booster_cf']['alternate_cf']['departure_from_same_mesh_nominal_s']:+.2f}"}
    for placeholder,stats in [('ENERGY','max_energy_relative_error'),('MASS','max_mass_relative_error')]:
        peak=max(json.loads((ROOT/f'validation/moving_surface_cases/{tag}.json').read_text())['stats'][stats] for tag in nominal['records'])
        fields[placeholder]=f'$10^{{{int(np.ceil(np.log10(peak)))}}}$'
    for key,value in fields.items(): text=text.replace(key,value)
    path=ROOT/'docs/en/continuous_moving_results.tex';path.write_text(text)
    for p in (path,Path(__file__),ROOT/'docs/analysis/moving_nominal.png',ROOT/'docs/analysis/moving_fields.png'):
        inputs[str(p.resolve().relative_to(ROOT))]=digest(p)
