"""Generate isolated attachment models, preserving the earlier 750 N clamp model."""
from generate import S,P,material,seal
import json,re,sys,hashlib
def make(case,fac=1,e0=.3,uf=.12,branch='power',umax=8,sign=1,cap=.9999,delta=.25):
    base=P/'outputs/battery_side_pull_20261005/runtime'/('friction_locked_fine' if fac==2 else 'friction_locked')
    d=S/'runtime'/case;d.mkdir(exist_ok=False)
    cfg=json.loads((base/'config.json').read_text());m=json.loads((base/'mesh.json').read_text())
    pilot=m['pilot'];nel=len(m['elements']);nphys=pilot-1;bottom=cfg['bottom_pilots']
    model=(base/'model.inp').read_text()
    assert model.count('TB,BISO,1\nTBDATA,1,148.0,1000')==1
    model=model.replace('TB,BISO,1\nTBDATA,1,148.0,1000',material(e0,uf,branch,cap))
    model=model.replace('/BATCH','/BATCH\n/TITLE,Edge battery: estimated nickel ductile damage',1)
    nsteps=round(umax/delta);assert abs(nsteps*delta-umax)<1e-9
    solve=f'''/SOLU
ANTYPE,STATIC
NLGEOM,ON
NROPT,UNSYM,,OFF
EQSLV,SPARSE
AUTOTS,ON
NEQIT,60
LNSRCH,ON
KBC,0
OUTRES,ALL,LAST
RESCONTROL,DEFINE,ALL,LAST,3
TIME,1
NSUBST,20,1000,5
F,{bottom[0]},FZ,750
F,{bottom[1]},FZ,750
SOLVE
*GET,COK,ACTIVE,0,SOLU,CNVG
*IF,COK,NE,1,THEN
/EXIT,NOSAVE
*ENDIF
*CFOPEN,preload_lock,csv
*VWRITE
('pilot,uz_mm,applied_preload_N')
'''
    for pn in bottom:
        solve+=f'''*GET,LOCKUZ,NODE,{pn},U,Z
FDELE,{pn},FZ
D,{pn},UZ,LOCKUZ
*VWRITE,{pn},LOCKUZ,750
(F9.0,2(',',E19.11))
'''
    solve+=f'''*CFCLOS
KBC,1
TIME,2
NSUBST,1,100,1
SOLVE
*GET,COK,ACTIVE,0,SOLU,CNVG
*IF,COK,NE,1,THEN
/EXIT,NOSAVE
*ENDIF
KBC,0
'''
    for dof in ['UY','UZ','ROTX','ROTY','ROTZ']:solve+=f'DDELE,{pilot},{dof}\n'
    solve+='''CNVTOL,F,,1E-5,,1
CNVTOL,M,,1E-4,,1
CUTCONTROL,DMGLIMIT,.02
FINISH
/NOPR
*CFOPEN,history,csv
*VWRITE
('step,time,ux_mm,fx_N,uy_mm,uz_mm,roty,dtop,dmid,dbot,peeq,seqv,clamp1_N,clamp2_N')
*CFCLOS
*CFOPEN,balance,csv
*VWRITE
('step,rx_N,ry_N,rz_N')
*CFCLOS
'''
    solve+=f'''*DIM,NVAL,ARRAY,{nphys},7
*VFILL,NVAL(1,1),RAMP,1,1
*DIM,EVAL,ARRAY,{nel},7
*VFILL,EVAL(1,1),RAMP,1,1
*DO,JJ,1,{nsteps}
 /SOLU
 TIME,2+JJ*{delta}
 NSUBST,10,2000,5
 D,{pilot},UX,{sign*delta}*JJ
 SOLVE
 *GET,COK,ACTIVE,0,SOLU,CNVG
 *IF,COK,NE,1,THEN
  *EXIT
 *ENDIF
 FINISH
 SAVE,last_good,db
 /POST1
 SET,LAST
 *GET,TT,ACTIVE,0,SET,TIME
 *GET,UXP,NODE,{pilot},U,X
 *GET,FXP,NODE,{pilot},RF,FX
 *GET,UYP,NODE,{pilot},U,Y
 *GET,UZP,NODE,{pilot},U,Z
 *GET,RYP,NODE,{pilot},ROT,Y
 CMSEL,S,NICKEL
 NSLE,S
 DTOP=0
 DMID=0
 DBOT=0
 PMAX=0
 SMAX=0
'''
    for idx,sh in enumerate(['TOP','MID','BOT'],start=2):
        solve+=f''' SHELL,{sh}
 ETABLE,ERAS
 ETABLE,DD,GDMG
 ETABLE,PP,NL,EPEQ
 ETABLE,SS,S,EQV
 ESORT,ETAB,DD,0,0
 *GET,DDMAX,SORT,0,MAX
 D{sh}=DDMAX
 ESORT,ETAB,PP,0,0
 *GET,PPMAX,SORT,0,MAX
 PMAX=MAX(PMAX,PPMAX)
 ESORT,ETAB,SS,0,0
 *GET,SSMAX,SORT,0,MAX
 SMAX=MAX(SMAX,SSMAX)
 *VLEN,{nel}
 *VGET,EVAL(1,{idx}),ELEM,1,ETAB,DD
'''
    solve+=f''' *VGET,EVAL(1,5),ELEM,1,ETAB,PP
 *VGET,EVAL(1,6),ELEM,1,ETAB,SS
 *VGET,EVAL(1,7),ELEM,1,CENT,Z
 *CFOPEN,damage_%JJ%,csv
 *VLEN,1
 *VWRITE
('element,damage_top,damage_mid,damage_bot,peeq_bot,seqv_bot,z_mm')
 *VLEN,{nel}
 *VWRITE,EVAL(1,1),EVAL(1,2),EVAL(1,3),EVAL(1,4),EVAL(1,5),EVAL(1,6),EVAL(1,7)
(F9.0,6(',',E16.8))
 *CFCLOS
 ALLSEL,ALL
 *VLEN,{nphys}
 *VGET,NVAL(1,2),NODE,1,LOC,X
 *VGET,NVAL(1,3),NODE,1,LOC,Y
 *VGET,NVAL(1,4),NODE,1,LOC,Z
 *VGET,NVAL(1,5),NODE,1,U,X
 *VGET,NVAL(1,6),NODE,1,U,Y
 *VGET,NVAL(1,7),NODE,1,U,Z
 *CFOPEN,nodes_%JJ%,csv
 *VLEN,1
 *VWRITE
('node,x_mm,y_mm,z_mm,ux_mm,uy_mm,uz_mm')
 *VLEN,{nphys}
 *VWRITE,NVAL(1,1),NVAL(1,2),NVAL(1,3),NVAL(1,4),NVAL(1,5),NVAL(1,6),NVAL(1,7)
(F9.0,6(',',E16.8))
 *CFCLOS
 *VLEN,1
 *GET,W1F,NODE,{bottom[0]},RF,FZ
 *GET,W2F,NODE,{bottom[1]},RF,FZ
 *CFOPEN,history,csv,,APPEND
 *VWRITE,JJ,TT,UXP,FXP,UYP,UZP,RYP,DTOP,DMID,DBOT,PMAX,SMAX,W1F,W2F
(F8.0,13(',',E16.8))
 *CFCLOS
 SX=0
 SY=0
 SZ=0
'''
    solve+=f' *GET,SX,NODE,{pilot},RF,FX\n'
    for pn in cfg['target_pilots']:
        for ax in 'XYZ':
            solve+=f' RR=0\n *GET,RR,NODE,{pn},RF,F{ax}\n S{ax}=S{ax}+RR\n'
    solve+=''' *CFOPEN,balance,csv,,APPEND
 *VWRITE,JJ,SX,SY,SZ
(F8.0,3(',',E16.8))
 *CFCLOS
 FINISH
 *IF,PMAX,GT,1.55,THEN
  *CFOPEN,STOP_STRAIN_LIMIT,txt
  *VWRITE,JJ,UXP,PMAX
(3E19.10)
  *CFCLOS
  *EXIT
 *ENDIF
*ENDDO
FINISH
/EXIT,NOSAVE
'''
    (d/'model.inp').write_text(model)
    (d/'preflight.dat').write_text(model+'/EXIT,NOSAVE\n')
    (d/'run.dat').write_text(model+solve)
    (d/'mesh.json').write_bytes((base/'mesh.json').read_bytes())
    cfg.update(case=case,elements=cfg['expected_total_elements'],eps0=e0,uf_mm=uf,hardening=branch,damage_cap=cap,displacement_mm=umax,delta_mm=delta,sign=sign,end_time=2+umax,solver_ranks=4,
               source_case=str(base),source_model_sha256=hashlib.sha256((base/'model.inp').read_bytes()).hexdigest(),
               retained_physics='same 750 N preload, locked platens, mu=0.2, free five other battery DOFs',
               fracture_definition='Native continuous damage only; no element deletion. Near-complete damage is not geometric severance.')
    seal(d,cfg)
    print(case,'prepared:',cfg['nodes'],'nodes',cfg['elements'],'elements')
if __name__=='__main__':
    make(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 1)
