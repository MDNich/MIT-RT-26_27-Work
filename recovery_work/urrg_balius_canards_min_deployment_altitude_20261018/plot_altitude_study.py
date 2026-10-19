from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'manifest.json').read_text());R=json.loads((OUT/'result.json').read_text())
FT=1/.3048
def folder(h):return OUT/f'altitude_{h:07.2f}ft'
high=R['minimum_tested_passing_trigger_ft'];low=R['highest_tested_failing_trigger_ft']
sweep=pd.read_csv(OUT/'sweep_summary.csv').sort_values('altitude_setting_ft')
good=pd.read_csv(folder(high)/'settling_metrics.csv');bad=pd.read_csv(folder(low)/'settling_metrics.csv')
assert good.passes.all() and not bad.passes.all() and len(good)==30
assert good.final_second_max_abs_error_pct.max()<=5
worst=int(good.final_second_max_abs_error_pct.idxmax())
worstbad=int(bad.final_second_max_abs_error_pct.idxmax())
with zipfile.ZipFile(R['native_ensemble_file']) as z:
    assert z.testzip() is None
    with z.open('rocket.ork') as f:root=ET.parse(f).getroot()
    assert len(root.findall('.//ensemblerun'))==30
    # Verify saved recovery options as well as the JSON summary.
    xml=z.read('rocket.ork').decode('utf-8')
    assert '<deployevent>altitude</deployevent>' in xml.lower()

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'text.color':'#173247','axes.labelcolor':'#173247'})
fig,(ax,detail)=plt.subplots(1,2,figsize=(15,9),facecolor='#f7f9fb',gridspec_kw={'width_ratios':[1,1.12]})
fig.subplots_adjust(left=.075,right=.97,top=.76,bottom=.28,wspace=.24)
fig.suptitle('Balius Canards · J800T · Minimum deployment altitude',fontsize=23,fontweight='bold',y=.96)
fig.text(.5,.905,'30 paired flights per altitude · 10 mph mean wind · normal mass σ = 5% · normal Cd σ = 2%',ha='center',fontsize=12)
fig.text(.5,.861,'Settled = within ±5% of the paired baseline descent speed throughout the final 1 second before impact',ha='center',fontsize=11)

mins=[];maxs=[]
for h in sweep.altitude_setting_ft:
    data=pd.read_csv(folder(h)/'settling_metrics.csv')
    mins.append(data.settled_duration_s.min());maxs.append(data.settled_duration_s.max())
ax.fill_between(sweep.altitude_setting_ft,mins,maxs,color='#087d93',alpha=.16,label='Range across 30 flights')
ax.plot(sweep.altitude_setting_ft,mins,'o-',color='#087d93',ms=4,label='Shortest settled duration')
ax.axhline(1,color='#173247',ls='--',label='Required: 1 second')
ax.axvline(high,color='#d67122',ls=':')
ax.scatter([low,high],[bad.settled_duration_s.min(),good.settled_duration_s.min()],c=['#bd4b29','#087d93'],s=55,zorder=5)
ax.annotate(f'{high:g} ft: 30/30 pass',xy=(high,good.settled_duration_s.min()),xytext=(8,24),
            textcoords='offset points',fontsize=11,fontweight='bold',color='#087d93',arrowprops={'arrowstyle':'-','color':'#087d93'})
ax.set(xlabel='Main deployment trigger (ft AGL)',ylabel='Time continuously within the ±5% band (s)',
       title='How much height is enough?',ylim=(0,max(maxs)*1.15))
ax.legend(loc='upper left',fontsize=9,frameon=False)

grid=np.linspace(-2.5,0,501)
all_curves=[]
for row in good.itertuples():
    tr=pd.read_csv(folder(high)/'traces'/f'run_{row.run:04d}.csv.gz').drop_duplicates('time_s',keep='first')
    ratios=-np.interp(row.ground_hit_s+grid,tr.time_s,tr.velocity_z_mps)/row.baseline_descent_mps
    all_curves.append(ratios)
    detail.plot(grid,100*ratios,color='#087d93',alpha=.25,lw=.8)
