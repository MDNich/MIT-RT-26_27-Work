"""Score original native exports, independent tunnel measurements and integrated Iris flights."""
import csv
import gzip
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/afterbody'
NATIVE = ROOT / 'inputs/native-afterbody'
MODES = ('previous', 'segments', 'center', 'tail', 'crossflow', 'combined','narrow')
CASES = ('A-straight','A-step','A-boattail','A-flare','B-straight','B-boattail','B-flare',
         'B-finned-straight','B-finned-boattail','C-finned-straight','C-finned-boattail','Iris-constant-finless','Iris-constant-finned','forebody','finless','finned')
MACH = np.arange(150,301)


def read(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', newline='') as stream:
        return list(csv.DictReader(stream))


def write(name, records):
    with (OUT / (name + '.csv')).open('w', newline='') as f:
        writer = csv.DictWriter(f, records[0].keys())
        writer.writeheader()
        writer.writerows(records)


def col(rows, name):
    return np.array([float(r[name]) for r in rows])


def rms(x):
    return float(np.sqrt(np.mean(x**2)))


def grid(rows, name, angle, label):
    subset = sorted((r for r in rows if float(r[angle]) == label and 1.5 <= float(r[name]) <= 3),
                    key=lambda r: float(r[name]))
    np.testing.assert_allclose(col(subset, name), MACH / 100, rtol=0, atol=1e-10)
    return subset


def static():
    native = {}
    for case in CASES:
        folder = NATIVE if case[0].isupper() else ROOT/'inputs/iris-components'
        records = read(folder/'rasaero'/(case+'.csv'))
        for a in (0,2,4):
            r = grid(records, 'Mach', 'Alpha', a)
            native[case,a] = (col(r,'CP'), col(r,'CN'))
    scores, probes, increments, invariance, tunnel = [], [], [], [], []
    pairs = [('A-straight', f'A-{k}',4.) for k in ('step','boattail','flare')]
    pairs += [('B-straight', f'B-{k}',3.) for k in ('boattail','flare')]
    pairs += [('B-finned-straight','B-finned-boattail',3.),('C-finned-straight','C-finned-boattail',5.),('Iris-constant-finless','finless',4.20),
              ('Iris-constant-finned','finned',4.20)]
    for mode in MODES:
        groups = defaultdict(list)
        for r in read(OUT/(mode+'.csv')):
            groups[r['geometry']].append(r)
        loads = {}
        for case in CASES:
            for a in (0,2,4):
                r = grid(groups[case], 'mach','alpha_deg',a)
                d = col(r,'D_in')
                x, n = col(r,'cp_in'), col(r,'n_rad') * np.deg2rad(a)
                rx, rn = native[case,a]
                err = (x-rx)/d
                scores.append(dict(model=mode,case=case,angle=a,points=len(err),cp_rms_D=rms(err),
                                   cp_bias_D=np.mean(err),cn_rms=rms(n-rn) if a else '',
                                   nose_first_moment_rms=rms((n*x-rn*rx)/d) if a else ''))
                j = 280-150
                probes.append(dict(model=mode,case=case,angle=a,mach=2.8,diameter_in=d[j],
                                   cp_in=x[j],native_cp_in=rx[j],cn=n[j],native_cn=rn[j]))
                loads[case,a] = (d,x,n,rx,rn)
        for base,variant,ref in pairs:
            for a in (2,4):
                def scaled(name):
                    d,x,n,rx,rn = loads[name,a]
                    return (d/ref)**2*np.stack([n, n*x/ref, rn, rn*rx/ref])
                dn,dj,rdn,rdj = scaled(variant)-scaled(base)
                increments.append(dict(model=mode,variant=variant,base=base,angle=a,ref_D_in=ref,
                                       delta_cn_rms_error=rms(dn-rdn),delta_J_rms_error=rms(dj-rdj),
                                       delta_cn_280=dn[130],ras_delta_cn_280=rdn[130],delta_J_280=dj[130],ras_delta_J_280=rdj[130]))
        for a in (0,2,4):
            def split(n):
                r=grid(groups[f'split-{n}'],'mach','alpha_deg',a)
                return np.array([col(r,'cp_in')/4, col(r,'n_rad')])
            gap=np.max([np.abs(split(n)-split(1)) for n in (2,4)], axis=(0,2))
            invariance.append(dict(model=mode,angle=a,max_cp_spread_D=gap[0],max_slope_spread=gap[1]))
            if mode in ('segments','center','combined','narrow'):
                assert np.max(gap)<1e-8, (mode,a,gap)
        for r in read(ROOT/'inputs/tmx653/readings.csv'):
            item=next(x for x in groups[r['geometry']] if float(x['mach'])==float(r['mach']))
            d=1.25
            n=float(item['n_rad'])*(float(item['D_in'])/d)**2
            x=float(item['cp_in'])/d-1.22
            rn=float(r['cn_slope_per_deg'])*180/np.pi
            rx=float(r['cp_from_junction_D'])
            tunnel.append(dict(model=mode,case=r['geometry'],mach=r['mach'],slope=n,measured_slope=rn,
                               cp_D=x,measured_cp_D=rx,J=n*x,measured_J=rn*rx))
    for name,rows in [('native-scores',scores),('mach280',probes),('paired-increments',increments),
                      ('segmentation',invariance),('tmx653',tunnel)]:
        write(name,rows)
    summary=[]
    for mode in MODES:
        sides = [sorted((r for r in tunnel if r['case']==case and r['model']==mode),key=lambda r:float(r['mach']))
                 for case in ('blunt-straight','blunt-flare10')]
        for q in ('cp_D','slope','J'):
            gap=[col(rows,q)-col(rows,'measured_'+q) for rows in sides]
            summary.append(dict(model=mode,quantity=q,straight_rmse=rms(gap[0]),flare_rmse=rms(gap[1]),
                                flare_minus_control_rmse=rms(gap[1]-gap[0])))
    write('tmx653-summary',summary)
    tunnel=[]
    for mode,path in [('previous',ROOT/'results/transfer-tunnel.csv'),('combined',OUT/'earlier-tunnel.csv'),('narrow',OUT/'narrow-tunnel.csv')]:
        groups=defaultdict(list)
        for r in read(path):
            if r['model']=='candidate' and float(r['mach'])>=1.5: groups[r['geometry']].append(r)
        for name,r in groups.items():
            tunnel.append(dict(model=mode,case=name,points=len(r),**{q+'_rms':rms(col(r,'predicted_'+q)-col(r,'measured_'+q)) for q in ('cp_d','cna','cm_alpha')}))
    write('earlier-tunnel-scores',tunnel)


def flights():
    native_file, = (NATIVE/'iris-flight').glob('*.csv')
    fresh = read(native_file)
    old = read(ROOT/'inputs/native-iris-half/Iris-half-flight.csv')
    # Distinguish numerical repeatability from merely opening an archived file in Windows.
    repeat=[]
    assert len(fresh)==len(old) and all(x['Stage']==y['Stage'] for x,y in zip(fresh,old))
    for key in fresh[0]:
        if key!='Stage':
            repeat.append(dict(field=key,rows=len(fresh),max_abs_diff=np.max(np.abs(col(fresh,key)-col(old,key)))))
    write('native-flight-repeat',repeat)
    # The archived shared-state sweeps are only valid for this repeat if its states agree.
    for key in ('Time (sec)','Mach Number','Angle of Attack (deg)'):
        np.testing.assert_allclose(col(fresh,key),col(old,key),atol=1e-9,rtol=0)
    burn=[r for r in fresh if r['Stage']=='S' and 15.519<=float(r['Time (sec)'])<=20.771]
    t,ras=col(burn,'Time (sec)'),col(burn,'Stability Margin (cal)')
    assert len(t)>520
    result=[]
    def event(model,time,margin,error):
        i=np.argmin(margin)
        result.append(dict(model=model,minimum_cal=margin[i],minimum_s=time[i],burnout_cal=margin[-1],
                           rms_cal=rms(error),bias_cal=np.mean(error)))
    event('RASAero',t,ras,ras-ras)
    for name,prefix in [('previous','transfer'),('combined','afterbody'),('narrow','afterbody-narrow')]:
        r=read(ROOT/'results'/(prefix+'-preferred-candidate.csv.gz'))
        use=(col(r,'time_s')>15)&(col(r,'time_s')<21)&np.isclose(col(r,'diameter_m'),.10668)
        tt,ss=col(r,'time_s')[use],col(r,'margin_cal')[use]
        assert tt[0]<=t[0] and tt[-1]>=t[-1] and np.all(np.diff(tt)>0)
        interp=np.interp(t,tt,ss)
        # Continuous interpolation at the same endpoints plus all actual internal solver samples.
        inside=(tt>t[0])&(tt<t[-1])
        event(name,np.r_[t[0],tt[inside],t[-1]],np.r_[interp[0],ss[inside],interp[-1]],interp-ras)
    write('iris-flight',result)
    ref={float(r['Time (sec)']):r for r in fresh}
    oldbase=read(ROOT/'results/transfer-iris-static.csv')
    out=[]
    for mode in MODES:
        allrows=read(OUT/(mode+'-replay.csv'))
        if mode=='previous':
            for k in ('time_s','x1_D','n1','x0_D','n0'):
                np.testing.assert_allclose(col(allrows,k),col(oldbase,k),rtol=0,atol=1e-9)
        for name,r in [('burn',[r for r in allrows if r['stage']=='S' and 15.519<=float(r['time_s'])<=20.771]),
                       ('hot sustainer',[r for r in allrows if r['stage']=='S' and float(r['mach'])>=2])]:
            native=[ref[float(x['time_s'])] for x in r]
            err=col(r,'x1_D')-col(native,'CP (in)')*.0254/col(r,'D_m')
            out.append(dict(model=mode,window=name,samples=len(r),cp_rms_D=rms(err),
                            cp_bias_D=np.mean(err),last_time_s=r[-1]['time_s'],last_cp_error_D=err[-1]))
    write('iris-replay-scores',out)


if __name__=='__main__':
    static()
    flights()
