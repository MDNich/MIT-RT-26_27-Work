"""Reference-area normalization, matched state errors, component load differences, and NACA scores."""
from pathlib import Path
from collections import defaultdict
import csv, gzip, math, json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results'; O=R/'followup'
MODELS=('legacy','full','charts','transfer','handover')
PARTS=('forebody','finless','finned')
TERMS=('forebody','remaining airframe','installed fins')
D=4.2
def read(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:return list(csv.DictReader(f))
def write(name,rows):
    with (O/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
def rms(x):return float(np.sqrt(np.mean(np.square(x))))
def load_rows():
    tables={m:read(O/(m+'-loads.csv')) for m in MODELS}
    measured={}
    for part in PARTS:
        area_ratio=(4.02/D)**2 if part=='forebody' else 1.
        for r in read(ROOT/'inputs/iris-components/rasaero'/(part+'.csv')):
            mach,alpha=float(r['Mach']),int(r['Alpha'])
            if not 1.50<=mach<=3:continue
            pos=float(r['CP'])/D
            n=float(r['CN'])*area_ratio/math.radians(alpha) if alpha else 0.
            measured[part,mach,alpha]=(n,n*pos,pos)
    return tables,measured
def component_audit(tables,ras):
    states={};allrows=[];increments=[];contributions=[]
    for model,rows in tables.items():
        for r in rows:
            if r['family']=='TN3795':continue
            mach=float(r['mach']);a=int(float(r['alpha_deg']));part=r['part'];fam=r['family']
            n=float(r['cna_per_rad']);x=float(r['cp_in'])/D
            states[model,fam,part,mach,a]=(n,n*x,x)
    for (part,m,a),v in ras.items():states['RAS','cdx',part,m,a]=v
    for model,fam in [('RAS','cdx')]+[(m,f) for m in MODELS for f in ('ork','cdx')]:
        keys=sorted((mach,a) for mm,ff,p,mach,a in states if (mm,ff,p)==(model,fam,'finned'))
        for m,a in keys:
            prev=np.zeros(2)
            for part,term in zip(PARTS,TERMS):
                n,j,x=states[model,fam,part,m,a]
                allrows.append(dict(model=model,fixture=fam,geometry=part,mach=m,alpha_deg=a,cp_D=x,N=n if a or model!='RAS' else '',J=j if a or model!='RAS' else ''))
                if model=='RAS' and a==0:continue
                pair=np.array([n,j]);dn,dj=pair-prev;prev=pair
                increments.append(dict(model=model,fixture=fam,term=term,mach=m,alpha_deg=a,N=dn,J=dj))
            if model=='RAS' or not a or ('finned',m,a) not in ras:continue
            n_total,j_total,_=states[model,fam,'finned',m,a];x_ref=ras['finned',m,a][2]
            old=np.zeros(2);sum_error=0
            for p,term in zip(PARTS,TERMS):
                error=np.array(states[model,fam,p,m,a][:2])-np.array(ras[p,m,a][:2]);dn,dj=error-old;old=error
                dx=(dj-x_ref*dn)/n_total;sum_error+=dx
                contributions.append(dict(model=model,fixture=fam,term=term,mach=m,alpha_deg=a,delta_N=dn,delta_J=dj,cp_error_D=dx))
            assert abs(sum_error-(j_total/n_total-x_ref))<1e-9
    write('states.csv',allrows);write('increments.csv',increments);write('attribution.csv',contributions)
    # Test matching to chart fin (with fixed body removed) at the lower join, to prior blend at upper.
    slopes=[]
    for normal,neighbor in [(1.15,'charts'),(1.30,'transfer')]:
        center=normal*math.hypot(5,3.5)/3.5
        for alpha in (0,2,4):
            for col,label in [(0,'N'),(1,'J')]:
                def inc(mod,m):
                    key=round(m,9)
                    return states[mod,'ork','finned',key,alpha][col]-states[mod,'ork','finless',key,alpha][col]
                mod='handover';h=1e-5
                def derivative(mod,side):return side*(-3*inc(mod,center)+4*inc(mod,center+side*h)-inc(mod,center+2*side*h))/(2*h)
                v=inc(mod,center)-inc(neighbor,center);sl=derivative(mod,-1);sr=derivative(mod,1)
                slopes.append(dict(normal_mach=normal,mach=center,alpha=alpha,quantity=label,value_error=v,left_slope=sl,right_slope=sr,branch_slope_error=sr-derivative(neighbor,1)))
                assert abs(v)<2e-8 and abs(sl-sr)<.01 and abs(sr-derivative(neighbor,1))<.01
    write('join-check.csv',slopes)
def tn_audit(tables):
    body_d=1.5; area=math.pi*body_d**2/4; out=[];interaction=[];errors=defaultdict(list)
    tn=read(ROOT/'followup/tn3795.csv')
    for model,allrows in tables.items():
        pred={(int(r['wing']),float(r['mach']),r['part']):r for r in allrows if r['family']=='TN3795'}
        for geom in tn:
            wing=int(geom['wing']);split=geom['split'];S=float(geom['area_in2']);c=float(geom['mac_in']);xc=8.-float(geom['root_in'])/3.
            for m,suffix in [(1.50,'M150'),(2.02,'M202')]:
                packed={}
                for part in ('body','wing','combined'):
                    row=pred[wing,m,part];n=float(row['cna_per_rad']);x=float(row['cp_in']);cd0=float(row['ca0'])
                    if part=='body':
                        ref_area=area;chord=11.;xref=0
                        l_exp=(.034 if m==1.50 else .046)*180/math.pi;moment_exp=-.20*l_exp
                    else:
                        ref_area=S;chord=c;xref=xc
                        l_exp=float(geom[part+'_lift_deg_'+suffix])*180/math.pi
                        moment_exp=l_exp*float(geom[part+'_dcm_dcl_'+suffix])
                    factor=area/ref_area
                    lift=(n-cd0)*factor
                    moment=n*factor*(xref-x)/chord
                    # NACA uses pitching moment / lift as an effective axial station.
                    effective_cp=xref-chord*moment/lift
                    measured_cp=xref-chord*moment_exp/l_exp
                    vals=dict(lift=lift-l_exp,moment=moment-moment_exp,effective_cp_D=(effective_cp-measured_cp)/body_d)
                    if part!='body' or wing==1:
                        out.append(dict(model=model,wing=wing if part!='body' else 0,split=split if part!='body' else 'shared',part=part,mach=m,
                            measured_lift=l_exp,predicted_lift=lift,measured_moment=moment_exp,predicted_moment=moment,
                            measured_cp_in=measured_cp,predicted_cp_in=effective_cp,predicted_axial_cd0=cd0*factor))
                    if part!='body':errors[model,split,part].append(list(vals.values()))
                    # Transform to a common lift-based nose-datum convention for *both* lab and model.
                    # This uses the paper's lift/centroid convention; exact body-axis shift also involves axial drag.
                    packed[part]=np.array([l_exp*ref_area,lift*ref_area, (moment_exp*chord-l_exp*xref)*ref_area,(moment*chord-lift*xref)*ref_area])
                delta=(packed['combined']-packed['body']-packed['wing'])/np.array([S,S,S*c,S*c])
                interaction.append(dict(model=model,split=split,wing=wing,mach=m,measured_lift=delta[0],predicted_lift=delta[1],
                    measured_moment=delta[2],predicted_moment=delta[3]))
    write('tn-native.csv',out);write('tn-interference.csv',interaction)
    for model in MODELS:
        for split in ('development','blind'):
            subset=[r for r in interaction if r['model']==model and r['split']==split]
            errors[model,split,'interference']=[[r['predicted_lift']-r['measured_lift'],r['predicted_moment']-r['measured_moment'],0.] for r in subset]
    summary=[]
    for (mod,split,part),list_ in errors.items():
        er=np.array(list_)
        summary.append(dict(model=mod,split=split,part=part,samples=len(er),lift_rms=rms(er[:,0]),moment_rms=rms(er[:,1]),effective_cp_rms_D=rms(er[:,2]) if part!='interference' else ''))
    write('tn-metrics.csv',summary)
def flight_audit():
    ras=read(ROOT/'inputs/native-iris-half/Iris-half-flight.csv')
    r=[v for v in ras if 15.519<=float(v['Time (sec)'])<=20.771]
    t=np.array([float(v['Time (sec)']) for v in r]);sm=np.array([float(v['Stability Margin (cal)']) for v in r]);out=[]
    def event(name,t,s,err):
        j=np.argmin(s);out.append(dict(model=name,min_s=t[j],minimum=s[j],burnout=s[-1],burn_rms=rms(err),bias=np.mean(err)))
    event('RAS',t,sm,sm-sm)
    for name in ('transfer','handover','charts'):
        raw=read(R/(name+'-preferred-candidate.csv.gz')); batch=[v for v in raw if 15.519<=float(v['time_s'])<=20.771]
        tt=np.array([float(v['time_s']) for v in batch]);ss=np.array([float(v['margin_cal']) for v in batch])
        # interpolate on the full separated run, including the first post-burn sample
        valid=[v for v in raw if 15<float(v['time_s'])<21]
        pred=np.interp(t,[float(v['time_s']) for v in valid],[float(v['margin_cal']) for v in valid]);event(name,tt,ss,pred-sm)
    write('flight.csv',out)
if __name__=='__main__':
    tables,ras=load_rows();component_audit(tables,ras);tn_audit(tables);flight_audit()
