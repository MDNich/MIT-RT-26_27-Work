from pathlib import Path
import json,math,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_extended import load_all,exact_rough,SURFACE
R=Path(__file__).resolve().parents[1];D,missing=load_all('--partial' not in sys.argv);F=[]
COL={'OR':'#08357E','RAS':'#A04A00','extra':'#38761D','gray':'#777777'}
Q={'CD':('cd_wind','CD Power-Off',r'$C_D$'),'CD0':('cd0','CD',r'$C_{D,0}$'),'CA':('ca','CA Power-Off',r'$C_A$'),'CN':('cn','CN',r'$C_N$'),'CL':('cl','CL Power-Off (derived)',r'$C_L$'),'CP':('cp_m','CP','CP from tip [calibers]')}
def C(x,y,label,color,style='-'):return {'x':np.asarray(x).tolist(),'y':np.asarray(y).tolist(),'label':label,'color':color,'style':style}
def p(case,q='CD',alpha=0,title=None,lim=(.1,3),mode='pair'):
 if case not in D:raise KeyError(case)
 d=D[case];o=d['a'][alpha]['o'];r=d['a'][alpha]['r'];ok,rk,yl=Q[q];x=o['mach'];yo=o[ok];yr=r[rk]
 if q=='CP':yo=yo/d['diameter'];yr=yr*.0254/d['diameter']
 cs=[C(x,yo,'MIT OR',COL['OR'],'--'),C(x,yr,'RASAero',COL['RAS'])]
 if mode=='difference':cs=[C(x,yr-yo,'RAS - OR',COL['extra'])]
 return {'title':title or case,'xlabel':'Mach','ylabel':yl if mode=='pair' else r'$\Delta$ '+yl,'xlim':list(lim),'curves':cs}
def add(key,title,note,fn,group):
 try:ps=fn()
 except KeyError:return
 F.append({'id':key,'title':title,'note':note,'group':group,'panels':ps})
primary=['Hsq','Hbev','Ssq','Sbev'];names={'Hsq':'4 in, square','Hbev':'4 in, beveled','Ssq':'2.26 in, square','Sbev':'2.26 in, beveled'}
add('01-baseline-cd','Baseline zero-angle drag','All surfaces have zero roughness; all-turbulent flow is selected. Direct installed-engine curves, without correction.',lambda:[p(n,title=names[n]) for n in primary],'Overview')
add('02-transonic-cd','Transonic drag detail','The denser transonic comparison tests the location, width and magnitude of the drag rise, rather than matching one peak.',lambda:[p(n,title=names[n],lim=(.7,1.6)) for n in primary],'Overview')
add('03-baseline-residual','Drag residuals by Mach','Positive residual means RASAero predicts more drag. The sign and size vary with geometry and Mach.',lambda:[p(n,title=names[n],mode='difference') for n in primary],'Overview')
for ln in [6,12,18]:
 og={6:'Hbody-nose6',12:'Hbody',18:'Hbody-nose18'}[ln]
 add(f'04-noses-L{ln}',f'Nose shapes at L/D = {ln/4:g}',f'Finless 4 in body, overall length 60 in, nose length {ln} in. Body length changes to hold total length fixed.',lambda ln=ln,og=og:[p(n,title=t) for n,t in [(og,'Tangent ogive'),(f'Hbody-cone{ln}','Cone'),(f'Hbody-vk{ln}','Von Karman'),(f'Hbody-ellipsoid{ln}','Ellipsoid')]],'Nose geometry')
add('05-ogive-fineness','Tangent-ogive fineness sweep','Nose length changes at fixed overall length. L/D is nose length divided by body diameter.',lambda:[p(f'Hbody-{key}',title=f'Nose L/D = {ln/4:g}') for key,ln in [('nose6',6),('ogive8',8),('nose18',18),('ogive24',24)]],'Nose geometry')
def nose_increment():
 ps=[]
 for family,label in [('ogive','Tangent ogive'),('cone','Cone'),('vk','Von Karman'),('ellipsoid','Ellipsoid')]:
  a,b=('Hbody-nose6','Hbody-nose18') if family=='ogive' else (f'Hbody-{family}6',f'Hbody-{family}18');z=p(a,title=label);x=np.array(z['curves'][0]['x']);cs=[]
  for key,lab,col,st in [('o','MIT OR',COL['OR'],'--'),('r','RASAero',COL['RAS'],'-')]:
   k='cd0' if key=='o' else 'CD';cs.append(C(x,D[a]['a'][0][key][k]-D[b]['a'][0][key][k],lab,col,st))
  z.update(curves=cs,ylabel=r'$C_D$(6 in nose) - $C_D$(18 in nose)');ps.append(z)
 return ps
