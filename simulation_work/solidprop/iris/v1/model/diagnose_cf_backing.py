"""One-way T700/M21 material-point diagnosis on published CF thermal histories.

Integrate the competitive channels in Tranchard et al., Materials 10 (2017)
494, Table 5 and 470, Table 1. Preserve the alternative printed catalyst entry.
These kinetics do not feed gas loss or enthalpy back into the liner temperature.
"""
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from continuous_heating_campaign import digest
from ops import ROOT, atomic, disks, utc

SOURCES = ['https://doi.org/10.3390/ma10050494','https://doi.org/10.3390/ma10050470']
A = np.array([7.2193,5.3309e8])
E = np.array([58.7107e3,146.674e3])
N = np.array([1.1125,2.0825])
CHI = np.array([.554,.9479])
RGAS=8.314462618
FRACTIONS=[.01,.10,.50,.90,.999]
DENSITY_LOSS=(1575.-1165.)/1575.


def solve(times, temperatures, catalyst, max_step=.25, freq=A, rtol=2e-9):
    t=np.asarray(times)
    temp=np.asarray(temperatures)
    if t.shape!=temp.shape or len(t)<2 or not np.all(np.diff(t)>0.) or t[0]!=0.:
        raise ValueError('Expected a sampled increasing exposure history')
    if np.min(temp)<-273.15 or np.any(~np.isfinite(temp)):
        raise ValueError('Invalid temperature history')
    # Stop at the first 1000 C crossing used as the diagnostic ceiling.
    crossed=np.flatnonzero(temp>=1000.)
    end=t[-1]
    if crossed.size:
        j=crossed[0]
        if j==0: raise ValueError('History begins outside material scope')
        end=t[j-1]+(1000.-temp[j-1])*(t[j]-t[j-1])/(temp[j]-temp[j-1])
    def rhs(s,y):
        k=freq*np.exp(-E/(RGAS*(np.interp(s,t,temp)+273.15)))
        u,a2=y
        # u is -log of the fraction still available to both pathways.
        one,two=k*np.exp(-(N-1)*u)
        two*=1.+catalyst*a2
        return [one+two,two*math.exp(-u)]
    def crossing(f):
        def reached(s,y):
            return y[0]+math.log1p(-f)
        reached.terminal=f==FRACTIONS[-1]
        reached.direction=1
        return reached
    res=solve_ivp(rhs,(0.,end),(0.,0.),method='DOP853',rtol=rtol,atol=rtol*1e-4,
                  max_step=max_step,events=[crossing(f) for f in FRACTIONS])
    if not res.success: raise RuntimeError(res.message)
    progress=-np.expm1(-res.y[0])
    a2=res.y[1]
    if np.min(progress-a2)<-1e-10 or np.min(a2)<-1e-10 or np.max(progress)>1.:
        raise ValueError('Nonphysical partition of common reactant')
    records={}
    for f,roots,states in zip(FRACTIONS,res.t_events,res.y_events):
        if len(roots)==0:
            records[str(f)]=None
            continue
        s=float(roots[0])
        i=int(np.clip(np.searchsorted(t,s)-1,0,len(t)-2))
        extent2=float(states[0,1])
        records[str(f)]=dict(time_s=s,temperature_C=float(np.interp(s,t,temp)),
            heating_rate_C_per_min=float(60.*(temp[i+1]-temp[i])/(t[i+1]-t[i])),
            lost_fraction_of_original_composite=float(DENSITY_LOSS*(CHI@[f-extent2,extent2])))
    return records,float(progress[-1]),float(res.t[-1])


def main():
    disks()
    # Exact isothermal nth-order channel with the competing frequency set to zero.
    temp=500.
    horizon=500.
    const=solve([0.,horizon],[temp,temp],0.,max_step=1.,freq=np.array([A[0],0.]))
    beta=(1.+(N[0]-1.)*A[0]*math.exp(-E[0]/(RGAS*(temp+273.15)))*const[2])**(-1./(N[0]-1.))
    assert abs(const[1]-(1.-beta))<1e-9
    nominal=ROOT/'validation/moving_surface_campaign_audit.json'
    audit=json.loads(nominal.read_text())
    cases={}
    for case in ('sustainer_cf','booster_cf'):
        cases[case]={}
        for tag_suffix in ('moving320_time04','moving640_time04','moving640_time02'):
            tag=case+'_'+tag_suffix
            path=ROOT/'validation/moving_surface_cases'/f'{tag}.json'
            assert digest(path)==audit['records'][tag]['record_sha256']
            d=json.loads(path.read_text())
            hist=d['history']
            times=np.array([r['time_s'] for r in hist])
            outputs={}
            for key in ('interface_C','outer_C'):
                path_t=np.array([r[key] for r in hist])
                base,end_fraction,end=solve(times,path_t,7.4886)
                refined,_,_=solve(times,path_t,7.4886,max_step=.10,rtol=2e-10)
                other,_,_=solve(times,path_t,10**(-.8744))
                diffs=[]
                for f in base:
                    if base[f] is None:
                        assert refined[f] is None
                    else:
                        diffs.append(abs(base[f]['time_s']-refined[f]['time_s']))
                assert not diffs or max(diffs)<.002
                outputs[key]=dict(table5=refined,table3_log_alternative=other,
                    integration_check_max_shift_s=max(diffs,default=0.),terminal_progress=end_fraction,
                    end_time_s=end,heating_path_end_s=times[-1])
            cases[case][tag_suffix]=dict(thermal_history_sha256=digest(path),outputs=outputs)
    atomic(ROOT/'validation/cf_backing_one_way.json',dict(checked_utc=utc(),sources=SOURCES,
        material='T700/M21 inert-atmosphere literature surrogate',model_sha256=digest(Path(__file__)),
        moving_audit_sha256=digest(nominal),A_per_s=A.tolist(),E_J_per_mol=E.tolist(),n=N.tolist(),
        catalyst_table5=7.4886,catalyst_table3_log=-.8744,initial_and_residue_density_kg_m3=[1575.,1165.],
        analytic_single_channel_error=abs(const[1]-(1.-beta)),cases=cases,
        meaning='Conversion is fraction of common reactive pool. Reconstructed fractional composite mass loss uses '
                'published pathway weights. Surface histories are prescribed from the inert-backing nominal results. '
                'No feedback into the wall and no structural failure or updated liner time.'))
    for case,g in cases.items():
        for key,row in g['moving640_time02']['outputs'].items():
            print(case,key,{f: round(r['time_s'],2) if r else None for f,r in row['table5'].items()})


if __name__=='__main__': main()
