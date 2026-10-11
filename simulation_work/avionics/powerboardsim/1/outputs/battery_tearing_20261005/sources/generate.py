import csv,hashlib,json,math,sys
from pathlib import Path
S=Path(__file__).resolve().parent.parent
P=S.parent.parent
for x in ['runtime','audit','results','figures']:(S/x).mkdir(exist_ok=True)
curve=list(csv.DictReader((P/'outputs/granta_audit_20261005/records/nickel200_annealed_sheet_20C.csv').open()))
def material(e0=.3,uf=.12,branch='power',cap=.9999):
    l=['MP,EX,1,205000','MP,PRXY,1,.29','TB,PLAS,1,,,MISO']
    for r in curve:l.append('TBPT,DEFI,%s,%s'%(r['true_plastic_strain'],r['true_stress_MPa']))
    for k in range(21,161):
        p=k/100;s=530.429*(p/.199999)**.3161930942101825 if branch=='power' else 530.429
        l.append('TBPT,DEFI,%.8g,%.9g'%(p,s))
    l+=['TB,CDM,1,,2,DUCTILE',
        '! Numerical tension-only extension: negligible accumulation for negative eta.',
        '! Transition [-1e-6,0]; not a calibrated compression/shear fracture law.',
        'TBPT,DEFI,-1000,1e6','TBPT,DEFI,-.000001,1e6']
    for eta in [0,1/3,.4,.5,.6,2/3,.8,1,1.2,1.5,2]:
        l.append('TBPT,DEFI,%.10g,%.10g'%(eta,e0*math.exp(-1.5*max(eta-1/3,0))))
    l+=['TB,CDM,1,,,LINDMG',f'TBDATA,1,{uf}','TB,CDM,1,,,DCAP',f'TBDATA,1,{cap}']
    return '\n'.join(l)+'\n'
def seal(d,config):
    (d/'config.json').write_text(json.dumps(config,indent=2))
    names=['model.inp','preflight.dat','run.dat','config.json']
    if (d/'mesh.json').exists():names.append('mesh.json')
    (d/'input_sha256.json').write_text(json.dumps({n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in names},indent=2))
def coupon(case='coupon_nominal',nlgeom='ON'):
    d=S/'runtime'/case;d.mkdir(exist_ok=False)
    model='/BATCH\n/PREP7\n/UNITS,MPA\nET,1,SHELL181\nKEYOPT,1,3,2\nKEYOPT,1,8,2\nSECTYPE,1,SHELL\nSECDATA,.15,1,0,7\n'+material()+'''N,1,0,0,0
N,2,1,0,0
N,3,1,1,0
N,4,0,1,0
E,1,2,3,4
D,ALL,UZ,0
D,ALL,ROTX,0
D,ALL,ROTY,0
D,ALL,ROTZ,0
D,1,UX,0
D,4,UX,0
D,1,UY,0
D,2,UY,0
CHECK
*GET,NN,NODE,0,COUNT
*GET,NE,ELEM,0,COUNT
*CFOPEN,inventory,txt
*VWRITE,NN,NE
(2F12.0)
*CFCLOS
SAVE,model,db
FINISH
'''
    solve=f'''/SOLU
ANTYPE,STATIC
NLGEOM,{nlgeom}
NROPT,UNSYM
EQSLV,SPARSE
AUTOTS,ON
NEQIT,60
LNSRCH,ON
KBC,0
OUTRES,ALL,ALL
TIME,1
NSUBST,400,20000,200
CUTCONTROL,DMGLIMIT,.01
CNVTOL,F,,1e-6,,1
CNVTOL,M,,1e-6,,1
D,2,UX,1
D,3,UX,1
SOLVE
FINISH
SAVE,solved,db
/POST1
/NOPR
SET,LAST
*GET,NSET,ACTIVE,0,SET,NSET
*CFOPEN,history,csv
*VWRITE
('set,time,ux_mm,fx_N,uy_mm,sx_MPa,eppl,damage')
*DO,II,1,NSET
SET,,,,,,,II
*GET,TT,ACTIVE,0,SET,TIME
*GET,UX1,NODE,2,U,X
*GET,UY1,NODE,3,U,Y
*GET,F1,NODE,2,RF,FX
*GET,F2,NODE,3,RF,FX
FX1=F1+F2
SHELL,TOP
ETABLE,SXX,S,X
ETABLE,EPL,NL,EPEQ
ETABLE,DMG,GDMG
*GET,SX1,ELEM,1,ETAB,SXX
*GET,EP1,ELEM,1,ETAB,EPL
*GET,DD1,ELEM,1,ETAB,DMG
*VWRITE,II,TT,UX1,FX1,UY1,SX1,EP1,DD1
(F8.0,7(',',E19.11))
*ENDDO
*CFCLOS
/EXIT,NOSAVE
'''
    (d/'model.inp').write_text(model);(d/'preflight.dat').write_text(model+'/EXIT,NOSAVE\n');(d/'run.dat').write_text(model+solve)
    seal(d,dict(case=case,model='one uniform uniaxial shell',nodes=4,elements=1,solver_ranks=1,nlgeom=nlgeom,end_time=1,displacement_mm=1,eps0=.3,uf_mm=.12,damage_cap=.9999))
if __name__=='__main__':coupon(sys.argv[1] if len(sys.argv)>1 else 'coupon_nominal')