add('06-nose-shape-sensitivity','Sensitivity to shortening the nose','The finite difference contains both the nose-shape change and the associated body wetted-area change. Both solvers receive the same dimensions.',nose_increment,'Nose geometry')
add('07-body-length','Body length and fin count controls','The first three panels vary only finless-body length. The fourth checks the 3-fin count against the original 4-fin family.',lambda:[p(n,title=t) for n,t in [('Hbody-short','Body 24 in'),('Hbody','Body 48 in'),('Hbody-long','Body 96 in'),('Hsq-count3','Three square fins')]],'Body and fin controls')
for base,label in [('Hsq','Square'),('Hbev','Beveled')]:
 ns=[(base+'-nearzero',.001),(base+'-t0.03125',.03125),(base+'-thin' if base=='Hsq' else base+'-t0.0625',.0625),(base,.125),(base+'-thick',.25),(base+'-t0.375',.375)]
 add('08-'+base+'-thickness',label+' fin thickness sweep','Fixed planform and sweep. The 0.001 in case is an asymptotic diagnostic, not a representative hardware design.',lambda ns=ns:[p(n,title=f'Thickness {t:g} in') for n,t in ns],'Fin geometry')
add('09-bevel-length','Leading bevel length sweep','FX1 is measured parallel to the body. Maximum thickness is 0.125 in and the trailing edge remains blunt.',lambda:[p(n,title=f'Bevel {b:g} in') for n,b in [('Hbev-b0.0625',.0625),('Hbev-b0.125',.125),('Hbev',.25),('Hbev-gentle',.5),('Hbev-b1',1),('Hrounded',0)]],'Fin geometry')
if F and F[-1]['id']=='09-bevel-length':F[-1]['panels'][-1]['title']='Rounded profile control'
for base,label in [('Hsq','Square'),('Hbev','Beveled')]:
 add('10-'+base+'-sweep',label+' fin sweep','Root/tip chords, span and thickness are fixed. Leading-edge sweep distance varies without fin overhang past the body.',lambda base=base:[p(n,title=f'Sweep {s:g} in') for n,s in [(base+'-unswept',0),(base+'-sweep2',2),(base+'-sweep3',3),(base,4)]],'Fin geometry')
add('11-fin-span','Fin span and aspect ratio','Root/tip chords, sweep and thickness are fixed. Each solver uses the same exposed fin span.',lambda:[p(f'{b}-span{s}',title=f'{lab}; span {s:g} in') for b,lab in [('Hsq','Square'),('Hbev','Beveled')] for s in [1.625,4.875]],'Fin geometry')
add('12-tip-chord','Fin taper at fixed sweep','Sweep is 2 in for all four cases; compare with the corresponding 2 in-sweep baseline, whose tip chord is 2 in.',lambda:[p(f'{b}-tip{t}',title=f'{lab}; tip chord {t:g} in') for b,lab in [('Hsq','Square'),('Hbev','Beveled')] for t in [1,3]],'Fin geometry')
def net_fins():
 ps=[]
 for n in primary:
  b=n[0]+'body';z=p(n,title=names[n]);z['ylabel']=r'$\Delta C_{D,\mathrm{fins}}$'
  for i,key in enumerate(['o','r']):k='cd0' if key=='o' else 'CD';z['curves'][i]['y']=(D[n]['a'][0][key][k]-D[b]['a'][0][key][k]).tolist()
  ps.append(z)
 return ps
add('13-fin-increments','Net drag added by fins','Finned-minus-finless subtraction includes fin/body interference and changes in exposed body surface. It is not an isolated RASAero fin-pressure coefficient.',net_fins,'Fin geometry')
add('14-profile-limits','Thin-profile limits and rounded control','These limits test whether the models approach a consistent finite-planform, vanishing-thickness behavior.',lambda:[p(n,title=t) for n,t in [('Hsq-nearzero','Square, t = 0.001 in'),('Hbev-nearzero','Beveled, t = 0.001 in'),('Hrounded','Rounded, t = 0.125 in'),('Hbev-b1','Gentle bevel, b = 1 in')]],'Fin geometry')
add('15-geometric-scale','Geometric scale and Reynolds number','Every external length is scaled together; reference area follows diameter squared. At common Mach and atmosphere, dimensionless geometry is unchanged and Reynolds number varies.',lambda:[p(f'{b}-scale{s}',title=f'{b}; scale {s:g}') for b in ['Hbody','Hsq','Hbev'] for s in [.5,2]],'Friction and Reynolds number')
def length_local():
 ps=[p('Hsq',title='Body 48 in: total drag'),p('Hsq-long',title='Body 96 in: total drag')]
 for n,b,lab in [('Hsq','Hbody','Body 48 in: fin addition'),('Hsq-long','Hbody-long','Body 96 in: fin addition')]:
  o=D[n]['a'][0]['o'];r=D[n]['a'][0]['r'];z=p(n,title=lab);z['ylabel']=r'$\Delta C_{D,\mathrm{fins}}$'
  z['curves'][0]['y']=(o['cd0']-D[b]['a'][0]['o']['cd0']).tolist();z['curves'][1]['y']=(r['CD']-D[b]['a'][0]['r']['CD']).tolist();ps.append(z)
 return ps
