from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_study import folder, run

OUT=Path(__file__).resolve().parent
FT=1/.3048
r=json.loads((OUT/'result.json').read_text())
summary=pd.read_csv(OUT/'sweep_summary.csv').sort_values('delay_s')
low=r['latest_tested_passing_delay_after_apogee_s'];high=r['first_failing_delay_after_apogee_s']
base=pd.read_csv(folder(1)/'paired_comparison.csv')
final=pd.read_csv(folder(low)/'paired_comparison.csv')
failed=pd.read_csv(folder(high)/'paired_comparison.csv')
limiting=int((final.impact_descent_ratio-1).abs().idxmax())
assert final.passes.all() and not failed.passes.all()
prior=OUT.parent/'urrg_balius_j800_20261018_native_ensemble_30_10mph/canards/results/individual_metrics.csv'
prior=pd.read_csv(prior)
assert np.array_equal(base[['mass_multiplier','cd_multiplier']].values,prior[['mass_multiplier','cd_multiplier']].values)
assert np.allclose(base.apogee_m,prior.apogee_m,atol=1e-7,rtol=0)
assert np.allclose(final.deployment_s-final.apogee_event_s,low,atol=.01,rtol=0)
assert np.allclose(final.impact_descent_ratio,final.impact_descent_mps/base.impact_descent_mps)

# Independently verify event-interpolated ground velocities from exported trajectories.
errors=[]
for delay,metrics in [(1.,base),(low,final),(high,failed)]:
    for row in metrics.itertuples():
        tr=pd.read_csv(folder(delay)/'traces'/f'run_{row.run:04d}.csv.gz')
        # Match OpenRocket's interpolation at the recorded ground-hit event.
        unique=tr.drop_duplicates('time_s',keep='first')
        v=-np.interp(row.ground_hit_s,unique.time_s,unique.velocity_z_mps)
        errors.append(abs(v-row.impact_descent_mps))
assert max(errors)<1e-7,max(errors)

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'text.color':'#173247','axes.labelcolor':'#173247'})
fig=plt.figure(figsize=(14,11),facecolor='#f7f9fb')
gs=fig.add_gridspec(2,2,left=.08,right=.97,bottom=.17,top=.84,hspace=.42,wspace=.24,height_ratios=[1,1])
whole=fig.add_subplot(gs[0,0]);zoom=fig.add_subplot(gs[0,1]);height=fig.add_subplot(gs[1,:])
fig.suptitle('Balius Canards · J800T · Main-parachute deployment delay',fontsize=21,fontweight='bold',y=.97)
fig.text(.5,.925,'30 paired flights per delay · 10 mph mean wind · normal mass σ = 5% · normal Cd σ = 2%',ha='center',fontsize=12)
fig.text(.5,.891,'Criterion: each flight’s vertical impact speed stays within 5% of its own apogee + 1 s baseline',ha='center',fontsize=11)

means=[];mins=[];maxs=[];curves=[]
for d in summary.delay_s:
    data=pd.read_csv(folder(d)/'paired_comparison.csv')
    means.append(data.impact_descent_mps.mean()*FT)
    mins.append(data.impact_descent_mps.min()*FT);maxs.append(data.impact_descent_mps.max()*FT)
    curves.append(100*np.abs(data.impact_descent_ratio.values-1))
curves=np.array(curves)
whole.fill_between(summary.delay_s,mins,maxs,color='#087d93',alpha=.16,label='Range across 30 flights')
whole.plot(summary.delay_s,means,'o-',color='#087d93',ms=3,label='Mean impact descent speed')
whole.axhline(base.impact_descent_mps.mean()*FT,color='#627c8c',ls='--',label='Apogee + 1 s baseline')
whole.axvline(low,color='#d67122',ls=':')
whole.set(title='Impact speed over the delay sweep',xlabel='Delay after apogee (s)',ylabel='Vertical impact speed (ft/s)')
whole.legend(fontsize=9,loc='upper left',frameon=False)

