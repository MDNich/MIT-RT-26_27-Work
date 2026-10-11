from pull_paths import *
import numpy as np,json,hashlib,math,sys
case=sys.argv[1] if len(sys.argv)>1 else 'proof'
fac=int(sys.argv[2]) if len(sys.argv)>2 else 1
sy=float(sys.argv[3]) if len(sys.argv)>3 else 148
sign=int(sys.argv[4]) if len(sys.argv)>4 else 1
umax=float(sys.argv[5]) if len(sys.argv)>5 else .1
et=float(sys.argv[6]) if len(sys.argv)>6 else 1000
out=S/'runtime'/case;out.mkdir(exist_ok=True)
assert not (out/'run.out').exists()
# N-mm-MPa model. Read-only CAD-based localized model. No crack/damage law.
cfg=dict(case=case,mesh_factor=fac,yield_MPa=sy,tangent_MPa=et,E_MPa=205000,nu=.29,thickness_mm=.15,displacement_mm=umax,sign=sign,battery_geometry_id=20157,nickel_geometry_ids=[20091,20348],clamp='perfect grip at annulus; no explicit pretension state',preload_N=750,washer_outer_radius_mm=5.5626,hole_radius_mm=2.704,degree='battery translations except UX and all rotations free; rigid end attachments')
N={};E=[];region=[];clamp=[];attach=[];lookup={};stripnodes=[]
def node(p):
 k=tuple(round(float(x),9) for x in p)
 if k not in lookup:lookup[k]=len(N)+1;N[lookup[k]]=k
 return lookup[k]
def elem(ids,r):E.append(ids);region.append(r)
# A square radial outer boundary, 8 sectors, exactly matching the vertical leg.
nangle=64*fac; ninner=6*fac;nouter=6*fac;nz=24*fac
cx=10.81234894; ztop=-1.197679;zb=-11.822674;xb=10.803671
for si,(cy,sg) in enumerate([(17.906999,-1),(102.907004,1)]):
 grid=[]
 for j in range(ninner+nouter+1):
  ring=[]
  for i in range(nangle):
   corners=[(-7.5,-7.425),(7.5,-7.425),(7.5,7.5),(-7.5,7.5)]
   side=i//(nangle//4);frac=(i%(nangle//4))/float(nangle//4)
   p0,p1=corners[side],corners[(side+1)%4]
   ox=p0[0]*(1-frac)+p1[0]*frac;oy=p0[1]*(1-frac)+p1[1]*frac
   th=math.atan2(oy,ox);a,b=math.cos(th),math.sin(th)
   # local y negative faces the battery, outer half-width 7.5 CAD, 7.425 midsurface bend
   hx=7.5;hy=7.425 if b<0 else 7.5
   rout=min(hx/(abs(a)+1e-30),hy/(abs(b)+1e-30))
   rad=2.704+(5.5626-2.704)*j/ninner if j<=ninner else 5.5626+(rout-5.5626)*(j-ninner)/nouter
   nd=node((cx+rad*a,cy+sg*rad*b,ztop));ring.append(nd)
   if j<=ninner:clamp.append(nd)
  grid.append(ring)
 for j in range(ninner+nouter):
  for i in range(nangle):
   ip=(i+1)%nangle;ids=[grid[j][i],grid[j+1][i],grid[j+1][ip],grid[j][ip]]
   if sg<0:ids=ids[::-1]
   elem(ids,'clamp' if j<ninner else 'flat')
 boundary=sorted([n for n in grid[-1] if abs((N[n][1]-cy)*sg+7.425)<1e-5],key=lambda n:N[n][0])
 assert len(boundary)>=nangle//4
 # coordinates at outer corners depend on angle; fixed bend plane wins within tolerance
 vg=[boundary]
 for iz in range(1,nz+1):
  row=[]
  for nd in boundary:
   x,y,z=N[nd];row.append(node((x,y,z-(ztop+18.622679)*iz/nz)))
  vg.append(row)
 for iz in range(nz):
  for ix in range(len(boundary)-1):
   ids=[vg[iz][ix],vg[iz+1][ix],vg[iz+1][ix+1],vg[iz][ix+1]]
   if sg<0:ids=ids[::-1]
   elem(ids,'vertical')
 for row in vg:
  for nd in row:
   x,y,z=N[nd]
   if (x-xb)**2+(z-zb)**2<=10.7**2:attach.append(nd)
