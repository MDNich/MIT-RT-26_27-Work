"""Read back sealed moving-wall results, physical ledgers, profiles and resolution."""
import bisect
import json

import numpy as np

from continuous_heating_campaign import digest
from moving_surface_campaign import PLAN, WORK, OUT, FLOWS, PARENT, VERIFICATION, decode, sources
from moving_surface_transient import Wall
from ops import ROOT, atomic, disks, utc


def audit_case(item,plan,sha,work=WORK,out=OUT):
    path = out/(item['tag']+'.json')
    cp_path = work/(item['tag']+'_checkpoint.json')
    data = json.loads(path.read_text())
    cp = json.loads(cp_path.read_text())
    assert cp['tag']==data['tag']==item['tag'] and cp['plan_sha256']==data['plan_sha256']==sha
    assert digest(cp_path)==data['checkpoint_sha256'] and not data['eligible_for_motor_lifetime']
    for name in ('history','profiles','stats','scope_bracket_s','event_bracket_s'):
        assert cp[name]==data[name]
    assert data['status']=='SURROGATE_EXHAUSTION' and data['post_scope']
    cfg = item['configuration']
    w = Wall(cfg,item['n'],item['nc'])
    final = decode(cp['state'])
    assert final.liner_edges.tolist()==[w.interface] and all(len(x)==0 for x in (final.virgin,final.char,final.enthalpy))
    h,profiles = data['history'],data['profiles']
    end,flag = data['event_bracket_s'],data['scope_bracket_s']
    assert 0<flag[0]<flag[1]<end[0]<end[1]==final.time==h[-1]['time_s']
    assert end[1]-end[0]<=item['dt']+1e-9 and flag[1]-flag[0]<=item['dt']+1e-9
    assert final.time<=plan['horizon_s'] and cp['ledger']==h[-1]['ledger']
    m0,H0 = w.inventory(w.initial())
    m,H = w.inventory(final)
    assert h[-1]['remaining_mm']==m==0 and abs(h[-1]['solid_sensible_J_per_rad_m']-H)<1e-8
    times = np.array([r['time_s'] for r in h])
    assert np.all(np.diff(times)>0) and np.all(np.diff([r['remaining_mm'] for r in h])<=1e-10)
    assert h[0]['time_s']==0 and abs(1000.*(w.interface-w.inner)-h[0]['remaining_mm'])<1e-10
    assert next(r for r in h if r['interface_C']>=cfg['case_property_limit_C'])['time_s']==flag[1]
    worst_m = worst_e = 0.
    for row in h:
        ledger = row['ledger']
        assert all(np.isfinite(val) for k,val in row.items() if k!='ledger') and all(np.isfinite(list(ledger.values())))
        assert abs(row['virgin_kg_per_rad_m']+row['char_kg_per_rad_m']-row['solid_mass_kg_per_rad_m'])<1e-11
        residual_m = row['solid_mass_kg_per_rad_m']+sum(ledger[k] for k in FLOWS[:3])-m0
        # Do not subtract swept sensible heat a second time: the mass carrying
        # it leaves the mesh and the wall balance credits it against products.
        residual_e = (row['solid_sensible_J_per_rad_m']-H0+ledger['outer_loss']+ledger['bulk_reaction']
                      +ledger['bulk_gas_heat']+ledger['face_reaction']+ledger['face_products_heat']
                      -ledger['film_heat']-ledger['radiation_heat'])
        worst_m = max(worst_m,abs(residual_m)/m0)
        worst_e = max(worst_e,abs(residual_e)/max(1.,abs(H0),abs(ledger['film_heat'])+abs(ledger['radiation_heat'])))
    assert worst_m < 1e-8 and worst_e < 1e-6
    assert data['stats']['max_mass_relative_error']<1e-8 and data['stats']['max_energy_relative_error']<1e-6
    for p in profiles:
        idx = np.argmin(abs(times-p['time_s']))
        assert abs(times[idx]-p['time_s'])<1e-9
        v,c,t,edges = [np.array(p[k]) for k in ('liner_virgin_kg_per_rad_m','liner_char_kg_per_rad_m','liner_temperature_C','liner_edges_m')]
        assert len(v)==len(c)==len(t)==len(edges)-1 and np.all(np.diff(edges)>0) and edges[-1]==w.interface
        assert np.all(v>=0) and np.all(c>=0)
        assert abs(sum(v+c)-h[idx]['solid_mass_kg_per_rad_m'])<1e-10
        assert abs((w.interface-edges[0])*1000.-h[idx]['remaining_mm'])<1e-9
    shared = np.arange(.5,end[1],.5)
    assert all(min(abs(times-t))<1e-9 for t in shared)
    return data,dict(tag=item['tag'],record_sha256=digest(path),checkpoint_sha256=digest(cp_path),
                event_bracket_s=end,scope_bracket_s=flag,max_sample_mass_relative_error=worst_m,
                max_sample_energy_relative_error=worst_e,terminal_temperature_C=float(final.case_C[0]))


