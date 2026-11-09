"""Verify static imposed relative travel and zero incremental travel after a prestressed modal restart."""
import json
import re
import numpy as np
from audit_local import ROOT,table
from stage_local_jobs import seal,digest


def stage():
    d=ROOT/'.runtime/board_actuator_control_v1'
    d.mkdir(exist_ok=True)
    return seal(d/'control.inp',(ROOT/'model/board_actuator_control.inp').read_bytes())


def audit():
    d=ROOT/'.runtime/board_actuator_control_v1'
    assert int((d/'exit.txt').read_text(encoding='utf-8-sig').strip())==0
    log=(d/'control.out').read_text(errors='replace')
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    a=table(d/'actuator_static.csv')
    assert np.all(np.diff(a['time'])>0) and a['time'][-1]==3.
    drive=.003*np.clip(a['time']-2.,0,1)
    board=(-50*np.minimum(1.,a['time'])-1e5*drive)/1.1e6
    head=board+drive
    for key,val in [('board_z_m',board),('head_z_m',head),('act_z_m',drive),('act_N',1e5*head),
                    ('base_reaction_N',50*np.minimum(1.,a['time']))]:
        assert np.allclose(a[key],val,rtol=1e-6,atol=1e-9),(key,a[key],val)
    m=table(d/'actuator_modal.csv')
    expected=float(np.sqrt(1.1e6/3.)/(2*np.pi))
    assert len(m)==1 and abs(m['frequency_Hz'][0]/expected-1)<1.e-7
    assert abs(m['board_z'][0])>.01 and np.isclose(m['board_z'][0],m['head_z'][0],rtol=1e-9) and abs(m['act_z'][0])<1e-10
    data=dict(scope='Two masses/two springs only; checks relative constraint sign, actuator reaction and prestressed modal boundary. No board result.',
              input_sha256=stage(),listing_sha256=digest((d/'control.out').read_bytes()),sets=len(a),
              final_board_m=float(a['board_z_m'][-1]),final_head_m=float(a['head_z_m'][-1]),
              final_actuator_N=float(a['act_N'][-1]),native_Hz=float(m['frequency_Hz'][0]),analytical_Hz=expected)
    (ROOT/'validation/board_actuator_control.json').write_text(json.dumps(data,indent=2)+'\n')

if __name__=='__main__':
    import sys
    {'stage':stage,'audit':audit}[sys.argv[1]]()
