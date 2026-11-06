"""Read back Al phase, checkpoints, budgets, profiles and paired refinements."""
import json

import numpy as np

import aluminium_backing_campaign as c
from aluminium_backing_wall import AluminiumBackingWall
from aluminium_phase_enthalpy import REFERENCE_H, SOLID_H, LIQUID_H, TO_SPECIFIC
from audit_moving_surface import compare
from continuous_heating_campaign import digest
from moving_surface_thermochemistry import sensible
from ops import ROOT, atomic, disks, utc


def audit_case(item, plan, sha):
    tag=item['tag']
    path=c.OUT/f'{tag}.json'
    cp_path=c.WORK/f'{tag}_checkpoint.json'
    data=json.loads(path.read_text())
    cp=json.loads(cp_path.read_text())
    assert data['plan_sha256']==cp['plan_sha256']==sha and data['checkpoint_sha256']==digest(cp_path)
    assert data['tag']==cp['tag']==tag and data['status']=='SURROGATE_EXHAUSTION'
    assert data['eligible_for_motor_lifetime'] is False
    for key in ('events','stats','profiles','history'): assert data[key]==cp[key]
    cfg=item['configuration']
    w=AluminiumBackingWall(cfg,item['n'],item['nc'])
    m0,h0=w.inventory(w.initial())
    state=c.nominal.decode(cp['state'])
    m,h=w.inventory(state)
    history,events=data['history'],data['events']
    assert len(state.char)==len(state.virgin)==len(state.enthalpy)==0 and state.liner_edges.tolist()==[w.interface]
    assert m==0 and abs(h-history[-1]['solid_sensible_J_per_rad_m'])<1e-8 and cp['ledger']==history[-1]['ledger']
    assert events['exhaustion']==data['event_bracket_s'] and events['property_flag']==data['scope_bracket_s']
    times=np.array([r['time_s'] for r in history])
    assert times[0]==0. and np.all(np.diff(times)>0.) and times[-1]==state.time==events['exhaustion'][1]
    assert all(np.min(abs(times-t))<1e-9 for t in np.arange(.5,state.time,.5))
    assert all(np.diff([r['remaining_mm'] for r in history])<=1e-10)
    assert state.time<=plan['horizon_s'] and history[-1]['remaining_mm']==0.
    assert abs(history[0]['remaining_mm']-1000*(w.interface-w.inner))<1e-10
    checks={'property_flag':lambda r:r['interface_C']>=cfg['case_property_limit_C'],
            'first_melt':lambda r:r['max_cell_liquid']>0.,
            'all_liquid':lambda r:r['min_cell_liquid']>=1.,
            'exhaustion':lambda r:r['remaining_mm']==0.}
    for name,test in checks.items():
        first=next((r for r in history if test(r)),None)
        bracket=events[name]
        if first is None:
            assert bracket is None
        else:
            assert bracket[0]<bracket[1]==first['time_s'] and bracket[1]-bracket[0]<=item['dt']+1e-9
    assert events['property_flag'][1]<events['first_melt'][0]<events['exhaustion'][0]
    peak_m=peak_h=0.
    for r in history:
        led=r['ledger']
        assert np.isfinite([v for k,v in r.items() if k!='ledger']).all() and np.isfinite(list(led.values())).all()
        assert 0.<=r['min_cell_liquid']<=r['mass_fraction_liquid']+1e-13
        assert r['mass_fraction_liquid']<=r['max_cell_liquid']+1e-13 and r['max_cell_liquid']<=1.
        dm=r['virgin_kg_per_rad_m']+r['char_kg_per_rad_m']+sum(led[k] for k in c.nominal.FLOWS[:3])-m0
        dh=r['solid_sensible_J_per_rad_m']-h0+sum(led[k] for k in c.nominal.FLOWS[5:10])-led['film_heat']-led['radiation_heat']
        peak_m=max(peak_m,abs(dm)/m0)
        peak_h=max(peak_h,abs(dh)/max(1.,abs(h0),abs(led['film_heat'])+abs(led['radiation_heat'])))
    assert max(peak_m,data['stats']['max_mass_relative_error'])<1e-8
    assert max(peak_h,data['stats']['max_energy_relative_error'])<1e-6
    for p in data['profiles']:
        j=np.argmin(abs(times-p['time_s']))
        assert abs(times[j]-p['time_s'])<1e-9
        row=history[j]
        v,ch,t,e=(np.array(p[k]) for k in ('liner_virgin_kg_per_rad_m','liner_char_kg_per_rad_m','liner_temperature_C','liner_edges_m'))
        assert len(t)==len(e)-1==len(v)==len(ch) and all(v>=0) and all(ch>=0) and np.all(np.diff(e)>0)
        assert abs(sum(v+ch)-row['solid_mass_kg_per_rad_m'])<1e-10 and abs((w.interface-e[0])*1000-row['remaining_mm'])<1e-9
        assert np.array_equal(p['casing_edges_m'],w.case_edges)
        al_h=w.casing(np.array(p['casing_cell_C']))[0]
        molar=al_h/TO_SPECIFIC+REFERENCE_H
        mass_liquid=w.case_mass@np.clip((molar-SOLID_H[-1])/(LIQUID_H[0]-SOLID_H[-1]),0.,1.)
        assert abs(mass_liquid/w.case_mass.sum()-row['mass_fraction_liquid'])<2e-12
        phases=sensible(t)
        total=v@phases[:,0]+ch@phases[:,1]+w.case_mass@al_h
        assert abs(total-row['solid_sensible_J_per_rad_m'])<1e-7
    return data,dict(record_sha256=digest(path),checkpoint_sha256=digest(cp_path),events=events,
                terminal_liquid_mass_fraction=history[-1]['mass_fraction_liquid'],
                max_sample_mass_relative_error=peak_m,max_sample_energy_relative_error=peak_h)