def compare(a,b):
    # Only exact common reporting instants. First-scope and final-event samples
    # are generally different times and must not be treated as shared output.
    grid_a = {round(r['time_s'],9):r for r in a['history']}
    grid_b = {round(r['time_s'],9):r for r in b['history']}
    times = sorted(grid_a.keys() & grid_b.keys())
    def largest(key,after=0.):
        diff,time = max((abs(grid_a[t][key]-grid_b[t][key]),t) for t in times if t>=after)
        return dict(difference=diff,at_s=time)
    e1,e2 = a['event_bracket_s'],b['event_bracket_s']
    delta = e2[1]-e1[1]
    threshold = max(.02,.01*a['history'][0]['remaining_mm'])
    thickness = largest('remaining_mm')
    # Compare physical radial locations inside BOTH remaining domains at saved
    # profiles. Exclude endpoints outside either set of real cell centres.
    profiles = {round(p['time_s'],9):p for p in a['profiles']}
    worst_field = (0.,0.,0.)
    for p2 in b['profiles']:
        p1 = profiles.get(round(p2['time_s'],9))
        if p1 is None or min(len(p1['liner_temperature_C']),len(p2['liner_temperature_C']))<2: continue
        coords = []
        for p in (p1,p2):
            r = np.array(p['liner_edges_m'])
            coords.append(r[:-1]+np.diff(r)*(r[:-1]+2*r[1:])/(3*(r[:-1]+r[1:])))
        low,high=max(c[0] for c in coords),min(c[-1] for c in coords)
        points = np.unique(np.r_[coords[0],coords[1]])
        points = points[(points>=low)&(points<=high)]
        if not len(points): continue
        diff = abs(np.interp(points,coords[0],p1['liner_temperature_C'])-np.interp(points,coords[1],p2['liner_temperature_C']))
        i = np.argmax(diff)
        worst_field = max(worst_field,(float(diff[i]),p2['time_s'],float(points[i])))
    return dict(event_difference_s=delta,event_relative_percent=100.*abs(delta)/e2[1],
                event_under_5_percent=abs(delta)<.05*e2[1],brackets_overlap=max(e1[0],e2[0])<=min(e1[1],e2[1]),
                shared_samples=len(times),thickness_target_mm=threshold,remaining_mm=thickness,
                thickness_pass=thickness['difference']<=threshold,case_interface_K=largest('interface_C'),
                hot_face_including_initial_K=largest('face_C'),hot_face_from_half_second_K=largest('face_C',.5),
                max_liner_field_difference_K=worst_field[0],field_time_s=worst_field[1],field_radius_m=worst_field[2])


def main():
    disks()
    plan=json.loads(PLAN.read_text())
    sha=digest(PLAN)
    assert json.loads((WORK/'complete.json').read_text())['plan_sha256']==sha
    assert plan['sources']==sources() and digest(VERIFICATION)==plan['verification_sha256'] and digest(PARENT)==plan['parent_plan_sha256']
    baseline = {i['case']:i['configuration'] for i in json.loads(PARENT.read_text())['cases']}
    records,by_case,evidence = {},{},{}
    for item in plan['cases']:
        assert item['configuration']==baseline[item['case']] and item['nc']==item['n']//4
        data,rec = audit_case(item,plan,sha)
        by_case.setdefault(item['case'],{})[(item['n'],item['dt'])]=data
        evidence[item['tag']]=rec
    levels=[(160,.08),(160,.04),(320,.04),(640,.04),(640,.02)]
    for case,group in by_case.items():
        assert set(group)==set(levels)
        records[case]={f'{n0}_{d0:g}_to_{n1}_{d1:g}':compare(group[n0,d0],group[n1,d1])
                       for (n0,d0),(n1,d1) in zip(levels,levels[1:])}
    result=dict(checked_utc=utc(),plan_sha256=sha,audit_sha256=digest(__file__),
                cases_checked=len(evidence),records=evidence,comparisons=records,
                eligible_for_motor_lifetime=False,native_verified=False,
                qualification='Numerical verification of a continuously heated independent mathematical wall. '
                   'Property flags precede all events. Raw final-step brackets and sampled changes are assessed separately.')
    atomic(ROOT/'validation/moving_surface_campaign_audit.json',result)
    for case,group in by_case.items():
        print(case,group[640,.02]['event_bracket_s'],group[640,.02]['scope_bracket_s'],
              [(round(p['event_difference_s'],4),p['brackets_overlap'],round(p['remaining_mm']['difference'],4)) for p in records[case].values()])


if __name__=='__main__':
    main()