add('16-fin-length-invariance','Fin drag versus upstream body length','Only the cylindrical body length changes. Net fin additions expose the influence of the skin-friction reference length.',length_local,'Friction and Reynolds number')
for base in ['Hbody','Hsq','Hbev']:
 def rough_panels(base=base):
  ps=[]
  for suf in ['polished','paint','rough','galv']:
   n=base+'-'+suf;k=SURFACE[D[n]['surface']];z=p(n,title=f'RAS roughness {k*1e6:g} micrometers');o=D[base]['a'][0]['o'];z['curves'][0]['label']='OR native nearest finish';z['curves'][0]['color']=COL['gray'];z['curves'].append(C(o['mach'],exact_rough(o,k,D[base]['length']),'OR exact roughness (reconstructed)',COL['OR'],'--'));ps.append(z)
  return ps
 add('17-roughness-'+base,'Physical roughness: '+base,'Gray: native OR nearest available finish (2, 5, 20, 150 micrometers respectively). Blue: native OR correlation reconstructed at the exact RAS roughness, verified against all native finish curves; no OR application changes.',rough_panels,'Friction and Reynolds number')
def rough_response():
 ps=[]
 for m in [.3,.8,1.5,3]:
  cs=[];ix=round(m*100)-1
  for base,col in [('Hbody',COL['OR']),('Hsq',COL['RAS']),('Hbev',COL['extra'])]:
   x=[];yo=[];yr=[]
   for suf in ['polished','paint','rough','galv']:
    n=base+'-'+suf;k=SURFACE[D[n]['surface']];x.append(k*1e6);yo.append(exact_rough(D[base]['a'][0]['o'],k,D[base]['length'])[ix]-D[base]['a'][0]['o']['cd0'][ix]);yr.append(D[n]['a'][0]['r']['CD'][ix]-D[base]['a'][0]['r']['CD'][ix])
   cs.extend([C(x,yo,base+' OR exact k',col,'--'),C(x,yr,base+' RAS',col)])
  ps.append({'title':f'Mach {m:g}','xlabel':'Roughness [micrometers]','ylabel':r'$C_D(k)-C_D(0)$','xscale':'log','curves':cs})
 return ps
add('18-roughness-increment','Roughness-induced drag at fixed Mach','Numerical physical roughness is matched in the reconstructed OR correlation. Pressure and base terms retain their native OR values.',rough_response,'Friction and Reynolds number')
add('19-transition-finned','Laminar-to-turbulent option: finned rockets','OR perfectFinish=true and RAS All Turbulent Flow=false. These settings enable the respective transition models; their transition equations are not assumed identical.',lambda:[p(n+'-transition',title=names[n]) for n in primary],'Flow settings')
def flow_diffs():
 ps=[]
 for base in ['Hbody','Sbody','Hsq','Hbev']:
  n=base+'-transition';z=p(n,title=base);z['ylabel']=r'$C_D$(transition) - $C_D$(turbulent)'
  for i,k in enumerate(['o','r']):q='cd0' if k=='o' else 'CD';z['curves'][i]['y']=(D[n]['a'][0][k][q]-D[base]['a'][0][k][q]).tolist()
  ps.append(z)
 return ps
add('20-transition-increment','Sensitivity to flow-transition treatment','Subtracting the fully turbulent baseline separates the change due to each program\'s flow option from the baseline pressure-drag disagreement.',flow_diffs,'Flow settings')
for base in ['Hbody','Hsq']:
 def nozzle_panels(base=base):
  ps=[]
  for dia in [1,2,3,4]:
   n=base+'-nozzle'+str(dia) if not(base=='Hbody' and dia==4) else 'Hbody-nozzle';z=p(n,title=f'Nozzle / body diameter = {dia/4:g}');z['curves'][0]['label']='OR (no nozzle model)';z['curves'][1]['label']='RAS power-off';r=D[n]['a'][0]['r'];z['curves'].append(C(r['Mach'],r['CD Power-On'],'RAS power-on',COL['extra']));ps.append(z)
  return ps
 add('21-nozzle-'+base,'Nozzle-area sensitivity: '+base,'Aero-only probes. OR has no corresponding nozzle-area correction here; its baseline is shown to reveal the missing dependency, not as a matched powered-flow prediction.',nozzle_panels,'Base and powered drag')
