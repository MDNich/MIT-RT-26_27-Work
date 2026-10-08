from pull_paths import *
import sys,json,hashlib,re
base,case=sys.argv[1:3];mu=float(sys.argv[3]) if len(sys.argv)>3 else .2
fkn=float(sys.argv[4]) if len(sys.argv)>4 else .1
alg=int(sys.argv[5]) if len(sys.argv)>5 else 0
D=S/'runtime'/case;D.mkdir(exist_ok=True);B=S/'runtime'/base
m=json.loads((B/'mesh.json').read_text());cfg=json.loads((B/'config.json').read_text());n={int(k):v for k,v in m['nodes'].items()};pilot=m['pilot'];nnew=max(n);nextras=0;eln=cfg['shell_elements']+cfg['rigid_links']
lines=[]
for l in (B/'model.inp').read_text().splitlines():
 if l=='CHECK':break
 if l.startswith('D,'):continue
 lines.append(l)
lines+=['ET,3,CONTA174',f'KEYOPT,3,2,{alg}','KEYOPT,3,10,2','KEYOPT,3,11,1','KEYOPT,3,12,0','ET,4,TARGE170','KEYOPT,4,2,1',f'MP,MU,2,{mu}']
targets=[];contids=[];bottompilots=[]
for si,cy in enumerate([17.906999,102.907004]):
 flat=[(i+1,ids) for i,ids in enumerate(m['elements']) if m['region'][i] in ['flat','clamp'] and abs(sum(n[k][1] for k in ids)/4-cy)<8]
 ann=[(i,ids) for i,ids in flat if m['region'][i-1]=='clamp']
 for side in [-1,1]:
  rid=si*2+(1 if side==-1 else 2)
  lines += [f'R,{rid},,,{fkn},.01,,.2',f'REAL,{rid}','MAT,2','TYPE,3']
  for eid,ids in flat:
   eln+=1;contids.append(eln);cc=ids if side==1 else ids[::-1];lines += [f'EN,{eln},'+','.join(map(str,cc))]
  maps={}
  for nid in sorted({k for i,ids in ann for k in ids}):
   nnew+=1;x,y,z=n[nid];maps[nid]=nnew
   lines += [f'N,{nnew},{x:.10g},{y:.10g},{z+side*.075:.10g}']
  nnew+=1;pn=nnew;targets.append(pn)
  lines += [f'N,{pn},10.81234894,{cy},{-1.197679+side*.075}','TYPE,4','TSHAP,PILO',f'E,{pn}'];eln+=1
  lines+=['TSHAP,QUAD']
  for eid,ids in ann:
   cc=ids[::-1] if side==1 else ids;eln+=1;lines+=[f'EN,{eln},'+','.join(str(maps[k]) for k in cc)]
  lines += [f'D,{pn},ALL,0']
  if side==-1:lines += [f'DDELE,{pn},UZ'];bottompilots.append(pn)
