"""Exercise four-stage force and contact readback on the completed, fixed-top raised control."""
import json

import numpy as np
from ansys.mapdl import reader
from audit_install import contact_history
from audit_local import ROOT, read, table
from local_equilibrium import SCREW_PILOTS, movement_table, positions, recover


def check():
    case='stand3_nylon_lateral_friction_locked_pin1'
    proof=read(ROOT/'validation/local'/f'{case}.json')
    f=ROOT/'.runtime/archive'/proof['campaign']/case
    raw=reader.read_binary(str(f/'pull.rst'))
    move=movement_table(f/'moving_supports.csv')
    for k in range(raw.nsets):
        nodes,d=raw.nodal_solution(k)
        idx=positions(nodes,SCREW_PILOTS)
        assert np.max(abs(d[idx,:3]))<1.e-10
        move.update({(k+1,n):u.tolist() for n,u in zip(SCREW_PILOTS,d[idx,:3],strict=True)})
    rows=recover(f/'pull.rst',ROOT/'.runtime/local_inputs'/proof['source'],move,True,moving_screw_tops=True)
    ref=table(ROOT/'.runtime/post'/proof['campaign']/case/'whole_fixture_balance.csv')
    for key in ref.dtype.names:assert np.array_equal([r[key] for r in rows],ref[key]),key
    tab=table(f/'case_pairs.csv')
    topology={i:int(tab['elements'][tab['pair']==i][0]) for i in (861,862)}
    _,checks=contact_history(raw,rows,tab,topology)
    independent=read(ROOT/'validation/pulls'/f'{case}_contact.json')
    assert np.isclose(max(checks['peak_closed_corner_penetration_mm'].values()),independent['max_closed_corner_penetration_mm'])
    assert np.isclose(checks['worst_case_support_contact_residual_N'],independent['max_active_contact_vs_support_force_residual_N'])
    data=dict(control=case,rst_sha256=proof['rst_sha256'],sets=len(rows),original_columns_reproduced=list(ref.dtype.names),
              max_case_support_residual_N=checks['worst_case_support_contact_residual_N'],
              scope='Controls four-top reaction recovery and two pair orientations on the raised fixture. Flush shell pairs and actual installation work require new native results.')
    (ROOT/'validation/install_reader_control.json').write_text(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':check()
