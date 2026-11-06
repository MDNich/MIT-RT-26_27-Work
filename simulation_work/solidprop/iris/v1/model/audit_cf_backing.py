"""Independently read back CF inventory, thermodynamics, event intervals and numerical pairs."""
import json
from pathlib import Path
import tempfile

import numpy as np

from audit_moving_surface import compare
import cf_backing_campaign as c
from continuous_heating_campaign import digest
from moving_surface_thermochemistry import sensible
from ops import ROOT,TMP,atomic,disks,utc


def read_case(item,plan,sha):
    tag=item['tag']
    path=c.OUT/(tag+'.json')
    cp_path=c.WORK/(tag+'_checkpoint.json')
    d=json.loads(path.read_text())
    cp=json.loads(cp_path.read_text())
    assert cp['tag']==d['tag']==tag and cp['plan_sha256']==d['plan_sha256']==sha
    assert d['checkpoint_sha256']==digest(cp_path) and d['eligible_for_motor_lifetime'] is False
    assert d['status']=='SURROGATE_EXHAUSTION'
    for field in ('events','stats','history','profiles'): assert cp[field]==d[field]
    cfg=item['configuration']
    g=cfg['geometry']
    e0,ei,eo=(g[k] for k in ('inner_radius_m','phenolic_outer_radius_m','outer_radius_m'))
    case_edges=np.linspace(ei,eo,item['nc']+1)
    m0=1575.*np.diff(case_edges)*(case_edges[:-1]+case_edges[1:])/2.
    liner0=cfg['material']['virgin_reference_density_kg_m3']*(ei-e0)*(ei+e0)/2.
    times=np.array([r['time_s'] for r in d['history']])
    assert times[0]==0. and np.all(np.diff(times)>0.) and times[-1]==cp['state']['time']<=plan['horizon_s']
    assert all(min(abs(times-t))<1e-8 for t in np.arange(.5,times[-1],.5))
    assert d['history'][0]['remaining_mm']==1000*(ei-e0) and d['history'][-1]['remaining_mm']==0.
    assert np.max(np.diff([r['remaining_mm'] for r in d['history']]))<=1e-10
    assert d['event_bracket_s']==d['events']['exhaustion'] and d['scope_bracket_s']==d['events']['property_flag']
    checks=dict(property_flag=lambda r:r['interface_C']>=cfg['case_property_limit_C'],
                inner_pool_half=lambda r:r['inner_pool']>=.5,outer_pool_half=lambda r:r['outer_pool']>=.5,
                first_1000C=lambda r:r['max_backing_C']>=1000.,exhaustion=lambda r:r['remaining_mm']==0.)
    for key,test in checks.items():
        row=next((r for r in d['history'] if test(r)),None)
        bracket=d['events'][key]
        if row is None: assert bracket is None
        else: assert bracket[1]==row['time_s'] and 0.<bracket[1]-bracket[0]<=item['dt']+1e-8
    by_time={r['time_s']:r for r in d['history']}
    peak_mass=peak_heat=0.
    for r in d['history']:
        led=r['ledger']
        assert np.isfinite([v for k,v in r.items() if k!='ledger']).all() and np.isfinite(list(led.values())).all()
        assert 0<=r['outer_pool']<=1+1e-12 and 0<=r['inner_pool']<=1+1e-12
        assert r['backing_retained_kg_per_rad_m']>0. and led['backing_gas']>=0.
        dm1=abs(r['virgin_kg_per_rad_m']+r['char_kg_per_rad_m']+sum(led[k] for k in c.parent.FLOWS[:3])-liner0)/liner0
        dm2=abs(r['backing_retained_kg_per_rad_m']+led['backing_gas']-sum(m0))/sum(m0)
        dh=(r['solid_sensible_J_per_rad_m']-d['history'][0]['solid_sensible_J_per_rad_m']+sum(led[k] for k in c.parent.FLOWS[5:10])
            +led['backing_gas_heat']-led['backing_reaction_heat']-led['film_heat']-led['radiation_heat'])
        peak_mass=max(peak_mass,dm1,dm2)
        peak_heat=max(peak_heat,abs(dh)/max(1.,abs(led['film_heat'])+abs(led['radiation_heat'])))
    assert max(peak_mass,d['stats']['max_mass_relative_error'])<1e-8 and max(peak_heat,d['stats']['max_energy_relative_error'])<1e-6
    # Direct piecewise polynomial antiderivative from the Part I properties.
    def enthalpy(t,coeff,hi):
        z=np.clip(t,20.,hi)
        return sum(a*(z**(j+1)-22.**(j+1))/(j+1)+(t-z)*a*z**j for j,a in enumerate(coeff))
    last_paths=np.zeros((2,item['nc']))
    for prof in d['profiles']:
        row=by_time[prof['time_s']]
        p=np.array(prof['backing_paths']); temp=np.array(prof['casing_cell_C'])
        assert p.shape==last_paths.shape and temp.shape==m0.shape
        assert np.all(p>=last_paths-1e-12) and np.all(p.sum(axis=0)<=1.+1e-12) and np.array_equal(prof['casing_edges_m'],case_edges)
        assert abs(sum(p[:,0])-row['inner_pool'])<1e-12 and abs(sum(p[:,-1])-row['outer_pool'])<1e-12
        x=.554*p[0]+.9479*p[1]
        m=m0*(1.-410.*x/1575.)
        assert abs(sum(m)-row['backing_retained_kg_per_rad_m'])<1e-10
        hc=(1.-x)*enthalpy(temp,[687.31,2.8773],300.)+x*enthalpy(temp,[662.53,2.599,-.0020761,5.1327e-7],1000.)
        v,ch,t,e=(np.array(prof[k]) for k in ('liner_virgin_kg_per_rad_m','liner_char_kg_per_rad_m','liner_temperature_C','liner_edges_m'))
        assert np.all(np.diff(e)>0.) and len(v)==len(ch)==len(e)-1 and np.all(v>=0) and np.all(ch>=0)
        assert abs(sum(v+ch)-row['solid_mass_kg_per_rad_m'])<1e-11 and abs(1000.*(ei-e[0])-row['remaining_mm'])<1e-9
        h=sensible(t)
        assert abs(m@hc+v@h[:,0]+ch@h[:,1]-row['solid_sensible_J_per_rad_m'])<1e-6
        last_paths=p
    state=cp['state']
    assert state['liner_edges']==[ei] and all(state[k]==[] for k in ('virgin','char','enthalpy'))
    assert state['case_C']==d['profiles'][-1]['casing_cell_C'] and cp['paths']==d['profiles'][-1]['backing_paths']
    assert cp['ledger']==d['history'][-1]['ledger'] and times[-1]==d['events']['exhaustion'][1]
    return d,dict(sha256=digest(path),checkpoint_sha256=digest(cp_path),max_mass_relative_error=peak_mass,
                  max_energy_relative_error=peak_heat,events=d['events'],final_backing_loss_fraction=1.-sum(m)/sum(m0))