def main():
    disks()
    plan=json.loads(c.PLAN.read_text())
    sha=digest(c.PLAN)
    assert plan['sources']==c.sources() and plan['coupon_sha256']==digest(c.COUPON) and plan['parent_sha256']==digest(c.nominal.PLAN)
    done=json.loads((c.WORK/'complete.json').read_text())
    assert done['cases']==len(plan['cases']) and done['plan_sha256']==sha
    parent=json.loads(c.nominal.PLAN.read_text())
    base_items={p['tag']:p for p in parent['cases']}
    records,groups,pairs,departures={},{},{},{}
    for item in plan['cases']:
        cfg=item['configuration'].copy()
        width=cfg.pop('al_fusion_width_K')
        assert cfg==base_items[item['nominal_tag']]['configuration']
        d,records[item['tag']]=audit_case(item,plan,sha)
        groups.setdefault(item['case'],{})[(item['n'],item['dt'],width)]=d
        if width==.5:
            path=c.nominal.OUT/(item['nominal_tag']+'.json')
            ref=json.loads(path.read_text())
            audit=json.loads((ROOT/'validation/moving_surface_campaign_audit.json').read_text())
            assert audit['records'][item['nominal_tag']]['record_sha256']==digest(path)
            departures[item['case']]=dict(previous_sha256=digest(path),reference_event_s=ref['event_bracket_s'][1],
                with_fusion_s=d['events']['exhaustion'][1],shift_s=d['events']['exhaustion'][1]-ref['event_bracket_s'][1])
    levels=[(320,.04,2.),(640,.04,2.),(640,.02,2.),(640,.02,1.),(640,.02,.5)]
    for case,rows in groups.items():
        assert set(rows)==set(levels)
        pairs[case]={}
        for key,l,r in zip(('mesh','time','width_2_to_1','width_1_to_half'),levels,levels[1:]):
            left,right=rows[l],rows[r]
            p=compare(left,right)
            p['phase_event_shifts_s']={name:(right['events'][name][1]-left['events'][name][1]
                if left['events'][name] and right['events'][name] else None) for name in c.MILESTONES}
            pairs[case][key]=p
    atomic(ROOT/'validation/aluminium_backing_audit.json',dict(checked_utc=utc(),plan_sha256=sha,
        audit_sha256=digest(__file__),records=records,comparisons=pairs,nominal_departures=departures,
        qualification='Numerical results for thermally retained pure-Al caloric surrogates, inherited conductivity. Mechanical loss is outside this study.'))
    print(json.dumps(departures,indent=2))


if __name__=='__main__': main()
