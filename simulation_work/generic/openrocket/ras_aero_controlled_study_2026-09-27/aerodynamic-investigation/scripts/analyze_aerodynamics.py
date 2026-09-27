from pathlib import Path
import csv,json,math,xml.etree.ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
def read(path):
 rows=list(csv.DictReader(path.open()));return {k:np.array([float(r[k]) for r in rows]) for k in rows[0]}
def cf(re,m):
 f=np.where(re<1e4,.0148,1/(1.5*np.log(np.maximum(re,1))-5.6)**2)
 c1=1-.1*m*m;c2=(1+.15*m*m)**(-.58)
 return f*np.where(m<.9,c1,np.where(m>1.1,c2,(c2*(m-.9)+c1*(1.1-m))/.2))
cases=json.loads((R/'cases.json').read_text());data={};long=[];audit=[]
for case in cases:
 n=case['name'];o=read(R/'openrocket'/f'{n}.csv');raw=read(R/'rasaero'/f'{n}.csv');sel=raw['Alpha']==0
 r={k:v[sel] for k,v in raw.items()};assert len(r['Mach'])==2500 and np.all(np.diff(r['Mach'])>0)
 r={k:np.interp(o['mach'],r['Mach'],v) for k,v in r.items()}
 assert np.max(abs(r['CD']-r['CD Power-Off']))<1e-10
 root=ET.parse(R/'models'/f'{n}.CDX1').getroot();nose=root.find('RocketDesign/NoseCone');dia=float(nose.findtext('Diameter'));ln=float(nose.findtext('Length'))
 m=o['mach'];re_ratio=r['Reynolds Number']/o['re_length'];re_delta=o['friction']*(cf(r['Reynolds Number'],m)/cf(o['re_length'],m)-1)
 sinphi=(dia/2)/math.hypot(dia/2,ln);nose_alt=np.full(len(m),np.nan);good=m>=1.32
 nose_alt[good]=2.1*sinphi**2+.5*sinphi/np.sqrt(m[good]**2-1)
 alt=o['cd']-o['nose_pressure']+nose_alt
 data[n]={'o':o,'r':r,'re_delta':re_delta,'nose_alt':nose_alt,'nose_total':alt,'case':case}
 audit.append({'case':n,'raw_rows':len(sel),'alpha0_rows':int(sum(sel)),'matched_rows':len(m),'min_re_ratio':float(min(re_ratio)),'max_re_ratio':float(max(re_ratio)),'max_re_cd_correction_M_ge_0p1':float(max(abs(re_delta[m>=.1]))),'max_power_difference':float(max(abs(r['CD Power-Off']-r['CD Power-On'])))})
 for i,mach in enumerate(m):
  long.append({'case':n,'mach':mach,'ras_cd':r['CD'][i],'or_cd':o['cd'][i],'gap_ras_minus_or':r['CD'][i]-o['cd'][i],'or_re_match_delta':re_delta[i],'or_fin_local_re_delta':o['fin_local_re_delta'][i],'or_nose_pressure':o['nose_pressure'][i],'or_base':o['base'][i],'or_friction':o['friction'][i],'proposed_nose_cd':nose_alt[i],'proposed_nose_only_total':alt[i]})
with (R/'matched-coefficients.csv').open('w') as f:
 w=csv.DictWriter(f,long[0]);w.writeheader();w.writerows(long)
summary={'audit':audit,'nose_proposal':[],'selected':[],'checks':{}}
for n in ['Hbody','Sbody','Hbody-short','Hbody-long','Hbody-nose6','Hbody-nose18']:
 d=data[n];sel=d['o']['mach']>=1.32;y=d['r']['CD'][sel];old=d['o']['cd'][sel];new=d['nose_total'][sel]
 summary['nose_proposal'].append({'case':n,'n':int(sum(sel)),'baseline_mae':float(np.mean(abs(old-y))),'candidate_mae':float(np.mean(abs(new-y))),'baseline_mape_pct':float(np.mean(abs(old/y-1))*100),'candidate_mape_pct':float(np.mean(abs(new/y-1))*100),'candidate_max_abs_error':float(max(abs(new-y)))})