def restart_check(plan,sha):
    # This deliberately warm, short job exercises both reaction channels and
    # the serialized arrays. Its event history is excluded from motor results.
    import copy
    job=copy.deepcopy(plan['cases'][0])
    job.update(n=10,nc=5,dt=.02,tag='warm_restart_coupon')
    job['configuration'].update(initial_temperature_C=475.)
    short={**plan,'horizon_s':.2,'profile_times_s':[.1,.2]}
    with tempfile.TemporaryDirectory(dir=TMP) as tmp:
        a,b=Path(tmp)/'a',Path(tmp)/'b'
        for path in (a,b): path.mkdir()
        assert c.run_case(job,short,sha,a,a)
        assert not c.run_case(job,short,sha,b,b,pause_after=8)
        stopped=json.loads((b/'status.json').read_text())
        assert stopped['status']=='PAUSED' and 0.<stopped['time_s']<.2
        assert c.run_case(job,short,sha,b,b)
        for suff in ('.json','_checkpoint.json'):
            assert (a/(job['tag']+suff)).read_bytes()==(b/(job['tag']+suff)).read_bytes()
        rec=json.loads((a/(job['tag']+'.json')).read_text())
        assert rec['history'][-1]['ledger']['backing_gas']>0.
        return dict(interruption_s=stopped['time_s'],end_s=.2,terminal_bytes_identical=True)


def main():
    disks()
    plan=json.loads(c.PLAN.read_text()); sha=digest(c.PLAN)
    assert plan['sources']==c.sources() and plan['parent_sha256']==digest(c.parent.PLAN) and plan['coupon_sha256']==digest(c.COUPON)
    complete=json.loads((c.WORK/'complete.json').read_text())
    assert complete['plan_sha256']==sha and complete['cases']==len(plan['cases'])
    nominal=json.loads((ROOT/'validation/moving_surface_campaign_audit.json').read_text())
    records,groups,departures,pairs={},{},{},{}
    base={r['tag']:r for r in json.loads(c.parent.PLAN.read_text())['cases']}
    for item in plan['cases']:
        cfg=item['configuration'].copy(); catalyst=cfg.pop('cf_catalyst')
        assert cfg==base[item['nominal_tag']]['configuration']
        assert abs(catalyst-(10**(-.8744) if item['variant']=='alternate' else 7.4886))<1e-12
        d,records[item['tag']]=read_case(item,plan,sha)
        groups.setdefault(item['case'],{})[item['variant']]=d
        if item['variant']=='fine':
            path=c.parent.OUT/(item['nominal_tag']+'.json')
            assert digest(path)==nominal['records'][item['nominal_tag']]['record_sha256']
            old=json.loads(path.read_text())['event_bracket_s'][1]
            departures[item['case']]=dict(inert_s=old,coupled_s=d['event_bracket_s'][1],shift_s=d['event_bracket_s'][1]-old)
    for case,rows in groups.items():
        assert set(rows)=={'mesh','time','fine','alternate'}
        pairs[case]={name:compare(rows[left],rows[right]) for name,left,right in
                    [('mesh','mesh','time'),('time','time','fine'),('catalyst_sensitivity','fine','alternate')]}
    result=dict(utc=utc(),auditor_sha256=digest(__file__),plan_sha256=sha,records=records,
                comparisons=pairs,nominal_departures=departures,restart=restart_check(plan,sha),
                scope='Audited independent oxygen-free retained CF material comparison. Native continuous verification pending.')
    atomic(ROOT/'validation/cf_backing_audit.json',result)
    print(json.dumps(departures))


if __name__=='__main__': main()
