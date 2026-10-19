"""Validate native OR ensemble statistics and render the requested altitude bands."""
from pathlib import Path
import json,argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

OUT=Path(__file__).resolve().parent/'urrg_balius_j800_20261018_native_ensemble'
DESIGNS=[('canards','Canards','#087d93'),('co2','CO₂','#cf7713')]
RUNS=500

def load_and_validate(key):
    folder=OUT/key/'results';summary=json.loads((folder/'summary.json').read_text())
    metrics=pd.read_csv(folder/'individual_metrics.csv')
    band=pd.read_csv(folder/'native_altitude_band.csv')
    assert len(metrics)==RUNS and metrics.notna().all().all()
    assert summary['completed']==RUNS and summary['excluded']==0
    for col,prefix in [('apogee_m','apogee'),('time_to_apogee_s','apogee_time')]:
        unit='m' if prefix=='apogee' else 's'
        assert abs(metrics[col].mean()-summary[f'{prefix}_mean_{unit}'])<1e-9
        assert abs(metrics[col].std(ddof=1)-summary[f'{prefix}_stdev_{unit}'])<1e-9
    assert np.ptp(metrics.launch_mass_kg/metrics.mass_multiplier)<1e-10
    interpolated=[]
    for run in metrics.run:
        tr=pd.read_csv(folder/'traces'/f'run_{run:04}.csv.gz')
        assert np.isfinite(tr).all().all() and np.all(np.diff(tr.time_s)>=0)
        assert band.time_s.iloc[0]>=tr.time_s.iloc[0] and band.time_s.iloc[-1]<=tr.time_s.iloc[-1]
        interpolated.append(np.interp(band.time_s,tr.time_s,tr.altitude_m))
    values=np.array(interpolated)
    errors={'native_mean_vs_independent_max_error_m':float(np.max(np.abs(values.mean(0)-band.mean_altitude_m))),
            'native_sample_sd_vs_independent_max_error_m':float(np.max(np.abs(values.std(0,ddof=1)-band.stdev_altitude_m)))}
    assert max(errors.values())<1e-7,errors
    assert band.time_s.iloc[-1]<=metrics.ground_hit_s.min()
    validation={'passed':True,'completed_runs':len(metrics),'source_mean_and_sd_recomputed_independently':True,
                'whole_vehicle_mass_multiplier_verified':True,**errors,
                'sampled_mass_multiplier_mean':float(metrics.mass_multiplier.mean()),
                'sampled_mass_multiplier_sd':float(metrics.mass_multiplier.std(ddof=1)),
                'sampled_cd_multiplier_mean':float(metrics.cd_multiplier.mean()),
                'sampled_cd_multiplier_sd':float(metrics.cd_multiplier.std(ddof=1)),
                'mass_cd_sample_correlation':float(metrics.mass_multiplier.corr(metrics.cd_multiplier)),
                'native_curve_common_end_s':float(band.time_s.iloc[-1]),
                'earliest_touchdown_s':float(metrics.ground_hit_s.min()),'latest_touchdown_s':float(metrics.ground_hit_s.max())}
    (folder/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    return summary,metrics,band

def main():
    global OUT,RUNS
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=OUT)
    parser.add_argument('--imperial',action='store_true');args=parser.parse_args()
    OUT=args.input
    RUNS=json.loads((OUT/'manifest.json').read_text())['runs_per_design']
    scale=1/.3048 if args.imperial else 1
    unit='ft' if args.imperial else 'm'
    tick_size=200 if args.imperial else 50
    loaded={key:load_and_validate(key) for key,*_ in DESIGNS}
    a,b=(loaded[k][1] for k,*_ in DESIGNS)
    assert np.array_equal(a[['mass_multiplier','cd_multiplier']].to_numpy(),b[['mass_multiplier','cd_multiplier']].to_numpy())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.labelcolor':'#243b4b','text.color':'#173247'})
    fig,(whole,peak)=plt.subplots(1,2,figsize=(15,8.7),gridspec_kw={'width_ratios':[1.1,1]},facecolor='#f7f9fb')
    fig.subplots_adjust(left=.075,right=.975,top=.75,bottom=.26,wspace=.25)
    fig.suptitle('Balius · J800T · Native OpenRocket ensembles',fontsize=23,fontweight='bold',y=.96)
    wind_label='4.47 mph' if args.imperial else '2 m/s'
    fig.text(.5,.905,f'{RUNS} flights per design · normal mass σ = 5% · normal Cd σ = 2% · fixed {wind_label} wind',ha='center',fontsize=12)
    handles=[]
    for key,label,color in DESIGNS:
        summary,metrics,band=loaded[key];t=band.time_s.to_numpy();mean=band.mean_altitude_m.to_numpy()*scale;sd=band.stdev_altitude_m.to_numpy()*scale
        for ax in [whole,peak]:
            ax.fill_between(t,mean-sd,mean+sd,color=color,alpha=.19,linewidth=0)
            ax.plot(t,mean,color=color,lw=2.1)
        x,y=summary['apogee_time_mean_s'],summary['apogee_mean_m']*scale
        sx,sy=summary['apogee_time_stdev_s'],summary['apogee_stdev_m']*scale
        peak.errorbar(x,y,xerr=sx,yerr=sy,fmt='o',color=color,ms=6,capsize=5,elinewidth=1.6,zorder=6)
        handles.append(Line2D([0],[0],c=color,lw=2.2,label=label))
    handles.extend([Patch(facecolor='#627c8c',alpha=.2,label='Shading: altitude mean ±1σ at each time'),
                    Line2D([0],[0],c='#173247',marker='o',lw=1,label='Bars: apogee altitude/time ±1σ')])
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.87),ncol=2,frameon=False,fontsize=10)
    whole.set_title('Altitude versus time',loc='left',fontweight='bold',pad=13)
    peak.set_title('Apogee detail',loc='left',fontweight='bold',pad=13)
    max_t=max(v[2].time_s.max() for v in loaded.values())
    ymax=max(v[0]['apogee_mean_m']+2.5*v[0]['apogee_stdev_m'] for v in loaded.values())*scale
    whole.set(xlim=(0,max_t+3),ylim=(0,tick_size*np.ceil(ymax/tick_size)),ylabel=f'Altitude above launch pad ({unit})')
    peak.set(xlim=(10.5,18),ylim=(700*scale,tick_size*np.ceil(ymax/tick_size)),ylabel=f'Altitude above launch pad ({unit})')
    for ax in [whole,peak]:
        ax.set_xlabel('Time after launch (s)');ax.grid(alpha=.18);ax.set_facecolor('white');ax.set_axisbelow(True)
    for i,(key,label,color) in enumerate(DESIGNS):
        s=loaded[key][0]
        fig.text(.26+.48*i,.137,f'{label}: apogee {s["apogee_mean_m"]*scale:.1f} ± {s["apogee_stdev_m"]*scale:.1f} {unit}\nTime to apogee {s["apogee_time_mean_s"]:.2f} ± {s["apogee_time_stdev_s"]:.2f} s',
                 ha='center',va='center',fontsize=13,fontweight='bold',color=color,linespacing=1.6)
    fig.text(.5,.064,'± values are sample standard deviations (N−1), not confidence intervals for the mean.',ha='center',fontsize=10)
    fig.text(.5,.037,'Native bands end at the first touchdown in each ensemble; later flight data remain in the saved ORKs.',ha='center',fontsize=9,color='#536a7a')
    suffix='_imperial' if args.imperial else ''
    fig.savefig(OUT/f'altitude_ensemble_comparison{suffix}.png',dpi=190)
    fig.savefig(OUT/f'altitude_ensemble_comparison{suffix}.pdf')
    plt.close(fig)
    rows=[]
    for key,label,_ in DESIGNS:
        s=loaded[key][0]
        rows.append({'design':label,'completed':s['completed'],'mean_max_altitude_m':s['apogee_mean_m'],
                     'stdev_max_altitude_m':s['apogee_stdev_m'],'mean_time_to_apogee_s':s['apogee_time_mean_s'],
                     'stdev_time_to_apogee_s':s['apogee_time_stdev_s']})
    pd.DataFrame(rows).to_csv(OUT/'comparison.csv',index=False)
    report={'comparison':rows,'native_band_validation_passed':True,'paired_identical_mass_cd_draws':True,
            'settings':f'{RUNS} runs; normal mass sigma 5%, normal Cd sigma 2%; all other ensemble sigmas zero.',
            'wind':'Source 2 m/s from east, 10% baseline turbulence; identical native wind realization across the ensemble.',
            'altitude_reference':'Height above URRG launch pad; pad 268.603 m elevation.',
            'mass_definition':'Native whole-active-vehicle mass and inertia multiplier, including remaining propellant; CG retained.',
            'cd_definition':'Native overall aerodynamic drag multiplier, also applied to recovery descent drag. Nominal 2.109216 m main and Cd 0.68 unchanged.',
            'uncertainty':'Mean ± sample standard deviation across all completed runs; pointwise altitude bands are native OR outputs, not confidence bands.'}
    (OUT/'comparison_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
