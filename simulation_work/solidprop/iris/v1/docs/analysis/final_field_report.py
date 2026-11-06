"""Export nominal histories and distinguish native temperatures from radial conversion profiles."""
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from backing_film_campaign import read
from continuous_heating_campaign import digest
from ops import ROOT


def build(cases, inputs, native):
    def track(path):
        signature = digest(path)
        inputs[str(path.relative_to(ROOT))] = signature
        return signature

    ledger = ROOT/'validation/whole_event_interval_refinement.json'
    track(ledger)
    nodal = read(ledger)['cases']
    assert len(native)==len(cases)==4
    data = ROOT/'output/data'
    data.mkdir(exist_ok=True)
    native_csv = data/'nominal_native_history.csv'
    radial_csv = data/'nominal_radial_history.csv'
    temp_fig, temp_axes = plt.subplots(2,2,figsize=(7.15,4.6),layout='constrained',sharex=True,sharey=True)
    alpha_fig, alpha_axes = plt.subplots(2,2,figsize=(7.15,4.15),layout='constrained',sharex=True,sharey=True)
    temperatures, intervals, differences = [], [], []
    colors = ['#1b4965','#a5522e','#517647','#816199']
    with native_csv.open('w',newline='') as nf, radial_csv.open('w',newline='') as rf:
        nw = csv.writer(nf,lineterminator='\n')
        rw = csv.writer(rf,lineterminator='\n')
        thermal = ['case','time_s','remaining_phenolic_mm','exposed_phenolic_C','liner_casing_interface_C','outer_casing_C']
        nw.writerow(thermal)
        rw.writerow(thermal+['virgin_kg_per_rad_m','char_kg_per_rad_m','cumulative_bulk_gas_kg_per_rad_m',
                              'cumulative_face_gas_kg_per_rad_m','cumulative_char_products_kg_per_rad_m',
                              'cumulative_film_heat_J_per_rad_m','cumulative_radiation_heat_J_per_rad_m'])
        for index,(case,label,_) in enumerate(cases):
            r = native[case]
            field = r['history']
            assert field[-1]['remaining_mm']==0 and r['native_end_s']==field[-1]['time_s']
            assert all(row['remaining_mm']>0 for row in field[:-1])
            cf = case.endswith('_cf')
            tag = case+('_reacting_fine' if cf else '_phase_n640_ms20_mK500')
            material = 'cf' if cf else 'aluminium'
            path = ROOT/f'validation/{material}_backing_cases/{tag}.json'
            assert track(path)==r['fv_sha256']
            fv = read(path)
            assert fv['history'][-1]['remaining_mm']==0 and r['independent_end_s']==fv['event_bracket_s'][1]
            for row in field:
                nw.writerow([case,row['time_s'],row['remaining_mm'],row['hot_C'] if row['remaining_mm']>0 else '',
                             row['interface_C'],row['outer_C']])
            for row in fv['history']:
                budget = row['ledger']
                rw.writerow([case,row['time_s'],row['remaining_mm'],row['face_C'] if row['remaining_mm']>0 else '',
                             row['interface_C'],row['outer_C'],row['virgin_kg_per_rad_m'],row['char_kg_per_rad_m'],
                             *[budget[k] for k in ('bulk_gas','face_gas','char_products','film_heat','radiation_heat')]])
            onset = r['native_events']['baseline_property_limit'][1]
            limit = r['casing_event_bracket_s'][1]
            t = np.array([0.]+[row['time_s'] for row in field])
            ax = temp_axes.flat[index]
            ax.axvspan(limit,t[-1],color='.91',zorder=0)
            ax.axvline(onset,color='.5',lw=.8,ls=':')
            for key,desc,color,style in [('hot_C','Exposed phenolic',colors[1],'-'),
                                        ('interface_C','Interface',colors[0],'-'),('outer_C','Outside',colors[2],'--')]:
                include = field[:-1] if key=='hot_C' else field
                values = [22.]+[row[key] for row in include]
                ax.plot(t[:len(values)],values,color=color,ls=style,lw=1.3,label=desc)
            ax.set(title=label,xlim=(0,150),ylim=(-25,1150))
            peaks = [max(field,key=lambda row:row[k]) for k in ('interface_C','outer_C')]
            temperatures.append(f"{label} & {onset:.2f} & {limit:.2f} & {peaks[0]['interface_C']:.0f} & "
                                f"{peaks[1]['outer_C']:.0f} & {t[-1]:.2f}"+r' \\')
            assert all(p['time_s']==t[-1] for p in peaks)
            ax = alpha_axes.flat[index]
            settings_path = ROOT/f"configs/native_verification/whole_sector_r2/{r['job']}_settings.json"
            settings = read(settings_path)
            track(settings_path)
            props = settings['configuration']['material']
            y = props['char_reference_density_kg_m3']/props['virgin_reference_density_kg_m3']
            original = settings['configuration']['geometry']['inner_radius_m']
            for sample_time, color in zip([1,7,30,60],colors):
                profile, = [p for p in fv['profiles'] if abs(p['time_s']-sample_time)<1e-7]
                edge = np.array(profile['liner_edges_m'])
                v = np.array(profile['liner_virgin_kg_per_rad_m'])
                c = np.array(profile['liner_char_kg_per_rad_m'])
                assert np.all(c+y*v>0) and np.all(c>=0) and np.all(v>=0)
                alpha = c/(c+y*v)
                width = np.diff(edge)
                centres = edge[:-1]+width*(edge[:-1]+2*edge[1:])/(3*(edge[:-1]+edge[1:]))
                ax.plot(1000*(centres-original),alpha,color=color,lw=1.4,label=f'{sample_time} s')
                ax.plot(1000*(centres[0]-original),alpha[0],'o',ms=3,color=color)
            ax.set(title=label,ylim=(-.035,1.1))
            fe = nodal[r['job']]['runs'][0]
            assert (fe['n'],fe['nc'],fe['dt_s'])==(settings['n'],settings['nc'],settings['dt_s'])
            a,b = r['native_event_bracket_s'], fe['event_bracket_s']
            assert min(a[1],b[1])>max(a[0],b[0])
            differences.append(max(abs(x-y) for x,y in zip(a,b)))
            intervals.append(f"{label} & {a[0]:.4f}--{a[1]:.4f} & {r['independent_event_bracket_s'][0]:.4f}--"
                             f"{r['independent_event_bracket_s'][1]:.4f} & {1000*r['event_interval_gap_s']:.1f}"+r' \\')
    for fig,axes,x,y,filename in [(temp_fig,temp_axes,'Time from first gas exposure [s]','Temperature [°C]','whole_wall_temperatures.png'),
                                   (alpha_fig,alpha_axes,'Depth from original gas-facing surface [mm]','Fraction converted','whole_liner_conversion.png')]:
        location = 'lower right' if fig is temp_fig else 'center right'
        axes[0,0].legend(fontsize=8, frameon=False, loc=location)
        fig.supxlabel(x,fontsize=10);fig.supylabel(y,fontsize=10)
        path = ROOT/'docs/analysis'/filename
        fig.savefig(path,dpi=185);plt.close(fig);track(path)
    thermal_page = r'''\section{Gas, liner and casing temperatures through exhaustion}\label{sec:temperatures}
The gas boundary stays at 2504~K (2231~$^\circ$C). The exposed solid heats to
about 1076--1077~$^\circ$C at its highest saved hot-face sample. Convection
supplies heat across the difference between gas and wall temperatures,
while conduction, decomposition, gas release and char consumption carry
energy away from the surface. The casing heats later as the liner thins.
\begin{figure}[H]\centering\includegraphics[width=.98\textwidth]{../analysis/whole_wall_temperatures.png}
\caption{Native ANSYS temperatures from first exposure. The dotted vertical line
marks the baseline casing-property flag (300~$^\circ$C Al, 150~$^\circ$C CF).
Shading begins when all Al is liquid or CF reaches 1000~$^\circ$C. The last
exposed-phenolic sample precedes exhaustion.}
\end{figure}
\begin{center}\small\begin{tabular}{lrrrrr}\toprule
& Baseline & Liquid Al or & Peak interface & Peak outside & Time of both\\
Motor & flag [s] & CF ceiling [s] & [$^\circ$C] & [$^\circ$C] & peaks [s]\\\midrule
TEMPS
\bottomrule\end{tabular}\end{center}
Both maxima use saved samples through liner exhaustion. The model ends there.
The CF casing sustains a larger inside-to-outside temperature difference than
the conductive Al surrogate. The assumed through-thickness CF properties and
retained backing geometry govern that result.
\clearpage
'''
    profile_page = r'''\section{Where pyrolysis occurs in the surviving liner}
The independent finite-volume model tracks virgin mass $m_v$ and char mass
$m_c$ in each surviving cell. With char yield $Y_c=600/1250=0.48$ the
converted fraction is $\alpha=m_c/(m_c+Y_c m_v)$. Thus a fully converted cell
can retain solid char. Geometric burnthrough requires that char to leave as well.
\begin{figure}[H]\centering\includegraphics[width=.98\textwidth]{../analysis/whole_liner_conversion.png}
\caption{Nominal 640-cell liner profiles with evolving casings. Symbols locate
the first surviving cell centre. The interval to its left grows as material
leaves the wall. Depth is measured from the original inner wall.}
\end{figure}
\paragraph{Independent check of the native calculation.}
On the same 80/20-cell mesh and 40~ms maximum step the independent nodal
reduction reproduced each end of the native final interval within BOUND~s.
The nodal and native intervals overlap in all four cases. A separately
discretized finite-volume wall gives the following results.
\begin{center}\small\begin{tabular}{lrrr}\toprule
Motor & Native last step [s] & Reference FV last step [s] & Gap [ms]\\\midrule
INTERVALS
\bottomrule\end{tabular}\end{center}
These raw integration intervals identify the last positive thickness and
the first zero thickness in each computation. The separation quantifies the
remaining difference between methods. The refinement comparisons on
pages~\pageref{sec:intervals}--\pageref{sec:matched} support the rounded
exposure times on the first page.
\clearpage
'''
    exponent = int(np.ceil(np.log10(max(differences))))
    text = thermal_page.replace('TEMPS','\n'.join(temperatures))+profile_page.replace('INTERVALS','\n'.join(intervals)).replace('BOUND',rf'$10^{{{exponent}}}$')
    target = ROOT/'docs/en/continuous_full_fields.tex'
    target.write_text(text)
    for path in (target,native_csv,radial_csv,Path(__file__).resolve()):
        track(path)