# validation planar convex quads, no duplicate nodes
areas=[];aspects=[]
for ids in E:
 p=np.array([N[n] for n in ids]);cross=np.cross(p[1]-p[0],p[2]-p[0])+np.cross(p[2]-p[0],p[3]-p[0]);areas.append(np.linalg.norm(cross)/2)
 edge=np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1);aspects.append(float(max(edge)/min(edge)))
assert min(areas)>1e-8 and not set(clamp)&set(attach)
pilot=node((xb,60.407,zb));nphys=pilot-1
lines=['/BATCH','/PREP7','/UNITS,MPA','ET,1,SHELL181','KEYOPT,1,3,2','KEYOPT,1,8,2','SECTYPE,1,SHELL','SECDATA,.15,1,0,7','SECOFFSET,MID','MP,EX,1,205000','MP,PRXY,1,.29','TB,BISO,1',f'TBDATA,1,{sy},{et}','ET,2,MPC184','KEYOPT,2,1,1','KEYOPT,2,2,0']
lines += [f'N,{n},{p[0]:.10g},{p[1]:.10g},{p[2]:.10g}' for n,p in N.items()]
lines+=['TYPE,1','MAT,1','SECNUM,1']+[f'EN,{i+1},'+','.join(map(str,ids)) for i,ids in enumerate(E)]
lines += ['ESEL,S,TYPE,,1','CM,NICKEL,ELEM','ALLSEL,ALL']
lines+=['TYPE,2']+[f'E,{pilot},{n}' for n in sorted(set(attach))]
for n in sorted(set(clamp)):lines.append(f'D,{n},ALL,0')
lines += ['ALLSEL,ALL',f'D,{pilot},UX,0','/SOLU','NLGEOM,ON','FINISH','/PREP7','CHECK','*GET,NN,NODE,0,COUNT','*GET,NE,ELEM,0,COUNT','*CFOPEN,inventory,txt','*VWRITE,NN,NE',"(2F12.0)",'*CFCLOS','SAVE,model,db','FINISH']
model='\n'.join(lines)+'\n';(out/'model.inp').write_text(model)
(out/'preflight.dat').write_text(model+'\n/EXIT,NOSAVE\n')
solve='''/SOLU
ANTYPE,STATIC
NLGEOM,ON
NROPT,FULL
EQSLV,SPARSE
AUTOTS,ON
NEQIT,60
LNSRCH,ON
KBC,0
OUTRES,ALL,ALL
RESCONTROL,DEFINE,ALL,LAST,2
TIME,1
NSUBST,50,2000,10
D,%s,UX,%.12g
SOLVE
FINISH
SAVE,solved,db
/POST1
SET,LAST
*GET,NSET,ACTIVE,0,SET,NSET
*CFOPEN,history,csv
*VWRITE
('set,time,ux_mm,fx_N,uy_mm,uz_mm,rotx,roty,rotz,max_seqv_MPa,max_eppl')
*DO,II,1,NSET
SET,,,,,,,II
*GET,TT,ACTIVE,0,SET,TIME
*GET,UXP,NODE,%s,U,X
*GET,FXP,NODE,%s,RF,FX
*GET,UYP,NODE,%s,U,Y
*GET,UZP,NODE,%s,U,Z
*GET,RXP,NODE,%s,ROT,X
*GET,RYP,NODE,%s,ROT,Y
*GET,RZP,NODE,%s,ROT,Z
CMSEL,S,NICKEL
NSLE,S
SHELL,TOP
ETABLE,SEQ,S,EQV
ETABLE,EPL,EPPL,EQV
ESORT,ETAB,SEQ,0,0
*GET,SMAX,SORT,0,MAX
ESORT,ETAB,EPL,0,0
*GET,PMAX,SORT,0,MAX
SHELL,BOT
ETABLE,SEQ,S,EQV
ETABLE,EPL,EPPL,EQV
ESORT,ETAB,SEQ,0,0
*GET,SMAXB,SORT,0,MAX
ESORT,ETAB,EPL,0,0
*GET,PMAXB,SORT,0,MAX
SMAX=MAX(SMAX,SMAXB)
PMAX=MAX(PMAX,PMAXB)
*VWRITE,II,TT,UXP,FXP,UYP,UZP,RXP,RYP,RZP,SMAX,PMAX
(F8.0,10(',',E19.11))
ALLSEL,ALL
*ENDDO
*CFCLOS
SET,LAST
RSYS,0
*CFOPEN,nodal,csv
*VWRITE
('node,x_mm,y_mm,z_mm,ux_mm,uy_mm,uz_mm')
*DO,II,1,%s
*GET,NX,NODE,II,LOC,X
*GET,NY,NODE,II,LOC,Y
*GET,NZ,NODE,II,LOC,Z
*GET,UX1,NODE,II,U,X
*GET,UY1,NODE,II,U,Y
*GET,UZ1,NODE,II,U,Z
*VWRITE,II,NX,NY,NZ,UX1,UY1,UZ1
(F9.0,6(',',E19.11))
*ENDDO
*CFCLOS
CMSEL,S,NICKEL
SHELL,TOP
ETABLE,SEQ,S,EQV
ETABLE,EPL,EPPL,EQV
*CFOPEN,element_top,csv
*VWRITE
('element,seqv_MPa,eppl')
*DO,II,1,%s
*GET,SS,ELEM,II,ETAB,SEQ
*GET,EE,ELEM,II,ETAB,EPL
*VWRITE,II,SS,EE
(F9.0,2(',',E19.11))
*ENDDO
*CFCLOS
ALLSEL,ALL
FINISH
/EXIT,NOSAVE
'''%(pilot,sign*umax,pilot,pilot,pilot,pilot,pilot,pilot,pilot,nphys,len(E))
extra=[]
for surface in ['BOT']:
 extra += ['/POST1','SET,LAST','CMSEL,S,NICKEL','SHELL,'+surface,'ETABLE,SEQ,S,EQV','ETABLE,EPL,EPPL,EQV','*CFOPEN,element_bottom,csv','*VWRITE',"('element,seqv_MPa,eppl')",'*DO,II,1,'+str(len(E)),'*GET,SS,ELEM,II,ETAB,SEQ','*GET,EE,ELEM,II,ETAB,EPL','*VWRITE,II,SS,EE',"(F9.0,2(',',E19.11))",'*ENDDO','*CFCLOS','ALLSEL,ALL']