def nozzle_area():
 ps=[]
 for m in [.3,.8,1.5,3]:
  cs=[];i=round(m*100)-1;x=np.array([0,1,4,9,16])/16
  for base,col in [('Hbody',COL['OR']),('Hsq',COL['RAS'])]:
   vals=[0]
   for dia in [1,2,3,4]:
    n='Hbody-nozzle' if base=='Hbody' and dia==4 else base+'-nozzle'+str(dia);r=D[n]['a'][0]['r'];vals.append(r['CD Power-Off'][i]-r['CD Power-On'][i])
   cs.append(C(x,vals,base+' RAS',col));cs.append(C(x,x*vals[-1],base+' area-proportional line',col,'--'))
  ps.append({'title':f'Mach {m:g}','xlabel':'Nozzle area / body reference area','ylabel':r'$C_{D,off}-C_{D,on}$','curves':cs,'xlim':[0,1]})
 return ps
add('22-nozzle-area-law','Test of nozzle-area scaling','The dashed line uses the observed full-area value. It tests area proportionality; it does not identify the absolute body-base coefficient.',nozzle_area,'Base and powered drag')
for q in ['CD','CA','CN','CL']:
 def alpha_panels(q=q):
  ps=[]
  for base in primary:
   z=p(base,q,title=names[base]);z['curves']=[]
   for alpha,col in [(0,COL['OR']),(2,COL['extra']),(4,COL['RAS'])]:
    zz=p(base,q,alpha)
    for c in zz['curves']:c['color']=col;c['label']+=f', {alpha} deg';z['curves'].append(c)
   ps.append(z)
  return ps
 add('23-alpha-'+q,{'CD':'Wind-axis drag','CA':'Axial force','CN':'Normal force','CL':'Wind-axis lift'}[q]+' at 0, 2 and 4 degrees','Body-axis forces are compared directly. Wind-axis drag/lift use CD=CA cos(alpha)+CN sin(alpha), CL=CN cos(alpha)-CA sin(alpha). RAS lift is reconstructed for power-off; its raw CL column corresponds to power-on when nozzle area is nonzero.',alpha_panels,'Angle of attack and stability')
for alpha in [0,4]:add('24-cp-'+str(alpha),f'Center of pressure at {alpha} degrees','CP is measured from the nose tip in body diameters; this is not a stability margin. OR warns of limitations of its body-force treatment above Mach 1.1.',lambda alpha=alpha:[p(n,'CP',alpha,title=names[n]) for n in primary],'Angle of attack and stability')
def cna():
 ps=[]
 for n in primary:
  z=p(n,'CN',4,title=names[n]);z['ylabel']=r'$C_N(4^\circ)/(4\pi/180)$ [rad$^{-1}$]'
  for c in z['curves']:c['y']=(np.array(c['y'])/np.deg2rad(4)).tolist()
  ps.append(z)
 return ps
add('25-cna-secant','Normal-force slope over 0 to 4 degrees','Both plotted slopes use the same 0-to-4-degree secant definition; neither is assumed to be the infinitesimal derivative in nonlinear flow.',cna,'Angle of attack and stability')
for q in ['CN','CP','CD']:
 def rogers(q=q):
  ps=[]
  for n in primary:
   z=p(n,q,4,title=names[n]);z['curves'][1]['label']='RAS default';c=p(n+'-rogers',q,4)['curves'][1];c['label']='RAS Rogers modified';c['color']=COL['extra'];z['curves'].append(c);ps.append(z)
  return ps
 add('26-rogers-'+q,'Rogers Modified Barrowman: '+q+' at 4 degrees','Default and modified RAS settings share geometry and drag-flow inputs. This isolates the normal-force/body-interference option, compared with unmodified MIT OR.',rogers,'Angle of attack and stability')

