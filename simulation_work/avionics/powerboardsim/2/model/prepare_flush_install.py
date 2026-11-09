"""Stage a physical tab-drawdown trial; no solve may be dispatched from this generator."""
import json
from pathlib import Path
import numpy as np
from local_case_geometry import ROOT, make
from stage_local_jobs import seal


def nickel_case_contact():
    # Two exterior sides of both active strips against a deformable PLA target.
    # The shell's reference surface is the mid-plane of its actual 0.15 mm section.
    lines=['ET,863,TARGE170','ET,864,CONTA174','KEYOPT,864,11,1','MP,MU,864,0']
    for real,side in [(863,'TOP'),(864,'BOTTOM')]:
        lines += ['ALLSEL,ALL',f'R,{real},,,,,,-0.6',f'REAL,{real}','ESEL,S,TYPE,,850','NSLE,S','TYPE,863','TSHAP','ESURF',
                  'ALLSEL,ALL','CMSEL,S,NICKEL,ELEM','NSLE,S','TYPE,864','MAT,864',f'ESURF,,{side}']
    return '\n'.join(lines+['ALLSEL,ALL',''])


def stage():
    source=ROOT/'.runtime/local_inputs/lateral_friction_locked'
    pilot=json.loads((source/'mesh.json').read_text())['pilot']
    mesh=np.load(ROOT/'.runtime/mesh/case_3.npz');skin=np.load(ROOT/'.runtime/mesh/fixture_targets.npz')
    cased=make(mesh,skin,'nylon',0.,pilot,initial_retreat_mm=3.)
    cased+='RMODIF,861,6,-0.6\nRMODIF,862,6,-0.6\n'+nickel_case_contact()
    prior=(source/'run.dat').read_text();assert prior.count('SAVE,model,db')==1
    head,rest=prior.split('SAVE,model,db')
    start=head+cased
    # This is a proposed local test, not an audited or released production model.
    # Four rigid screw tops are the local stand-in for the flexible PCB. Both beam
    # ends initially shift together so the unloaded axial grip is the flush grip.
    tag='TIME,3\nNSUBST,100,4000,20\n'
    assert tag in rest
    tops=(950002,950004,950006,950008)
    install='TIME,3\nNSUBST,150,6000,75\n'+''.join(f'D,{top},UZ,3.0\n' for top in tops)+'SOLVE\nTIME,4\nNSUBST,100,4000,20\n'
    assert rest.index(f'DDELE,{pilot},UZ')<rest.index(tag)
    run=start+'SAVE,model,db'+rest.replace(tag,install,1)
    # At t=2 the washer heights are locked. At t=3 the tabs have advanced 3 mm
    # with lateral cell displacement held at zero. Only t=3..4 drives it sideways.
    checks=['/GOPR','ALLSEL,ALL','*CFOPEN,inventory,csv','*VWRITE', "('pair,target,contact')"]
    for real in (861,862,863,864):
        t,c=(861,862) if real<863 else (863,864)
        for typ,par in [(t,'NT'),(c,'NC')]:
            checks.extend([f'ESEL,S,TYPE,,{typ}',f'ESEL,R,REAL,,{real}',f'*GET,{par},ELEM,0,COUNT'])
        checks+= [f'*VWRITE,{real},NT,NC',"(F5.0,2(',',F10.0))"]
    checks+=['*CFCLOS','ALLSEL,ALL','FINISH','/SOLU','ANTYPE,STATIC','NLGEOM,ON','CNCHECK,DETAIL,861,864',
             '/COM,FLUSH_APPROACH_PREFLIGHT_END','FINISH','/EXIT,NOSAVE','']
    dest=ROOT/'.runtime/flush_approach_v1';dest.mkdir(exist_ok=True)
    pre_hash=seal(dest/'pre.inp',(start+'\n'+'\n'.join(checks)).encode())
    trial_hash=seal(dest/'trial.inp',run.encode())
    # Verify no beam pre-stretch was introduced by shifting the assembly.
    original=make(mesh,skin,'nylon',0.,pilot)
    prior_xyz={line.split(',')[1]:np.array(line.split(',')[2:],float) for line in original.splitlines() if line.startswith('N,')}
    new_xyz={line.split(',')[1]:np.array(line.split(',')[2:],float) for line in cased.splitlines() if line.startswith('N,')}
    for top in tops:
        for node in (top,top-1):
            assert np.allclose(new_xyz[str(node)]-prior_xyz[str(node)],[0,0,-3],atol=1e-8)
        assert np.linalg.norm((new_xyz[str(top)]-new_xyz[str(top-1)])-(prior_xyz[str(top)]-prior_xyz[str(top-1)]))<1.e-8
    print(json.dumps({'preflight_input_sha256':pre_hash,'trial_input_sha256':trial_hash,'scope':'Unlaunched local proposal; shell/PLA contact on both active strip faces; four fixed screw-top increments; unchanged flush screw grip; passive neighboring strip response absent.'},indent=2))

if __name__=='__main__':stage()
