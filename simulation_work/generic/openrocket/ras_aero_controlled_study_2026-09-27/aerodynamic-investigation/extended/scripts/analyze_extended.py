from pathlib import Path
import csv,json,math,xml.etree.ElementTree as E
import numpy as np
R=Path(__file__).resolve().parents[1]
SURFACE={'Smooth (Zero Roughness)':0.,'Polished':1.27e-6,'Smooth Paint':6.35e-6,'Rough Camouflage Paint':30.48e-6,'Galvanized Metal':152.4e-6}
def read(p):
 a=list(csv.DictReader(p.open()));return {k:np.array([float(x[k]) for x in a]) for k in a[0]}
def cf(re,m):
 f=np.where(re<1e4,.0148,(1.5*np.log(np.maximum(re,1))-5.6)**-2);c1=1-.1*m*m;c2=(1+.15*m*m)**-.58
 return f*np.where(m<.9,c1,np.where(m>1.1,c2,(c2*(m-.9)+c1*(1.1-m))/.2))
def roughfactor(m):return np.where(m<.9,1-.1*m*m,np.where(m>1.1,1/(1+.18*m*m),((1/(1+.18*1.1**2))*(m-.9)+(1-.1*.9**2)*(1.1-m))/.2))
def exact_rough(o,k,L):
 c0=cf(o['re_length'],o['mach']);ck=np.maximum(c0,.032*(k/L)**.2*roughfactor(o['mach']))
 return o['cd0']+o['friction']*(ck/c0-1)
def load_all(require=True):
 cases=json.loads((R/'cases.json').read_text());data={};missing=[]
 for c in cases:
  n=c['name'];rp=R/'rasaero'/f'{n}.csv'
  if not rp.exists():missing.append(n);continue
  o=read(R/'openrocket'/f'{n}.csv');raw=read(rp);z=E.parse(R/'models'/f'{n}.CDX1').getroot();nose=z.find('RocketDesign/NoseCone');b=z.find('RocketDesign/BodyTube');dia=float(nose.findtext('Diameter'))*.0254;ln=float(nose.findtext('Length'))*.0254;L=ln+float(b.findtext('Length'))*.0254
  slices={}
  for alpha in [0,2,4]:
   rr={k:v[raw['Alpha']==alpha] for k,v in raw.items()};oo={k:v[o['alpha_deg']==alpha] for k,v in o.items()};assert np.all(np.diff(rr['Mach'])>0)
   ri={k:np.interp(oo['mach'],rr['Mach'],v) for k,v in rr.items()};aa=np.deg2rad(alpha)
   ri['CL Power-Off (derived)']=ri['CN']*np.cos(aa)-ri['CA Power-Off']*np.sin(aa)
   ri['CL Power-On (derived)']=ri['CN']*np.cos(aa)-ri['CA Power-On']*np.sin(aa)
   slices[alpha]={'o':oo,'r':ri}
  data[n]={'a':slices,'c':c,'diameter':dia,'length':L,'nose_length':ln,'surface':z.findtext('RocketDesign/Surface'),'flow':z.findtext('RocketDesign/Turbulence'),'shape':nose.findtext('Shape')}
 if require and missing:raise RuntimeError('Missing RAS exports: '+', '.join(missing))
 return data,missing