for n in ['Hsq','Hbev','Ssq','Sbev','Hbody','Sbody','Hsq-nearzero','Hbev-nearzero','Hbev-gentle','Hsq-long']:
 for mach in [.3,.8,1,1.2,1.5,2,3]:
  d=data[n];o=d['o'];r=d['r'];i=int(round(mach*100))-1;b='Sbody' if n.startswith('S') else 'Hbody-long' if n=='Hsq-long' else 'Hbody'
  summary['selected'].append({'case':n,'mach':mach,'ras_cd':r['CD'][i],'or_cd':o['cd'][i],'ras_fin_increment':r['CD'][i]-data[b]['r']['CD'][i],'or_fin_increment':o['cd'][i]-data[b]['o']['cd'][i],'local_re_delta':o['fin_local_re_delta'][i]})
# Count scaling is independent of fin count: discrepancy cannot be a count convention.
a=data['Hsq-count3']['r']['CD']-data['Hbody']['r']['CD'];b=.75*(data['Hsq']['r']['CD']-data['Hbody']['r']['CD'])
summary['checks']['ras_count3_vs_count4_scaled_max_error']=float(max(abs(a-b)))
summary['checks']['or_count3_vs_count4_scaled_max_error']=float(max(abs((data['Hsq-count3']['o']['cd']-data['Hbody']['o']['cd'])-.75*(data['Hsq']['o']['cd']-data['Hbody']['o']['cd']))))
summary['checks']['full_nozzle_coast_unchanged_max_error']=float(max(max(abs(data[n+'-nozzle']['r']['CD']-data[n]['r']['CD'])) for n in ['Hbody','Sbody']))
summary['checks']['nozzle_difference_H_vs_S_max_error']=float(max(abs((data['Hbody-nozzle']['r']['CD Power-Off']-data['Hbody-nozzle']['r']['CD Power-On'])-(data['Sbody-nozzle']['r']['CD Power-Off']-data['Sbody-nozzle']['r']['CD Power-On']))))
for n in ['Hsq','Ssq']:
 dif=data[n]['o']['fin_pressure']-data[n.replace('sq','bev')]['o']['fin_pressure'];m=data[n]['o']['mach'];sel=(abs(dif)<1e-10)&(m>1)
 summary['checks'][n+'_square_bevel_equal_Machs']=m[sel].tolist()
summary['max_Re_Cd_effect']=max(x['max_re_cd_correction_M_ge_0p1'] for x in audit)
(R/'analysis-results.json').write_text(json.dumps(summary,indent=2)+'\n')
plt.rcParams.update({'font.family':'serif','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18})
colors=['#08357E','#A04A00','#38761D','#7A0101']
def save(fig,n):
 fig.tight_layout();fig.savefig(R/'figures'/f'{n}.pdf');fig.savefig(R/'figures'/f'{n}.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(2,2,figsize=(10,7))
for ax,n in zip(ax.flat,['Hsq','Hbev','Ssq','Sbev']):
 d=data[n];m=d['o']['mach'];ax.plot(m,d['r']['CD'],color=colors[1],label='RASAero');ax.plot(m,d['o']['cd'],color=colors[0],label='MIT OR');ax.set(xlim=(.1,3),ylim=(0,None),title=n,xlabel='Mach',ylabel='$C_D$');ax.legend()
save(fig,'total-drag')
fig,ax=plt.subplots(1,2,figsize=(10,4))
for a,n in zip(ax,['Hbody','Sbody']):
 d=data[n];m=d['o']['mach'];a.plot(m,d['r']['CD'],color=colors[1],label='RASAero');a.plot(m,d['o']['cd'],color=colors[0],label='MIT OR');a.plot(m,d['nose_total'],color=colors[2],label='OR + trial nose term');a.set(xlim=(.1,3),ylim=(0,.65),title=n,xlabel='Mach',ylabel='$C_D$');a.legend(fontsize=8)
save(fig,'body-nose-trial')
fig,ax=plt.subplots(1,2,figsize=(10,4))
for a,geom in zip(ax,['H','S']):
 for profile,style in [('sq','-'),('bev','--')]:
  d=data[geom+profile];b=data[geom+'body'];m=d['o']['mach']
  for solver,col in [('r',colors[1]),('o',colors[0])]:
   key='CD' if solver=='r' else 'cd';a.plot(m,d[solver][key]-b[solver][key],style,color=col,label=('RAS ' if solver=='r' else 'OR ')+profile)
 a.set(xlim=(.1,3),title=geom+' fin addition',xlabel='Mach',ylabel='$C_D$(finned) - $C_D$(body)');a.legend(fontsize=8)
save(fig,'fin-increment')
print(json.dumps({k:v for k,v in summary.items() if k not in ['selected','audit']},indent=2))