lines += [f'D,{pilot},ALL,0','ESEL,S,TYPE,,3','CM,CLAMP_CONTACT,ELEM','ALLSEL,ALL','/SOLU','NLGEOM,ON','FINISH','/PREP7','CHECK','*GET,NN,NODE,0,COUNT','*GET,NE,ELEM,0,COUNT','*CFOPEN,inventory,txt','*VWRITE,NN,NE',"(2F12.0)",'*CFCLOS','SAVE,model,db','FINISH']
model='\n'.join(lines)+'\n';(D/'model.inp').write_text(model);(D/'preflight.dat').write_text(model+'/EXIT,NOSAVE\n')
src=(B/'run.dat').read_text();post=src[src.index('/POST1'):]
post=re.sub(r'\*CFOPEN,balance,csv.*?\*CFCLOS', '', post, flags=re.S)
# fuller per-set top/bottom shell extrema and clamp sliding/force audit
post=post.replace('max_seqv_MPa,max_eppl','max_seqv_MPa,max_eppl')
# avoid APDL format >80 chars by keep one history per observable group
post=post.replace('ALLSEL,ALL\n*ENDDO\n*CFCLOS\nSET,LAST', 'ALLSEL,ALL\n*ENDDO\n*CFCLOS\nSET,LAST',1)
extra='''/POST1
SET,LAST
*GET,NSET,ACTIVE,0,SET,NSET
*CFOPEN,contact_history,csv
*VWRITE
('set,time,washer1_uz,washer2_uz,washer1_RFz,washer2_RFz,max_slide,max_pressure')
*DO,II,1,NSET
SET,,,,,,,II
*GET,TT,ACTIVE,0,SET,TIME
*GET,W1U,NODE,%d,U,Z
*GET,W2U,NODE,%d,U,Z
W1F=0
*GET,W1F,NODE,%d,RF,FZ
W2F=0
*GET,W2F,NODE,%d,RF,FZ
CMSEL,S,CLAMP_CONTACT
ETABLE,CSL,CONT,SLIDE
ETABLE,CPR,CONT,PRES
ESORT,ETAB,CSL,0,0
*GET,CSMAX,SORT,0,MAX
ESORT,ETAB,CPR,0,0
*GET,CPMAX,SORT,0,MAX
*VWRITE,II,TT,W1U,W2U,W1F,W2F,CSMAX,CPMAX
(F8.0,7(',',E19.11))
ALLSEL,ALL
*ENDDO
*CFCLOS
'''%tuple(bottompilots*2)
bal=['*CFOPEN,balance,csv','*VWRITE',"('set,time,force_x_N,force_y_N,force_z_N')",'*DO,II,1,NSET','SET,,,,,,,II','*GET,TT,ACTIVE,0,SET,TIME','SX=0','SY=0','SZ=0']
for pn in targets+[pilot]:
 for ax in 'XYZ':bal += ['RR=0',f'*GET,RR,NODE,{pn},RF,F{ax}',f'S{ax}=S{ax}+RR']
bal+=['*IF,TT,LE,1,THEN','SZ=SZ+1500*TT','*ENDIF','*VWRITE,II,TT,SX,SY,SZ',"(F8.0,4(',',E19.11))",'*ENDDO','*CFCLOS']
post=post.replace('FINISH\n/EXIT,NOSAVE',extra+'\n'.join(bal)+'\nFINISH\n/EXIT,NOSAVE')
sol=['/SOLU','ANTYPE,STATIC','NLGEOM,ON','NROPT,UNSYM,,OFF','EQSLV,SPARSE','AUTOTS,ON','NEQIT,60','LNSRCH,ON','KBC,0','OUTRES,ALL,ALL','RESCONTROL,DEFINE,ALL,LAST,2','TIME,1','NSUBST,20,1000,5']
sol += [f'F,{pn},FZ,750' for pn in bottompilots]+['SOLVE']
sol+=['*CFOPEN,preload_lock,csv',"*VWRITE", "('pilot,uz_mm,applied_preload_N')"]
for pn in bottompilots:
 sol += [f'*GET,LOCKUZ,NODE,{pn},U,Z',f'FDELE,{pn},FZ',f'D,{pn},UZ,LOCKUZ',f'*VWRITE,{pn},LOCKUZ,750',"(F9.0,2(',',E19.11))"]
sol+=['*CFCLOS']+[f'DDELE,{pilot},{dof}' for dof in ['UY','UZ','ROTX','ROTY','ROTZ']]
sol+=['CNVTOL,F,,1E-5,,1','CNVTOL,M,,1E-4,,1','TIME,2','NSUBST,100,4000,20',f'D,{pilot},UX,{cfg["sign"]*cfg["displacement_mm"]}','SOLVE','FINISH','SAVE,solved,db']
(D/'run.dat').write_text(model+'\n'.join(sol)+'\n'+post)
cfg.update(case=case,fkn=fkn,contact_algorithm=alg,clamp='Two rigid annular platens per strip with Coulomb friction; bottom platen 750 N then locked Z position',mu=mu,nodes=nnew,contact_target_elements=eln-cfg['shell_elements']-cfg['rigid_links'],bottom_pilots=bottompilots,target_pilots=targets,expected_total_elements=eln)
(D/'config.json').write_text(json.dumps(cfg,indent=2));(D/'mesh.json').write_text(json.dumps(m))
(D/'input_sha256.json').write_text(json.dumps({f:hashlib.sha256((D/f).read_bytes()).hexdigest() for f in ['model.inp','preflight.dat','run.dat','mesh.json','config.json']},indent=2))
print(cfg)
