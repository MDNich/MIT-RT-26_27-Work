"""Burnout attribution sensitivity, branch replay and previous regression cohorts."""
from analyze import ROOT,O,R,PARTS,TERMS,read,write,rms
import json, math, xml.etree.ElementTree as ET
from collections import defaultdict
import numpy as np

def zero_attribution():
    # Native CP(0) is supplied, but the zero-incidence force derivative is not.
    # Use two potential-force secants and an alternate total-force secant to expose identifiability.
    refs={}
    for part in PARTS:
        area=(4.02/4.2)**2 if part=='forebody' else 1.
        for z in read(ROOT/'inputs/iris-components/rasaero'/(part+'.csv')):
            m,alpha=float(z['Mach']),int(z['Alpha'])
            if 1.5<=m<=3:refs[part,m,alpha]=(area,float(z['CN Potential']),float(z['CN']),float(z['CP'])/4.2)
    states={(z['model'],z['fixture'],z['geometry'],float(z['mach'])):(float(z['N']),float(z['J']))
            for z in read(O/'states.csv') if z['model']!='RAS' and float(z['alpha_deg'])==0}
    out=[]
    for m in [i/100 for i in range(150,301)]:
        for proxy,angle,col in [('potential2',2,1),('potential4',4,1),('total2',2,2)]:
            for model in ['transfer','handover']:
                for fam in ['cdx','ork']:
                    old=np.zeros(2);n_total,j_total=states[model,fam,'finned',m]
                    x=refs['finned',m,0][3];total=0
                    for term,p in zip(TERMS,PARTS):
                        v=refs[p,m,angle];n=v[0]*v[col]/math.radians(angle)
                        err=np.array(states[model,fam,p,m])-n*np.array([1.,refs[p,m,0][3]])
                        dn,dj=err-old;old=err;dx=(dj-x*dn)/n_total;total+=dx
                        out.append(dict(mach=m,model=model,fixture=fam,proxy=proxy,term=term,ras_geometry_N_est=n,delta_N=dn,delta_J=dj,cp_error_D=dx))
                    assert abs(total-j_total/n_total+x)<1e-9
    write('zero-attribution-sensitivity.csv',out)
    # Cross-check the aggregate slope proxy on the existing native flight at its own near-zero incidence.
    radio=[]; ms=np.arange(150,301)/100
    n=[refs['finned',m,2][1]/math.radians(2) for m in ms]
    for r in read(ROOT/'inputs/native-iris-half/Iris-half-flight.csv'):
        t=float(r['Time (sec)']);m=float(r['Mach Number']);a=math.radians(float(r['Angle of Attack (deg)']))
        if r['Stage']!='S' or not 15.52<=t<=20.771 or not 1.5<=m<=3 or not 0<a<math.radians(.05):continue
        actual=(float(r['CL'])*math.cos(a)+float(r['CD'])*math.sin(a))/a
        estimate=float(np.interp(m,ms,n))
        radio.append(dict(time_s=t,mach=m,alpha_rad=a,native_flight_secant=actual,potential_proxy=estimate,error=estimate-actual))
    write('slope-proxy-flight-check.csv',radio)

def regression():
    design=json.loads((ROOT/'design.json').read_text())
    groups={n:k for k,ns in design.items() if isinstance(ns,list) for n in ns}
    truth={(r['case'],int(r['alpha_deg']),round(100*float(r['mach']))):float(r['cp_in'])*.0254 for r in read(ROOT/'inputs/ras-states.csv.gz')}
    for file in (ROOT/'inputs/native-final/rasaero').glob('*.csv'):
        groups[file.stem]='confirmation'
        for r in read(file):
            if .10<=float(r['Mach'])<=5:
                truth[file.stem,int(r['Alpha']),round(100*float(r['Mach']))]=float(r['CP'])*.0254
    allscores={}
    for model,files in [('transfer',[R/'endpoints-transfer.csv.gz',R/'final-transfer.csv.gz']),('handover',[O/'static.csv.gz',O/'final.csv.gz'])]:
        vs=defaultdict(list)
        for f in files:
            for z in read(f):
                n=z['case'];a=int(z['alpha_deg']);i=round(100*float(z['mach']))
                if 150<=i<=300:vs[groups[n],a].append(float(z['x1_D'])-truth[n,a,i]/float(z['D_m']))
        for (g,a),v in vs.items():allscores[model,g,a]=dict(model=model,split=g,alpha_deg=a,samples=len(v),rmse=rms(v),bias=np.mean(v))
    write('regression.csv',list(allscores.values()))
    tt=[]
    for mod,p in [('handover',O/'tunnel.csv'),('transfer',R/'transfer-tunnel.csv')]:
        for case in ('ARCAS','Yuska-B'):
            r=[v for v in read(p) if v['geometry']==case and v['model']=='candidate' and float(v['mach'])>=1.50]
            metrics={key:rms([float(v['predicted_'+key])-float(v['measured_'+key]) for v in r]) for key in ('cna','cp_d','cm_alpha')}
            tt.append(dict(model=mod,vehicle=case,**metrics))
    write('earlier-tunnels.csv',tt)
    old=read(R/'iris-common-state.csv');new=read(O/'replay.csv');assert len(old)==len(new)
    replay=[]
    for u,v in zip(old,new):
        assert abs(float(u['time_s'])-float(v['time_s']))<1e-9 and u['stage']==v['stage']
        replay.append(dict(time_s=u['time_s'],stage=u['stage'],mach=u['mach'],ras_cp_D=u['ras_cp_D'],old_cp_D=u['transfer_cp_D'],new_cp_D=v['x1_D'],error_D=float(v['x1_D'])-float(u['ras_cp_D'])))
    write('replay-comparison.csv',replay)

if __name__=='__main__':
    zero_attribution();regression()