extra+=['*CFOPEN,balance,csv','*VWRITE',"('set,force_x_N,force_y_N,force_z_N')",'*DO,II,1,NSET','SET,,,,,,,II','SX=0','SY=0','SZ=0']
for nd in sorted(set(clamp))+[pilot]:
 for ax in 'XYZ':extra += ['RR=0',f'*GET,RR,NODE,{nd},RF,F{ax}',f'S{ax}=S{ax}+RR']
extra+=['*VWRITE,II,SX,SY,SZ',"(F8.0,3(',',E19.11))",'*ENDDO','*CFCLOS']
solve=solve.replace('FINISH\n/EXIT,NOSAVE','\n'.join(extra)+'\nFINISH\n/EXIT,NOSAVE')
(out/'run.dat').write_text(model+solve)
mesh=dict(nodes=N,elements=E,region=region,clamp=sorted(set(clamp)),attachment=sorted(set(attach)),pilot=pilot,area=sum(areas),min_area=min(areas),max_edge_ratio=max(aspects))
(out/'mesh.json').write_text(json.dumps(mesh))
cfg.update(nodes=len(N),shell_elements=len(E),rigid_links=len(set(attach)),max_edge_ratio=max(aspects))
(out/'config.json').write_text(json.dumps(cfg,indent=2))
(out/'input_sha256.json').write_text(json.dumps({f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in ['model.inp','preflight.dat','run.dat','mesh.json','config.json']},indent=2))
print(cfg)
