"""Integrate actuator work and compare measured states bracketing a common force on two verified native paths."""
import json
import numpy as np
from compare_pull import ROOT,series
from audit_local import table


def audit():
    keys=('bare_lateral_friction_locked','stand3_nylon_lateral_friction_locked_pin1')
    paths=[];out={}
    for key in keys:
        proof,records=series(key)
        x=np.array([r['ux_mm'] for r in records]);f=np.array([r['cell_force_N'] for r in records])
        p=np.array([r['nickel_peak_plastic_strain'] for r in records])
        assert x[0]==0 and x[-1]==.5 and np.all(np.diff(x)>0) and np.all(np.diff(f)>0) and np.all(np.diff(p)>=0)
        work=float(np.trapezoid(f,x))
        # Verify against an independent quadrature over the POST1 table keyed by native set.
        native=table(ROOT/f".runtime/archive/{proof['campaign']}/{key}/history.csv")
        h=native[np.isin(native['set'],[r['set'] for r in records])]
        w2=sum(.5*(a['fx_N']+b['fx_N'])*(b['ux_mm']-a['ux_mm']) for a,b in zip(h,h[1:]))
        assert abs(work-w2)<1e-7
        take=np.unique(np.r_[np.arange(0,len(x),2),len(x)-1])
        out[key]=dict(rst_sha256=proof['rst_sha256'],native_travel_states=len(x),cell_X_work_to_half_mm_mJ=work,
                      alternate_state_integration_mJ=float(np.trapezoid(f[take],x[take])),native_POST1_work_mJ=float(w2))
        paths.append((x,f,p))
    x,f,p=paths[1];xb,fb,pb=paths[0];goal=fb[-1]
    i=int(np.searchsorted(f,goal));assert 0<i<len(f) and f[i-1]<goal<f[i]
    br=slice(i-1,i+1)
    result=dict(work=out,target_cell_force_N=float(goal),bare_at_target=dict(travel_mm=float(xb[-1]),peak_nickel_plastic_strain=float(pb[-1])),
       cased_native_neighboring_states=[dict(force_N=float(ff),travel_mm=float(xx),peak_nickel_plastic_strain=float(pp)) for xx,ff,pp in zip(x[br],f[br],p[br])],
       cased_interpolant=dict(travel_mm=float(np.interp(goal,f[br],x[br])),peak_nickel_plastic_strain=float(np.interp(goal,f[br],p[br]))),
       interpretation='Work is external sideways actuator work after washer lock, not energy dissipation. Adjacent converged states span first contact; the force-matched cased values are interpolated, not a native force-controlled endpoint.')
    (ROOT/'validation/pulls/raised_nylon_work.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit(),indent=2))