for i in range(30):zoom.plot(summary.delay_s,curves[:,i],color='#8196a4',alpha=.32,lw=.9)
zoom.plot(summary.delay_s,curves.max(1),'o-',color='#bd4b29',ms=4,label='Largest difference among 30 flights')
zoom.axhline(5,color='#173247',ls='--',label='5% limit')
zoom.axvline(low,color='#087d93',ls=':')
zoom.scatter([low,high],[(final.impact_descent_ratio-1).abs().max()*100,(failed.impact_descent_ratio-1).abs().max()*100],
             s=50,c=['#087d93','#bd4b29'],zorder=5)
zoom.set(xlim=(max(1,low-1.5),high+.4),ylim=(-1,15),xlabel='Delay after apogee (s)',ylabel='Absolute difference from baseline (%)',
         title=f'Latest tested pass: {low:.3f} s; fails at {high:.3f} s')
zoom.legend(fontsize=9,loc='upper left',frameon=False)

heights=final.deployment_altitude_m.to_numpy()*FT
colors=['#087d93']*30;colors[limiting]='#bd4b29'
height.bar(final.run,heights,color=colors,alpha=.85,width=.72)
height.axhline(heights.mean(),color='#173247',ls='--',label=f'Mean {heights.mean():.0f} ft AGL')
height.set(xlabel='Ensemble flight',ylabel='Deployment altitude (ft AGL)',xticks=list(range(1,31)),
           title=f'Altitude at apogee + {low:.3f} s · mean {heights.mean():.0f} ± {heights.std(ddof=1):.0f} ft · range {heights.min():.0f}–{heights.max():.0f} ft')
height.text(.99,.92,'Orange: flight closest to the 5% limit',ha='right',transform=height.transAxes,fontsize=10,color='#bd4b29')
height.legend(loc='upper left',fontsize=10,frameon=False)
for ax in [whole,zoom,height]:
    ax.grid(alpha=.17);ax.set_axisbelow(True);ax.set_facecolor('white')
fig.text(.5,.105,f'All 30 pass at apogee + {low:.3f} s (about {r["deployment_time_after_launch_mean_s"]:.1f} s after launch).',ha='center',fontsize=13,fontweight='bold')
fig.text(.5,.071,'AGL uses the flat ground plane at the URRG launch pad. ± values are sample standard deviations.',ha='center',fontsize=10)
fig.text(.5,.043,'Model limit: instantaneous full parachute drag; canopy inflation time and opening-load failure are not modeled.',ha='center',fontsize=10,color='#536a7a')
fig.savefig(OUT/'deployment_delay_study_imperial.png',dpi=190)
fig.savefig(OUT/'deployment_delay_study_imperial.pdf')
plt.close(fig)
validation={'passed':True,'paired_draws_match_prior_30':True,'apogee_unchanged':True,
            'impact_speed_trace_validation_max_error_mps':max(errors),'limiting_flight':limiting+1,
            'limiting_flight_deployment_altitude_ft':float(heights[limiting]),
            'deployment_altitude_mean_ft':float(heights.mean()),'deployment_altitude_sd_ft':float(heights.std(ddof=1)),
            'deployment_altitude_min_ft':float(heights.min()),'deployment_altitude_max_ft':float(heights.max()),
            'baseline_vertical_impact_mean_fps':float(base.impact_descent_mps.mean()*FT),
            'latest_vertical_impact_mean_fps':float(final.impact_descent_mps.mean()*FT),
            'latest_vertical_impact_sd_fps':float(final.impact_descent_mps.std()*FT),
            'latest_mean_total_impact_fps':float(final.impact_total_mps.mean()*FT),
            'maximum_speed_increase_pct':float((final.impact_descent_ratio.max()-1)*100),
            'first_failing_pass_count':int(failed.passes.sum()),
            'deployment_speed_range_fps':[float(final.deployment_total_mps.min()*FT),float(final.deployment_total_mps.max()*FT)]}
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps(validation,indent=2))
