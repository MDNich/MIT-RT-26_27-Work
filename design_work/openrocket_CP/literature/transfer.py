from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze import *
def moments(x,n):return np.stack([n,x*n])
def model(p,a,b):
    F,W,B=p
    t=F+a*(W-F)+b*(B-W);return t[1]/t[0],t[0]
def cases():
    z=[rows(R/f) for f in ('openrocket.csv.gz','chart-wing.csv.gz','chart-combined.csv.gz')];p={};it=lambda r:(r['case'],int(r['alpha_deg']),round(100*float(r['mach'])))
    for us in zip(*z,strict=True):
        n,al,i=it(us[0]);assert all(it(v)==(n,al,i) for v in us)
        p[n,al,i]=np.array([moments(float(r['x1_D']),float(r['n1'])) for r in us])
    return p
def tunnel():
    tt={}
    for g in ('ARCAS','Yuska-B'):
        sets=[]
        for f in ('tunnel.csv','wing-tunnel.csv','chart-tunnel.csv'):
            r=[v for v in rows(R/f) if v['model']=='candidate' and v['geometry']==g and float(v['mach'])>=1.5]
            cv=lambda k:np.array([float(z[k]) for z in r])
            sets.append(moments(cv('predicted_cp_d'),cv('predicted_cna')))
        tt[g]=(sets,cv('measured_cp_d'),cv('measured_cna'))
    return tt
def select():
    dd,ss,rr=load();ps=cases();ts=tunnel();P=np.stack([ps[n,0,i] for n in dd['fit'] for i in range(150,301)],axis=-1)
    Y=np.concatenate([rr[n,0][5,140:291] for n in dd['fit']]);scores=[]
    for a in np.linspace(0,1,51):
        for b in np.linspace(0,1,51):
            z,_=model(P,a,b); err=rms(z-Y);ok=True
            for g,(T,X,N) in ts.items():
                x,n=model(T,a,b);sf,nf=model(T,0,0)
                ok &= rms(x-X)<=rms(sf-X)+.1+1e-10 and rms(n-N)<=1.05*rms(nf-N)+1e-10
            scores.append(dict(a=a,b=b,train_rmse=err,passes_tunnel=bool(ok)))
    best=min((s for s in scores if s['passes_tunnel']),key=lambda s:s['train_rmse']);write('transfer-grid.csv',scores)
    (R/'transfer.json').write_text(json.dumps(best,indent=2)+'\n');print(best)
    print('unconstrained',min(scores,key=lambda s:s['train_rmse']))
if __name__=='__main__':select()