def analyze(require=True):
 d,missing=load_all(require);audit=[];metrics=[];rows=[]
 for n,v in d.items():
  for alpha,t in v['a'].items():
   o,r=t['o'],t['r'];m=o['mach'];aoa=np.deg2rad(alpha);errCD=np.max(abs(r['CD Power-Off']-(r['CA Power-Off']*np.cos(aoa)+r['CN']*np.sin(aoa))));errCL=np.max(abs(r['CL']-(r['CN']*np.cos(aoa)-r['CA Power-On']*np.sin(aoa))));assert errCD<1e-9 and errCL<1e-9
   audit.append({'case':n,'alpha':alpha,'points':len(m),'ras_axis_cd_max_error':float(errCD),'ras_axis_cl_max_error':float(errCL)})
   for band,sel in [('subsonic',(m>=.1)&(m<=.8)),('transonic',(m>=.81)&(m<=1.3)),('supersonic',(m>=1.31)&(m<=3))]:
    for coeff,ok,rk,f in [('CD','cd_wind','CD Power-Off',1),('CA','ca','CA Power-Off',1),('CN','cn','CN',1),('CL','cl','CL Power-Off (derived)',1),('CP_m','cp_m','CP',.0254)]:
     y=r[rk]*f;x=o[ok];delta=y-x;metrics.append({'case':n,'alpha_deg':alpha,'band':band,'coefficient':coeff,'mean_RAS_minus_OR':float(np.mean(delta[sel])),'mean_absolute_error':float(np.mean(abs(delta[sel]))),'max_absolute_error':float(max(abs(delta[sel]))),'RMSE':float(np.sqrt(np.mean(delta[sel]**2)))})
   roughkey=SURFACE[v['surface']]
   if roughkey>0:
    smooth=d[v['c']['parent']]['a'][alpha]['o'];cd_exact=exact_rough(smooth,roughkey,v['length']);ca_exact=smooth['ca']*cd_exact/smooth['cd0'];wind_exact=ca_exact*np.cos(aoa)+smooth['cn']*np.sin(aoa)
   else:cd_exact=o['cd0'];wind_exact=o['cd_wind']
   for i in range(len(m)):
    rows.append({'case':n,'alpha_deg':alpha,'mach':m[i],'or_cd0':o['cd0'][i],'or_cd0_exact_ras_roughness':cd_exact[i],'or_cd_wind_exact_ras_roughness':wind_exact[i],'ras_cd0':r['CD'][i],'or_cd_wind':o['cd_wind'][i],'ras_cd_wind':r['CD Power-Off'][i],'or_ca':o['ca'][i],'ras_ca':r['CA Power-Off'][i],'or_cn':o['cn'][i],'ras_cn':r['CN'][i],'or_cl':o['cl'][i],'ras_cl':r['CL Power-Off (derived)'][i],'ras_cl_export_poweron':r['CL'][i],'or_cp_m':o['cp_m'][i],'ras_cp_m':r['CP'][i]*.0254,'or_re':o['re_length'][i],'ras_re':r['Reynolds Number'][i],'or_roughness_m':o['roughness_m'][i],'ras_roughness_m':SURFACE[v['surface']]})
 for file,rs in [('matched-coefficients.csv',rows),('error-metrics.csv',metrics),('axis-audit.csv',audit)]:
  with (R/file).open('w') as f:w=csv.DictWriter(f,rs[0]);w.writeheader();w.writerows(rs)
 # Verify the independent native-OR roughness reconstruction against all retained native finishes.
 rougherrs=[]
 for n in ['Hbody','Hsq','Hbev']:
  smooth=d[n]['a'][0]['o'];L=d[n]['length']
  for p in (R/'openrocket').glob(n+'-ORfinish-*.csv'):
   raw=read(p);o={k:v[raw['alpha_deg']==0] for k,v in raw.items()};q=exact_rough(smooth,o['roughness_m'][0],L);rougherrs.append({'case':p.stem,'roughness_m':o['roughness_m'][0],'max_abs_error':float(max(abs(q-o['cd0'])))})
 assert max(x['max_abs_error'] for x in rougherrs)<1e-8
 out={'cases':len(d),'missing':missing,'matched_points':len(rows),'alpha_degrees':[0,2,4],'mach_min':.01,'mach_max':3,'native_OR_roughness_verification':rougherrs,'findings':{}}
 def val(n,m=.3,a=0,key='cd0',solver='o'):return float(d[n]['a'][a][solver][key][round(m*100)-1])
 # Selected independent shape controls isolate the tangent-ogive anomaly.
 out['findings']['nose_M2']=[{'shape':n,'or_cd':val(n,2),'ras_cd':val(n,2,key='CD',solver='r'),'ras_minus_or':val(n,2,key='CD',solver='r')-val(n,2)} for n in ['Hbody','Hbody-cone12','Hbody-vk12','Hbody-ellipsoid12'] if n in d]
 out['findings']['source_roughness_mapping']=[{'surface':k,'ras_um':v*1e6} for k,v in SURFACE.items()]
 # Zero-Mach grid does not include Mach=0; aerodynamic slopes are evaluated at common nonzero Mach.
 for fam in ['Hsq','Hbev','Ssq','Sbev']:
  n=fam+'-rogers'
  if n in d:out['findings'][n]={'CN4_M03_OR':val(fam,.3,4,'cn'),'CN4_M03_RAS_default':val(fam,.3,4,'CN','r'),'CN4_M03_RAS_modified':val(n,.3,4,'CN','r'),'CP4_M03_OR_in':val(fam,.3,4,'cp_m')/.0254,'CP4_M03_RAS_default_in':val(fam,.3,4,'CP','r'),'CP4_M03_RAS_modified_in':val(n,.3,4,'CP','r')}
 # Nozzle-area scaling is tested against the observed full-area difference, never assumed to be all base drag.
 for fam,full in [('Hbody','Hbody-nozzle'),('Hsq','Hsq-nozzle4')]:
  if full not in d or fam+'-nozzle3' not in d:continue
  f=d[full]['a'][0]['r'];df=f['CD Power-Off']-f['CD Power-On'];es=[]
  for dia in [1,2,3]:
   rr=d[fam+'-nozzle'+str(dia)]['a'][0]['r'];es.append(float(max(abs((rr['CD Power-Off']-rr['CD Power-On'])-df*(dia/4)**2))))
  out['findings'][fam+'_nozzle_area_scaling_max_error']=max(es)
 (R/'analysis-summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
 return d
if __name__=='__main__':
 import sys
 analyze('--partial' not in sys.argv)
