"""Paired, native OpenRocket deployment-delay ensembles; no physics overrides."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, subprocess, time, math, hashlib
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'manifest.json').read_text())

def folder(delay):
    return OUT/f'delay_{delay:08.3f}s'

def run(delay,save=False):
    dest=folder(delay);dest.mkdir(exist_ok=True)
    if not (dest/'process_result.json').exists() or save:
        cmd=[M['runtime'],'-Xmx4g','-Djava.awt.headless=true','-cp',f'{OUT}/build:{OUT}/engine.jar',
             'BaliusNativeEnsemble',str(OUT/'source.ork'),str(dest),'30','.05','.02','20261018','2',
             '4.4704',str(delay),str(save).lower()]
        start=time.time()
        with (dest/'engine.log').open('w') as log:
            p=subprocess.Popen(cmd,stdout=log,stderr=log)
            (dest/'process.json').write_text(json.dumps({'pid':p.pid,'command':cmd,'start_epoch':start},indent=2))
            print(f'Started delay {delay:.3f} s',flush=True)
            code=p.wait()
        (dest/'process_result.json').write_text(json.dumps({'returncode':code,'elapsed_s':time.time()-start},indent=2))
        if code:raise RuntimeError(f'Native ensemble failed at delay {delay}: inspect {dest}/engine.log')
        print(f'Completed delay {delay:.3f} s',flush=True)
    assert json.loads((dest/'process_result.json').read_text())['returncode']==0
    d=pd.read_csv(dest/'individual_metrics.csv')
    s=json.loads((dest/'summary.json').read_text())
    assert len(d)==30 and s['completed']==30 and s['excluded']==0
    assert s['recovery']['delay_s']==delay and s['wind_mean_mps']==4.4704
    # OR can process a scheduled deployment event after landing; it is not a flight deployment.
    after_ground=d.deployment_s>=d.ground_hit_s
    d.loc[after_ground,['deployment_s','deployment_altitude_m','deployment_descent_mps','deployment_total_mps']]=np.nan
    return d

def batch(delays):
    result={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(run,d):d for d in delays}
        for f in as_completed(futures):result[futures[f]]=f.result()
    return result

def assess(delay,d,baseline):
    assert np.array_equal(d[['mass_multiplier','cd_multiplier']].values,
                          baseline[['mass_multiplier','cd_multiplier']].values)
    assert np.allclose(d.apogee_m,baseline.apogee_m,atol=1e-7,rtol=0)
    ratio=d.impact_descent_mps/baseline.impact_descent_mps
    passed=(ratio.between(.95,1.05)&d.deployment_s.notna()&(d.deployment_s<d.ground_hit_s))
    d=d.assign(impact_descent_ratio=ratio,passes=passed)
    d.to_csv(folder(delay)/'paired_comparison.csv',index=False)
    return {'delay_s':delay,'passed':int(passed.sum()),'attempted':30,
            'max_speed_ratio':float(ratio.max()),'min_speed_ratio':float(ratio.min()),
            'max_abs_speed_difference_pct':float(100*(ratio-1).abs().max()),
            'impact_descent_mean_mps':float(d.impact_descent_mps.mean()),
            'impact_descent_sd_mps':float(d.impact_descent_mps.std()),
            'deployment_altitude_mean_m':float(d.deployment_altitude_m.mean()),
            'deployment_altitude_sd_m':float(d.deployment_altitude_m.std()),
            'deployment_altitude_min_m':float(d.deployment_altitude_m.min()),
            'deployment_altitude_max_m':float(d.deployment_altitude_m.max())}

def main():
    initial=batch([1.,1000.]);baseline=initial[1.]
    no_chute=initial[1000.]
    assert no_chute.deployment_s.isna().all()
    upper=float((no_chute.ground_hit_s-no_chute.apogee_event_s).min())
    print(f'Earliest unchuted impact: {upper:.3f} s after apogee',flush=True)
    results={1.:assess(1.,baseline,baseline)}
    coarse=[float(x) for x in range(5,5*math.ceil(upper/5)+1,5)]
    for delay,data in sorted(batch(coarse).items()):results[delay]=assess(delay,data,baseline)
    pd.DataFrame(results.values()).sort_values('delay_s').to_csv(OUT/'sweep_summary.csv',index=False)
    failed=[d for d,r in results.items() if r['passed']<30]
    assert failed,'Need a failed upper bound'
    high=min(failed);low=max(d for d,r in results.items() if d<high and r['passed']==30)
    assert all(r['passed']<30 for d,r in results.items() if d>=high),'Nonmonotonic acceptance; inspect sweep'
    # Search down from the earliest unchuted impact on a 0.1-s grid. This checks
    # every later candidate instead of assuming speed error varies monotonically.
    candidates=[round(x/10,1) for x in range(math.floor(upper*10),math.ceil(low*10)-1,-1)]
    for start in range(0,len(candidates),4):
        part=candidates[start:start+4]
        for delay,data in batch(part).items():
            row=assess(delay,data,baseline);results[delay]=row
            print(f'Refine {delay:.3f} s: {row["passed"]}/30 pass, max absolute difference {row["max_abs_speed_difference_pct"]:.3f}%',flush=True)
        pd.DataFrame(results.values()).sort_values('delay_s').to_csv(OUT/'sweep_summary.csv',index=False)
        passing=[d for d in part if results[d]['passed']==30]
        if passing:
            low=max(passing);high=min(d for d in results if d>low and results[d]['passed']<30)
            assert high-low<=.100001
            break
    else:raise RuntimeError('No passing delay on descending refinement grid')
    # Preserve an app-openable native ensemble at the limiting passing delay.
    final=run(low,save=True);final_row=assess(low,final,baseline)
    assert final_row['passed']==30
    report={'latest_tested_passing_delay_after_apogee_s':low,
            'first_failing_delay_after_apogee_s':high,'bracket_width_s':high-low,
            'criterion':M['criterion'],'limiting_result':final_row,
            'baseline_vertical_impact_mean_mps':float(baseline.impact_descent_mps.mean()),
            'baseline_vertical_impact_sd_mps':float(baseline.impact_descent_mps.std()),
            'deployment_time_after_launch_mean_s':float(final.deployment_s.mean()),
            'deployment_time_after_launch_sd_s':float(final.deployment_s.std()),
            'earliest_unchuted_impact_after_apogee_s':upper,
            'total_simulated_flights':30*(len(results)+2),
            'native_ensemble_file':str(folder(low)/'J800T_native_ensemble.ork')}
    src=M['source_inputs']['canards']
    assert hashlib.sha256(Path(src['path']).read_bytes()).hexdigest()==src['sha256']
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
