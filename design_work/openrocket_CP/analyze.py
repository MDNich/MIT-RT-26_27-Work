"""Fit only named geometries and the specified states. All distances measured aft of nose in diameters."""
from pathlib import Path
from collections import defaultdict
import csv, gzip, json, math
import numpy as np
D=Path(__file__).resolve().parent; R=D/'results'; I=D/'inputs'
def rows(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else p.open()) as f: return list(csv.DictReader(f))
def write(name,data):
    with (R/name).open('w') as f:
        w=csv.DictWriter(f,data[0].keys()); w.writeheader(); w.writerows(data)
def mix(k,x0,n0,x1,n1):
    return ((1-k)*x0*n0+k*x1*n1)/((1-k)*n0+k*n1)
def rms(d): return float(np.sqrt(np.mean(d*d)))
def load():
    design=json.loads((D/'design.json').read_text());splits={n:s for s in ('fit','holdout','control','sensitivity','blind') for n in design[s]}
    def key(r): return (r['case'],int(r['alpha_deg']),round(float(r['mach'])*100))
    ras={key(r):r for r in rows(I/'ras-states.csv.gz')}
    data=defaultdict(list)
    for v in rows(R/'openrocket.csv.gz'):
        n,a,i=key(v)
        if (n,a,i) not in ras: continue
        rr=ras.pop((n,a,i));dia=float(v['D_m']);data[n,a].append([i/100,float(v['x0_D']),float(v['n0']),float(v['x1_D']),float(v['n1']),float(rr['cp_in'])*.0254/dia,float(rr['cn']),float(rr['cna_0_4'])])
    assert not ras
    data={key:np.array(vals).T for key,vals in data.items()}
    for n in splits:
        for a in (0,2,4):
            t=data[n,a];assert np.isfinite(t).all() and np.all(np.diff(t[0])>0)
            if splits[n]=='control' or n.startswith('Hbody'):
                np.testing.assert_array_equal(t[1:3],t[3:5])
            mask=t[0]<=1.10;np.testing.assert_array_equal(t[1:3,mask],t[3:5,mask])
    return design,splits,data
def fit(data,names):
    vals=np.concatenate([data[n,0][:,(data[n,0][0]>=1.5)&(data[n,0][0]<=3)] for n in names],axis=1)
    assert vals.shape[1]==151*len(names)
    _,x,n,y,q,t,*_=vals
    grid=np.arange(1001)/1000; scores=np.array([rms(mix(k,x,n,y,q)-t) for k in grid])
    return float(grid[scores.argmin()]),grid,scores
bands={'sub':(.1,.8),'trans':(.81,1.30),'sup':(1.50,3.00),'upper':(3.01,5.00)}
def analyze():
    design,splits,data=load(); k,grid,scores=fit(data,design['fit']);print('k =',k)
    fits=[dict(excluded='none',k=k)]
    for n in design['fit']:
        fits.append(dict(excluded=n,k=fit(data,[x for x in design['fit'] if x!=n])[0]))
    write('fits.csv',fits)
    metrics=[]; pooled=defaultdict(list); coeffs={'legacy':0.,'finite':1.,'fit':k}
    per_angle={}
    for (name,alpha),tab in data.items():
        m,x,n,y,q,t,rcn,rs=tab
        for band,(lo,hi) in bands.items():
            mask=(m>=lo)&(m<=hi)
            if not np.any(mask): continue
            for model,weight in coeffs.items():
                err=(mix(weight,x,n,y,q)-t)[mask]
                o=dict(case=name,split=splits[name],alpha=alpha,band=band,model=model,points=len(err),bias=float(err.mean()),mae=float(abs(err).mean()),rmse=rms(err),max_abs=float(abs(err).max()))
                metrics.append(o);pooled[splits[name],alpha,band,model].append(err)
                if alpha==4:
                    # OR's effective CNa = CN / alpha for the uncanted fixtures; RAS native secant explicitly between 0 and 4.
                    secant=(1-weight)*n+weight*q
                    np.testing.assert_allclose(rcn[mask]/np.deg2rad(4),rs[mask],rtol=1e-5,atol=1e-6)
                    per_angle[name,model,band]=rms((secant-rs)[mask])
    write('case-metrics.csv',metrics)
    summary=[]
    for (s,a,b,m),es in pooled.items():
        er=np.concatenate(es);summary.append(dict(split=s,alpha=a,band=b,model=m,cases=len(es),points=len(er),bias=float(er.mean()),mae=float(abs(er).mean()),rmse=rms(er),max_abs=float(abs(er).max())))
    write('group-metrics.csv',summary)
    write('force-audit.csv',[dict(case=n,model=m,band=b,cna_rmse_rad=v) for (n,m,b),v in per_angle.items()])
    tunnel=rows(R/'tunnel.csv');phys=[]
    for g in ['ARCAS','Yuska-B']:
        get=lambda t: [v for v in tunnel if v['geometry']==g and v['model']==t and float(v['mach'])>=1.50]
        a,b=get('legacy'),get('candidate');assert len(a)==len(b)==5 and [z['mach'] for z in a]==[z['mach'] for z in b]
        col=lambda r,key:np.array([float(z[key]) for z in r])
        x=col(a,'predicted_cp_d');y=col(b,'predicted_cp_d');n=col(a,'predicted_cna');q=col(b,'predicted_cna')
        for model,w in coeffs.items():
            c=mix(w,x,n,y,q);t=(1-w)*n+w*q
            phys.append(dict(vehicle=g,model=model,cp_rmse=rms(c-col(a,'measured_cp_d')),cna_rmse=rms(t-col(a,'measured_cna')),moment_rmse=rms((1-w)*col(a,'predicted_cm_alpha')+w*col(b,'predicted_cm_alpha')-col(a,'measured_cm_alpha'))))
    write('tunnel-metrics.csv',phys)
    brief=[v for v in summary if v['alpha']==0 and v['band']=='sup']
    print([(v['split'],v['model'],round(v['rmse'],4)) for v in brief])
    print(fits);print(phys)
    return k
if __name__=='__main__': analyze()
