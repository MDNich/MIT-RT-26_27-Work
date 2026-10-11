"""Build a no-SOLVE native preflight from the exported static model."""
from pathlib import Path
import re,hashlib,json,sys,datetime
work=Path(__file__).resolve().parent
if len(sys.argv)>1:setup=Path(sys.argv[1])
else:
    windows_path=(work/'latest_setup.txt').read_text().strip()
    setup=work/windows_path.rsplit('\\',1)[-1]
source=setup/'static_input.dat'
text=source.read_text(errors='strict')
# Stop before the first solve so second-step %_FIX% is never evaluated without a solution.
lines=text.splitlines()
solves=[i for i,line in enumerate(lines) if line.split('!',1)[0].strip().lower()=='solve']
if len(solves)!=2:raise RuntimeError(f'Expected two static load steps; got {len(solves)} SOLVE lines')
pre='\n'.join(lines[:solves[0]])+'\n'
if any(re.match(r'\s*(solve|lssolve)\b',l,re.I) for l in pre.splitlines()):raise RuntimeError('Unexpected solve command')
if text.count('PSMESH,PBPT')!=6:raise RuntimeError('Six pretension definitions required')
if text.count("F,PBPN,FX,PBLoad")!=12:raise RuntimeError('Six loads in each step required')
# The phase-specific branch selects load at step 1 and lock at step 2.
pre+='''
/GOPR
ALLSEL,ALL
/COM,PCB670_NO_SOLVE_CHECK
*CFOPEN,bolt_inventory,csv
*VWRITE
('bolt,prets179,target170,contact174,preload_N')
*DO,PBII,1,6
PBSEC=PBSection%PBII%
PBPIL=PBPilot%PBII%
ESEL,S,TYPE,,PBSEC
*GET,PBPC,ELEM,0,COUNT
ESEL,S,TYPE,,PBSEC+1
*GET,PBTC,ELEM,0,COUNT
ESEL,S,TYPE,,PBSEC+2
*GET,PBCC,ELEM,0,COUNT
*GET,PBFF,NODE,PBPIL,F,FX
*VWRITE,PBII,PBPC,PBTC,PBCC,PBFF
(F4.0,',',F8.0,',',F8.0,',',F8.0,',',F12.3)
*ENDDO
*CFCLOS
ALLSEL,ALL
CNCHECK,DETAIL
FINISH
/PREP7
CDWRITE,DB,pcb670_preflight,cdb
FINISH
/COM,PCB670_NO_SOLVE_COMPLETE
/EXIT,NOSAVE
'''
run=setup/('preflight_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S'))
run.mkdir()
(run/'preflight.dat').write_text(pre)
manifest={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'preflight_sha256':hashlib.sha256((run/'preflight.dat').read_bytes()).hexdigest(),'purpose':'No SOLVE: six cuts, six contact pairs, 750 N load records','product':'ANSYS MAPDL 2026 R1.02','mode':'SMP, one process','results_qualification':'Input check only; preload equilibrium and modal frequencies not solved'}
(run/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(run)
