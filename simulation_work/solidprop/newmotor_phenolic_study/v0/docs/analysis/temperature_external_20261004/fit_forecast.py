"""Fit a radial surrogate to MAPDL numerical data; hold out the final interval.

All writes are derived analysis products, never solver input or runtime files.
"""
import json
import time
import numpy as np
from scipy.optimize import least_squares
from radial_model import RadialModel, DATA, HERE

profiles=DATA['profiles']
observed=json.loads((HERE/'temperature_history.json').read_text())
depths=np.array([.08,.15,.25,.4,.6,.85,1.1,1.5,2,3,4])/1000+.066675


def evaluate(x, end, dt=.0125):
    model=RadialModel(k_scale=x[0],cp_scale=x[1],qcond_scale=x[2])
    wanted=[p for p in profiles[1:] if p['time_s']<=end+1e-8]
    _,history,snaps=model.run(model.initial(profiles[0]),end,dt=dt,
                             targets=[p['time_s'] for p in wanted])
    residual=[];comparisons=[]
    for p in wanted:
        s=snaps[p['time_s']];truth=np.array(p['temperature_C'])
        pred=model.summary(s)
        # Fixed physical-depth samples, not an arbitrary count of cold mesh nodes.
        err=np.interp(depths,model.r,s.T)-np.interp(depths,DATA['radii_m'],truth)
        ae=s.alpha.mean(axis=1)-np.array(p['alpha'])
        residual.extend(err/10.)
        residual.append((pred['hot_C']-p['audit_hot_C'])/10.)
        residual.append((pred['outer_C']-truth[-1])/.025)
        residual.append((pred['interface_C']-truth[240])/.025)
        residual.extend(ae[::4]/.05)
        first=max(p['layer'],s.layer)
        comparisons.append({'time_s':p['time_s'],'outer_error_K':pred['outer_C']-truth[-1],
                            'interface_error_K':pred['interface_C']-truth[240],
                            'hot_error_K':pred['hot_C']-p['audit_hot_C'],
                            'profile_rmse_K':float(np.sqrt(np.mean((s.T[first:]-truth[first:])**2))),
                            'alpha_rmse':float(np.sqrt(np.mean(ae**2)))})
    return np.array(residual),history,comparisons,model


def fit(end, x0):
    n=0
    def fun(x):
        nonlocal n
        residual,_,_,_=evaluate(x,end)
        n+=1
        print('eval',n,'end',end,'x',x,'rms',np.sqrt(np.mean(residual**2)),flush=True)
        return residual
    result=least_squares(fun,x0,bounds=([.85,.85,.98],[1.15,1.15,1.02]),
                         diff_step=1e-4,xtol=1e-6,ftol=1e-6,gtol=1e-6,max_nfev=40)
    return {'parameters':result.x.tolist(),'success':bool(result.success),'message':result.message,
            'cost':result.cost,'optimality':result.optimality,'nfev':result.nfev,
            'jacobian_singular_values':np.linalg.svd(result.jac,compute_uv=False).tolist()}


def milestones(history):
    results=[]
    for f in [.25,.5,.75]:
        goal=f*4.7625
        pair=next(((a,b) for a,b in zip(history,history[1:]) if a['front98_mm']<goal<=b['front98_mm']),None)
        if pair is None:results.append({'fraction':f,'reached':False});continue
        a,b=pair;w=(goal-a['front98_mm'])/(b['front98_mm']-a['front98_mm'])
        out={k:float(a[k]+w*(b[k]-a[k])) for k in ['time_s','outer_C','interface_C','hot_C','remaining_mm','removed_mm']}
        out.update(fraction=f,reached=True,front98_mm=goal)
        results.append(out)
    return results


def forecast(x,dt=.0125,refine=1,removal=True):
    model=RadialModel(k_scale=x[0],cp_scale=x[1],qcond_scale=x[2],refine=refine,removal=removal)
    final,history,_=model.run(model.initial(profiles[-1]),150,dt=dt,stop_front=.75*4.7625,record_dt=dt)
    return {'dt':dt,'refine':refine,'removal':removal,'history':history,'milestones':milestones(history),
            'max_energy_balance_relative':model.max_balance_error,'max_mass_balance_relative':model.max_mass_balance_error,
            'max_alpha_increment':model.max_alpha_increment,'steps':model.steps}


if __name__=='__main__':
    t=time.time()
    training=fit(5.,[1.,1.,1.])
    _,hist,comp,m=evaluate(training['parameters'],profiles[-1]['time_s'])
    trained={'fit':training,'history':hist,'comparisons':comp,
             'training_end_s':5.,'holdout_end_s':profiles[-1]['time_s']}
    (HERE/'fit_validation.json').write_text(json.dumps(trained,indent=2)+'\n')
    fitted=fit(profiles[-1]['time_s'],training['parameters'])
    _,hist,comp,m=evaluate(fitted['parameters'],profiles[-1]['time_s'])
    (HERE/'fit_all.json').write_text(json.dumps({'fit':fitted,'history':hist,'comparisons':comp},indent=2)+'\n')
    x=fitted['parameters']
    for name,kwargs in [('central',{}),('half_dt',{'dt':.00625}),('double_mesh',{'refine':2}),
                        ('fixed_geometry',{'removal':False})]:
        out=forecast(x,**kwargs)
        (HERE/f'forecast_{name}.json').write_text(json.dumps(out,indent=2)+'\n')
        print(name,out['milestones'],flush=True)
    print('Total wall seconds',time.time()-t,flush=True)
