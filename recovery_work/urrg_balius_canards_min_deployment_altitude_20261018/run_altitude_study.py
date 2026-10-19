"""Native altitude-triggered ensembles, with a sustained terminal-descent criterion."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,subprocess,time,math,hashlib,os
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'manifest.json').read_text())
BASE=pd.read_csv(Path(M['baseline_results'])/'individual_metrics.csv')
FT=1/.3048

def folder(height_ft):return OUT/f'altitude_{height_ft:07.2f}ft'

def run(height_ft,save=False):
    dest=folder(height_ft);dest.mkdir(exist_ok=True)
    if (dest/'process.json').exists() and not (dest/'process_result.json').exists():
        info=json.loads((dest/'process.json').read_text())
        while True:
            try:os.kill(info['pid'],0)
            except ProcessLookupError:break
            time.sleep(2)
        if (dest/'summary.json').exists() and 'RESULT ' in (dest/'engine.log').read_text():
            (dest/'process_result.json').write_text(json.dumps({'returncode':0,'adopted_completed_process':True}))
    if not (dest/'process_result.json').exists() or (save and not (dest/'J800T_native_ensemble.ork').exists()):
        cmd=[M['runtime'],'-Xmx4g','-Djava.awt.headless=true','-cp',f'{OUT}/build:{OUT}/engine.jar',
             'BaliusNativeEnsemble',str(OUT/'source.ork'),str(dest),'30','.05','.02','20261018','4',
             '4.4704','1','true',str(height_ft*.3048)]
        start=time.time()
        with (dest/'engine.log').open('w') as log:
            p=subprocess.Popen(cmd,stdout=log,stderr=log)
            (dest/'process.json').write_text(json.dumps({'pid':p.pid,'command':cmd,'start_epoch':start},indent=2))
            print(f'Started {height_ft:g} ft AGL',flush=True)
            code=p.wait()
        (dest/'process_result.json').write_text(json.dumps({'returncode':code,'elapsed_s':time.time()-start},indent=2))
        if code:raise RuntimeError(f'Native ensemble failed at {height_ft} ft: {dest}/engine.log')
        print(f'Completed {height_ft:g} ft AGL',flush=True)
    assert json.loads((dest/'process_result.json').read_text())['returncode']==0
    d=pd.read_csv(dest/'individual_metrics.csv')
    s=json.loads((dest/'summary.json').read_text())
    assert len(d)==30 and s['completed']==30 and s['excluded']==0
    assert s['recovery']['deployment']=='ALTITUDE' and s['recovery']['delay_s']==0
    assert abs(s['recovery']['altitude_setting_m']-height_ft*.3048)<1e-10
    assert np.array_equal(d[['mass_multiplier','cd_multiplier']].values,BASE[['mass_multiplier','cd_multiplier']].values)
    assert np.allclose(d.apogee_m,BASE.apogee_m,atol=1e-7,rtol=0)
    assert (d.deployment_s<d.ground_hit_s).all()
    assert ((d.deployment_altitude_m-height_ft*.3048).abs()<1).all()
    return assess(height_ft,d)

def assess(height_ft,d):
    records=[]
    for row in d.itertuples():
        baseline=float(BASE.loc[BASE.run==row.run,'impact_descent_mps'].iloc[0])
        tr=pd.read_csv(folder(height_ft)/'traces'/f'run_{row.run:04d}.csv.gz').drop_duplicates('time_s',keep='first')
        tt=tr.time_s.to_numpy();vv=-tr.velocity_z_mps.to_numpy();hh=tr.altitude_m.to_numpy()
        assert abs(np.interp(row.ground_hit_s,tt,vv)-row.impact_descent_mps)<1e-7
        start=row.ground_hit_s-M['settled_duration_s']
        window=np.r_[start,tt[(tt>start)&(tt<row.ground_hit_s)],row.ground_hit_s]
        ratios=np.interp(window,tt,vv)/baseline
        maximum=float(np.max(np.abs(ratios-1)))
        passed=bool(start>=row.deployment_s and maximum<=M['tolerance_fraction']+1e-12)
        # Find the last entry into the speed band before impact, interpolating the boundary.
        ts=np.r_[row.deployment_s,tt[(tt>row.deployment_s)&(tt<row.ground_hit_s)],row.ground_hit_s]
        vs=np.interp(ts,tt,vv)/baseline
        outside=np.abs(vs-1)>.05
        if outside[-1]:settled=0.;entered=float('nan')
        elif not outside.any():entered=row.deployment_s;settled=row.ground_hit_s-entered
        else:
            i=int(np.flatnonzero(outside)[-1]);bound=1.05 if vs[i]>1.05 else .95
            frac=(bound-vs[i])/(vs[i+1]-vs[i]);entered=float(ts[i]+frac*(ts[i+1]-ts[i]))
            settled=row.ground_hit_s-entered
        required_estimate=float('nan')
        if np.isfinite(entered) and entered+1<=row.ground_hit_s:
            required_estimate=(row.deployment_altitude_m-np.interp(entered+1,tt,hh))*FT
        record=row._asdict();record.update(baseline_descent_mps=baseline,impact_speed_ratio=row.impact_descent_mps/baseline,
            final_second_max_abs_error_pct=100*maximum,settled_duration_s=settled,band_entry_time_s=entered,
            estimated_required_height_ft=required_estimate,passes=passed)
        records.append(record)
    data=pd.DataFrame(records);data.to_csv(folder(height_ft)/'settling_metrics.csv',index=False)
    result={'altitude_setting_ft':height_ft,'altitude_setting_m':height_ft*.3048,'passed':int(data.passes.sum()),'completed':30,
            'worst_final_second_error_pct':float(data.final_second_max_abs_error_pct.max()),
            'minimum_settled_duration_s':float(data.settled_duration_s.min()),
            'impact_descent_mean_mps':float(data.impact_descent_mps.mean()),'impact_descent_sd_mps':float(data.impact_descent_mps.std()),
            'actual_deployment_height_mean_ft':float(data.deployment_altitude_m.mean()*FT),
            'actual_deployment_height_min_ft':float(data.deployment_altitude_m.min()*FT),
            'actual_deployment_height_max_ft':float(data.deployment_altitude_m.max()*FT),
            'estimated_required_height_max_ft':float(data.estimated_required_height_ft.max())}
    (folder(height_ft)/'settling_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'{height_ft:g} ft: {result["passed"]}/30 pass; worst final-second error {result["worst_final_second_error_pct"]:.3f}%; minimum settled duration {result["minimum_settled_duration_s"]:.3f} s',flush=True)
    return result

def batch(heights):
    results={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={pool.submit(run,h):h for h in heights}
        for f in as_completed(fs):results[fs[f]]=f.result()
    return results

def main():
    results=batch([25.,50.,100.])
    while not any(r['passed']==30 for r in results.values()):
        h=max(results)*2;results[h]=run(h)
    while not any(r['passed']<30 for r in results.values()):
        h=min(results)/2;results[h]=run(h)
    high=min(h for h,r in results.items() if r['passed']==30)
    low=max(h for h,r in results.items() if h<high and r['passed']<30)
    estimate=results[high]['estimated_required_height_max_ft']
    trials=sorted({float(max(math.ceil(low+1),min(math.floor(high-1),math.floor(estimate)-1))),
                   float(max(math.ceil(low+1),min(math.floor(high-1),math.ceil(estimate)+1)))})
    results.update(batch([h for h in trials if low<h<high and h not in results]))
    while True:
        high=min(h for h,r in results.items() if r['passed']==30)
        low=max(h for h,r in results.items() if h<high and r['passed']<30)
        assert all(r['passed']==30 for h,r in results.items() if h>=high),'Nonmonotonic settling; inspect'
        pd.DataFrame(results.values()).sort_values('altitude_setting_ft').to_csv(OUT/'sweep_summary.csv',index=False)
        if high-low<=1.000001:break
        if high-low<=4:
            results.update(batch([float(h) for h in range(math.floor(low)+1,math.ceil(high)) if float(h) not in results]))
        elif results[low]['minimum_settled_duration_s']>=.9:
            # A nearly passing case gives a close lower bound: test adjacent feet
            # before spending another ensemble on the middle of a wide bracket.
            results.update(batch([low+1,low+2]))
        else:
            mid=float(math.floor((low+high)/2));results[mid]=run(mid)
    # Save the selected native 30-flight ensemble for reopening in the requested app.
    previous=pd.read_csv(folder(high)/'individual_metrics.csv')
    needs_rerun=not (folder(high)/'J800T_native_ensemble.ork').exists()
    final=run(high,save=True)
    rerun=pd.read_csv(folder(high)/'individual_metrics.csv')
    assert np.allclose(previous.select_dtypes('number'),rerun.select_dtypes('number'),atol=1e-10,rtol=0,equal_nan=True)
    report={'minimum_tested_passing_trigger_ft':high,'minimum_tested_passing_trigger_m':high*.3048,
            'highest_tested_failing_trigger_ft':low,'resolution_ft':high-low,'criterion':M['criterion'],
            'final':final,'failed':results[low],'baseline_descent_mean_fps':float(BASE.impact_descent_mps.mean()*FT),
            'native_ensemble_file':str(folder(high)/'J800T_native_ensemble.ork'),
            'total_simulated_flights':30*(len(results)+int(needs_rerun)),'same_draws_as_prior_30':True,
            'selected_native_ensemble_saved':True,'selected_case_rerun_for_export':needs_rerun}
    src=M['source_inputs']['canards'];assert hashlib.sha256(Path(src['path']).read_bytes()).hexdigest()==src['sha256']
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
