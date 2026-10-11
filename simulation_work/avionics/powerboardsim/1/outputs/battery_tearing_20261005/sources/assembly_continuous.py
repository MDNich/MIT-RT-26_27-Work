"""Fresh attachment runs: one continuous SOLU session, separate read-only POST1.
All converged substeps are retained. No resumption of the rejected run is used.
"""
from generate import S,P,material,seal
import argparse,json,hashlib

def make(case,fac=1,e0=.3,uf=.12,branch='power',umax=8,sign=1,delta=.25,cores=4,force_tol=1e-5):
    base=P/'outputs/battery_side_pull_20261005/runtime'/('friction_locked_fine' if fac==2 else 'friction_locked')
    d=S/'runtime'/case; d.mkdir(exist_ok=False)
    cfg=json.loads((base/'config.json').read_text()); m=json.loads((base/'mesh.json').read_text())
    pilot=m['pilot']; bottom=cfg['bottom_pilots']; nel=len(m['elements']); nphys=pilot-1
    model=(base/'model.inp').read_text()
    assert model.count('TB,BISO,1\nTBDATA,1,148.0,1000')==1
    model=model.replace('TB,BISO,1\nTBDATA,1,148.0,1000',material(e0,uf,branch))
    model=model.replace('/BATCH','/BATCH\n/TITLE,Edge battery: continuous preloaded nickel damage',1)
    nsteps=round(umax/delta); assert abs(nsteps*delta-umax)<1e-9
    solve=f'''/SOLU
ANTYPE,STATIC
NLGEOM,ON
NROPT,UNSYM,,OFF
EQSLV,SPARSE
AUTOTS,ON
NEQIT,60
LNSRCH,ON
KBC,0
OUTRES,ALL,ALL
RESCONTROL,DEFINE,ALL,LAST,3
CNVTOL,F,,1E-5,,1
CNVTOL,M,,1E-4,,1
CUTCONTROL,DMGLIMIT,.02
*CFOPEN,solve_progress,csv
*VWRITE
('stage,loadstep,substep,iterations,ux_mm,converged')
*CFCLOS
TIME,1
NSUBST,20,1000,5
F,{bottom[0]},FZ,750
F,{bottom[1]},FZ,750
SOLVE
'''
    def gate(expected):
        return f'''*GET,COK,ACTIVE,0,SOLU,CNVG
*GET,LSTEP,ACTIVE,0,SOLU,NCMLS
*GET,SSTEP,ACTIVE,0,SOLU,NCMSS
*GET,CITER,ACTIVE,0,SOLU,NCMIT
*GET,UXP,NODE,{pilot},U,X
*CFOPEN,solve_progress,csv,,APPEND
*VWRITE,{expected},LSTEP,SSTEP,CITER,UXP,COK
(4(F10.0,','),E19.11,',',F4.0)
*CFCLOS
*IF,COK,NE,1,THEN
 /EXIT,NOSAVE
*ENDIF
*IF,LSTEP,NE,{expected},THEN
 *CFOPEN,REJECTED_LOAD_HISTORY,txt
 *VWRITE,{expected},LSTEP
 (2F10.0)
 *CFCLOS
 /EXIT,NOSAVE
*ENDIF
'''
    solve+=gate('1')+'''*CFOPEN,preload_lock,csv
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
    solve+='''*CFCLOS
KBC,1
TIME,2
NSUBST,1,100,1
SOLVE
'''+gate('2')+'KBC,0\n'
    for dof in ['UY','UZ','ROTX','ROTY','ROTZ']: solve+=f'DDELE,{pilot},{dof}\n'
    solve+=f'''CNVTOL,F,,{force_tol:.10g},,1
*DO,JJ,1,{nsteps}
 TIME,2+JJ*{delta}
 NSUBST,10,2000,5
 D,{pilot},UX,{sign*delta}*JJ
 SOLVE
'''+gate('JJ+2')+''' SAVE,last_good,db
*ENDDO
SAVE,solved,db
FINISH
/EXIT,NOSAVE
'''
    # No results SET or processor change can occur inside the solve sequence.
    active=solve[solve.index('SOLVE\n'):solve.rindex('FINISH')]
    assert '/SOLU' not in active and '/POST' not in active and 'FINISH' not in active and '\nSET,' not in active
    post=f'''/BATCH
RESUME,model,db
/POST1
FILE,tear,rst
/NOPR
SET,LAST
*GET,NSETS,ACTIVE,0,SET,NSET
*DIM,NVAL,ARRAY,{nphys},7
*VFILL,NVAL(1,1),RAMP,1,1
*DIM,EVAL,ARRAY,{nel},7
*VFILL,EVAL(1,1),RAMP,1,1
*CFOPEN,history,csv
*VWRITE
('step,time,ux_mm,fx_N,uy_mm,uz_mm,roty,dtop,dmid,dbot,peeq,seqv,clamp1_N,clamp2_N')
*CFCLOS
*CFOPEN,balance,csv
*VWRITE
('step,rx_N,ry_N,rz_N')
*CFCLOS
*CFOPEN,set_inventory,csv
*VWRITE
('set,loadstep,substep,time,ux_mm,fx_N,clamp1_N,clamp2_N,peeq,damage')
*CFCLOS
JJ=0
*DO,KK,1,NSETS
 ALLSEL,ALL
 SET,,,,,,,KK
 *GET,LS,ACTIVE,0,SET,LSTP
 *GET,SS,ACTIVE,0,SET,SBST
 *IF,SS,EQ,999999,THEN
  *CYCLE
 *ENDIF
 *GET,TT,ACTIVE,0,SET,TIME
 *GET,UXP,NODE,{pilot},U,X
 *GET,FXP,NODE,{pilot},RF,FX
 *GET,UYP,NODE,{pilot},U,Y
 *GET,UZP,NODE,{pilot},U,Z
 *GET,RYP,NODE,{pilot},ROT,Y
 *GET,W1F,NODE,{bottom[0]},RF,FZ
 *GET,W2F,NODE,{bottom[1]},RF,FZ
 CMSEL,S,NICKEL
 NSLE,S
 PMAX=0
 SMAX=0