detail.plot(grid,100*np.mean(all_curves,axis=0),color='#087d93',lw=2.2,label=f'{high:g} ft: mean of 30 flights')
detail.plot(grid,100*np.array(all_curves)[worst],color='#087d93',lw=1.4,ls='--',label=f'{high:g} ft: most limiting flight')
row=bad.iloc[worstbad]
tr=pd.read_csv(folder(low)/'traces'/f'run_{int(row.run):04d}.csv.gz').drop_duplicates('time_s',keep='first')
ratio=-np.interp(row.ground_hit_s+grid,tr.time_s,tr.velocity_z_mps)/row.baseline_descent_mps
detail.plot(grid,100*ratio,color='#bd4b29',lw=1.7,label=f'{low:g} ft: most limiting flight')
detail.axhspan(95,105,color='#c7d9c1',alpha=.35)
detail.axvspan(-1,0,color='#80ad84',alpha=.12)
detail.axhline(95,color='#536a7a',ls=':',lw=1);detail.axhline(105,color='#536a7a',ls=':',lw=1)
detail.axvline(-1,color='#536a7a',ls=':',lw=1)
detail.set(xlim=(-2.5,0),ylim=(80,120),xlabel='Time relative to impact (s)',ylabel='Vertical descent speed / baseline (%)',
           title='Final descent: all 30 flights at the selected altitude')
detail.legend(loc='upper right',fontsize=9,frameon=True,facecolor='white',framealpha=.92)
detail.text(-.5,82,'Final 1 second',ha='center',fontsize=10,color='#466848')
for a in [ax,detail]:a.grid(alpha=.17);a.set_axisbelow(True);a.set_facecolor('white')
mean=good.impact_descent_mps.mean()*FT;sd=good.impact_descent_mps.std()*FT
fig.text(.5,.187,f'Minimum tested trigger: {high:g} ft ({high*.3048:.1f} m) AGL · 30/30 flights settled',ha='center',fontsize=17,fontweight='bold')
fig.text(.5,.137,f'At {low:g} ft: {int(bad.passes.sum())}/30 pass · Impact descent: {mean:.1f} ± {sd:.1f} ft/s · Altitude resolution: {high-low:g} ft',ha='center',fontsize=12)
fig.text(.5,.084,'AGL is measured above the flat ground plane at the URRG launch pad. ± denotes sample standard deviation.',ha='center',fontsize=10)
fig.text(.5,.050,'Simulation assumes immediate full parachute drag; canopy inflation time and opening-load failure are not modeled.',ha='center',fontsize=10,color='#536a7a')
fig.savefig(OUT/'minimum_deployment_altitude_imperial.png',dpi=190)
fig.savefig(OUT/'minimum_deployment_altitude_imperial.pdf')
plt.close(fig)
v={'passed':True,'saved_native_ork_crc_passed':True,'saved_native_ensemble_runs':30,
   'minimum_trigger_ft':high,'minimum_trigger_m':high*.3048,'lower_test_ft':low,'lower_test_pass_count':int(bad.passes.sum()),
   'limiting_flight':int(good.iloc[worst].run),'maximum_final_second_error_pct':float(good.final_second_max_abs_error_pct.max()),
   'minimum_settled_duration_s':float(good.settled_duration_s.min()),
   'impact_descent_mean_fps':float(mean),'impact_descent_sd_fps':float(sd),
   'deployment_speed_mean_mph':float(good.deployment_total_mps.mean()/.44704),
   'deployment_speed_min_mph':float(good.deployment_total_mps.min()/.44704),
   'deployment_speed_max_mph':float(good.deployment_total_mps.max()/.44704),
   'actual_deployment_altitude_range_ft':[float(good.deployment_altitude_m.min()*FT),float(good.deployment_altitude_m.max()*FT)],
   'deployment_time_after_apogee_range_s':[float((good.deployment_s-good.apogee_event_s).min()),float((good.deployment_s-good.apogee_event_s).max())]}
(OUT/'validation.json').write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps(v,indent=2),flush=True)