def rough_net():
 ps=[]
 for suf in ['polished','paint','rough','galv']:
  cs=[]
  for base,col in [('Hsq',COL['OR']),('Hbev',COL['RAS'])]:
   n=base+'-'+suf;k=SURFACE[D[n]['surface']];o=D[base]['a'][0]['o'];ob=D['Hbody']['a'][0]['o'];r=D[n]['a'][0]['r'];rb=D['Hbody-'+suf]['a'][0]['r'];m=o['mach']
   yo=(exact_rough(o,k,D[base]['length'])-o['cd0'])-(exact_rough(ob,k,D['Hbody']['length'])-ob['cd0'])
   yr=(r['CD']-D[base]['a'][0]['r']['CD'])-(rb['CD']-D['Hbody']['a'][0]['r']['CD'])
   cs.extend([C(m,yo,base+' OR exact k',col,'--'),C(m,yr,base+' RAS',col)])
  ps.append({'title':f'Roughness {k*1e6:g} micrometers','xlabel':'Mach','ylabel':r'$\Delta C_{D,\mathrm{fins}}(k)-\Delta C_{D,\mathrm{fins}}(0)$','xlim':[.1,3],'curves':cs})
 return ps
add('27-fin-roughness-response','Isolated fin response to physical roughness','Two subtractions remove smooth baseline drag and the finless-body roughness response. RASAero square-fin curves remain at zero to floating-point precision; beveled fins respond. OR exact-roughness curves are reconstructed from its native correlation.',rough_net,'Friction and Reynolds number')
def flow_net():
 ps=[]
 for base in primary:
  body=base[0]+'body';z=p(base,title=names[base]);z['ylabel']=r'$\Delta C_{D,\mathrm{fins}}$(transition - turbulent)'
  for i,k in enumerate(['o','r']):
   q='cd0' if k=='o' else 'CD';v=(D[base+'-transition']['a'][0][k][q]-D[base]['a'][0][k][q])-(D[body+'-transition']['a'][0][k][q]-D[body]['a'][0][k][q]);z['curves'][i]['y']=v.tolist()
  ps.append(z)
 return ps
add('28-fin-transition-response','Isolated fin response to flow transition','Subtract the body-only response to the flow option from the finned-rocket response. This isolates the net fin dependency without labeling it as a proprietary RASAero internal pressure or friction term.',flow_net,'Flow settings')
add('29-nose-transonic-detail','Nose-shape transonic detail at L/D = 3','Geometry and zero roughness are matched. Different onset, peak Mach and width of the transonic rise remain even in shapes that agree closely at Mach 2.',lambda:[p(n,title=t,lim=(.7,1.6)) for n,t in [('Hbody','Tangent ogive'),('Hbody-cone12','Cone'),('Hbody-vk12','Von Karman'),('Hbody-ellipsoid12','Ellipsoid')]],'Nose geometry')
# Group the dynamically added diagnostic sheets with their corresponding mechanism.
order=['Overview','Nose geometry','Body and fin controls','Fin geometry','Friction and Reynolds number','Flow settings','Base and powered drag','Angle of attack and stability']
F.sort(key=lambda f:order.index(f['group']))

plt.rcParams.update({'font.family':'serif','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.2,'svg.fonttype':'none'})
for f in F:
 rows=math.ceil(len(f['panels'])/2);fig,axs=plt.subplots(rows,2,figsize=(10.4,rows*3.7+1.1),squeeze=False);legend={}
 for ax,z in zip(axs.flat,f['panels']):
  for c in z['curves']:
   line,=ax.plot(c['x'],c['y'],color=c['color'],linestyle=c['style'],lw=1.65,label=c['label']);legend.setdefault(c['label'],line)
  ax.set(title=z['title'],xlabel=z['xlabel'],ylabel=z['ylabel']);ax.tick_params(labelsize=9)
  if 'xlim' in z:ax.set_xlim(z['xlim'])
  if 'xscale' in z:ax.set_xscale(z['xscale'])
  if any(min(c['y'])<0<max(c['y']) for c in z['curves']):ax.axhline(0,color='.6',lw=.5,zorder=0)
 for ax in axs.flat[len(f['panels']):]:ax.axis('off')
 fig.suptitle(f['title'],fontsize=14,y=.995);fig.legend(list(legend.values()),list(legend),loc='upper center',bbox_to_anchor=(.5,.963),ncol=min(3,len(legend)),frameon=False,fontsize=9)
 fig.tight_layout(rect=(0,.02,1,.90 if len(legend)>3 else .92));fig.savefig(R/'figures'/(f['id']+'.png'),dpi=160);fig.savefig(R/'figures'/(f['id']+'.svg'));plt.close(fig)
(R/'figure-data.json').write_text(json.dumps(F,separators=(',',':'))+'\n')
print('FIGURES',len(F),'PANELS',sum(len(f['panels']) for f in F),'MISSING_CASES',len(missing))
