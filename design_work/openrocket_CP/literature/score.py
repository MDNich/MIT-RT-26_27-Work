from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze import *
from transfer import model,moments
def main():
    design,split,data=load();pars=json.loads((R/'transfer.json').read_text());a,b=pars['a'],pars['b']
    truth={(n,al,round(100*m)):v for (n,al),tab in data.items() for m,v in zip(tab[0],tab[5])}
    for p in sorted((I/'native-final/models').glob('*.CDX1')):
        from xml.etree import ElementTree as E
        d=float(E.parse(p).findtext('.//NoseCone/Diameter'));n=p.stem; split[n]='confirmation'
        for r in rows(I/'native-final/rasaero'/(n+'.csv')):
            m=float(r['Mach']);al=int(r['Alpha'])
            if .1<=m<=5 and al in (0,2,4):truth[n,al,round(100*m)]=float(r['CP'])/d
    zz=defaultdict(list);by=defaultdict(list); maxerr=0;cnt=0
    for files in [('openrocket','chart-wing','chart-combined','endpoints-transfer'),('final-endpoints','final-wing','final-combined','final-transfer')]:
        datasets=[rows(R/(f+'.csv.gz')) for f in files]
        for u,v,z,t in zip(*datasets,strict=True):
            key=lambda w:(w['case'],int(w['alpha_deg']),round(100*float(w['mach'])))
            n,al,m=key(u);assert key(u)==key(v)==key(z)==key(t)
            def pt(row):return moments(float(row['x1_D']),float(row['n1']))
            cp,load_=model([pt(row) for row in (u,v,z)],a,b)
            maxerr=max(maxerr,abs(cp-float(t['x1_D'])),abs(load_-float(t['n1']))); cnt+=1
            ref=truth[n,al,m];band=next((k for k,(l,h) in bands.items() if round(100*l)<=m<=round(100*h)),None)
            if band is None:continue
            x0,n0,x1,n1=[float(u[k]) for k in ('x0_D','n0','x1_D','n1')]
            for label,x in [('Legacy',x0),('Full',x1),('Scalar',mix(.459,x0,n0,x1,n1)),('Wing',float(v['x1_D'])),('Combined',float(z['x1_D'])),('Transfer',float(t['x1_D']))]:
                zz[split[n],al,band,label].append(x-ref);by[n,al,band,label].append(x-ref)
    assert cnt==30*491*3 and maxerr<1e-8
    def sums(d,keyname):
        ret=[]
        for (s,al,band,label),es in d.items():
            e=np.array(es);ret.append({keyname:s,'alpha':al,'band':band,'model':label,'n':len(e),'rmse':rms(e),'bias':e.mean(),'max_abs':abs(e).max()})
        return ret
    met=sums(zz,'split');write('chart-groups.csv',met);write('chart-cases.csv',sums(by,'case'))
    out=[]
    for nm,f in [('Wing','wing-tunnel.csv'),('Combined','chart-tunnel.csv'),('Transfer','transfer-tunnel.csv')]:
        r=rows(R/f)
        for g in ['ARCAS','Yuska-B']:
            rr=[x for x in r if x['geometry']==g and x['model']=='candidate' and float(x['mach'])>=1.5]
            out.append(dict(model=nm,geometry=g,**{key:rms(np.array([float(z['predicted_'+key])-float(z['measured_'+key]) for z in rr])) for key in ('cp_d','cna','cm_alpha')}))
    write('chart-tunnel-metrics.csv',out)
    print('direct overlay check',cnt,maxerr)
    for grp in ['fit','holdout','blind','confirmation','control']:
        print(grp,[(v['model'],round(v['rmse'],3)) for v in met if v['split']==grp and v['alpha']==0 and v['band']=='sup'])
    print(out)
if __name__=='__main__':main()