'''
    for idx,sh in enumerate(['TOP','MID','BOT'],start=2):
        post+=f''' SHELL,{sh}
 ETABLE,ERAS
 ETABLE,DD,GDMG
 ETABLE,PP,NL,EPEQ
 ETABLE,SSV,S,EQV
 ESORT,ETAB,DD,0,0
 *GET,D{sh},SORT,0,MAX
 ESORT,ETAB,PP,0,0
 *GET,PPMAX,SORT,0,MAX
 PMAX=MAX(PMAX,PPMAX)
 ESORT,ETAB,SSV,0,0
 *GET,SSMAX,SORT,0,MAX
 SMAX=MAX(SMAX,SSMAX)
 *VLEN,{nel}
 *VGET,EVAL(1,{idx}),ELEM,1,ETAB,DD
'''
    post+=f''' *VGET,EVAL(1,5),ELEM,1,ETAB,PP
 *VGET,EVAL(1,6),ELEM,1,ETAB,SSV
 *VGET,EVAL(1,7),ELEM,1,CENT,Z
 DMAX=MAX(DTOP,DMID,DBOT)
 *VLEN,1
 *CFOPEN,set_inventory,csv,,APPEND
 *VWRITE,KK,LS,SS,TT,UXP,FXP,W1F,W2F,PMAX,DMAX
 (3(F9.0,','),6(E19.11,','),E19.11)
 *CFCLOS
 *IF,LS,LT,3,THEN
  *CYCLE
 *ENDIF
 JJ=JJ+1
 *CFOPEN,damage_%JJ%,csv
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
 *CFOPEN,history,csv,,APPEND
 *VWRITE,JJ,TT,UXP,FXP,UYP,UZP,RYP,DTOP,DMID,DBOT,PMAX,SMAX,W1F,W2F
(F8.0,13(',',E16.8))
 *CFCLOS
 SX=FXP
 SY=0
 SZ=0
'''
    for pn in cfg['target_pilots']:
        for ax in 'XYZ': post+=f' *GET,RR,NODE,{pn},RF,F{ax}\n S{ax}=S{ax}+RR\n'
    post+=''' *CFOPEN,balance,csv,,APPEND
 *VWRITE,JJ,SX,SY,SZ
(F8.0,3(',',E16.8))
 *CFCLOS
*ENDDO
FINISH
/EXIT,NOSAVE
'''
    (d/'model.inp').write_text(model); (d/'preflight.dat').write_text(model+'/EXIT,NOSAVE\n')
    (d/'run.dat').write_text(model+solve); (d/'post.dat').write_text(post)
    (d/'mesh.json').write_bytes((base/'mesh.json').read_bytes())
    cfg.update(case=case,elements=cfg['expected_total_elements'],eps0=e0,uf_mm=uf,hardening=branch,damage_cap=.9999,displacement_mm=umax,delta_mm=delta,sign=sign,end_time=2+umax,solver_ranks=cores,
       yield_MPa=185,tangent_MPa=None,plasticity='Granta Nickel200102-point MISO plus estimated tail',
       force_convergence_tolerance_pull=force_tol,force_convergence_tolerance_preload=1e-5,
       load_protocol='continuous_solu_v2',result_policy='all converged substeps; separate POST1; exclude substep999999',
       source_case=str(base),source_model_sha256=hashlib.sha256((base/'model.inp').read_bytes()).hexdigest(),
       strain_limit_policy='Report any section-summary PEEQ over1.55; MISO table plateaus beyond1.6; no live strain stop in continuous SOLU',
       fracture_definition='Native continuous damage only; no element deletion. Near-complete damage is not geometric severance.')
    seal(d,cfg)
    f=d/'input_sha256.json';mf=json.loads(f.read_text()); mf['post.dat']=hashlib.sha256((d/'post.dat').read_bytes()).hexdigest();f.write_text(json.dumps(mf,indent=2))
    print(case,':',cfg['nodes'],'nodes,',cfg['elements'],'elements; continuous SOLU,',nsteps+2,'load steps')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('--fac',type=int,default=1);p.add_argument('--e0',type=float,default=.3);p.add_argument('--uf',type=float,default=.12);p.add_argument('--branch',default='power',choices=['power','plateau']);p.add_argument('--umax',type=float,default=8);p.add_argument('--delta',type=float,default=.25);p.add_argument('--sign',type=int,default=1);p.add_argument('--cores',type=int,default=4);p.add_argument('--force-tol',type=float,default=1e-5)
    make(**vars(p.parse_args()))
