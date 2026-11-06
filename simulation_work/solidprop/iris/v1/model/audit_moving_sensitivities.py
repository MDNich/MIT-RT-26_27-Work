"""Verify varied fields against the nominal plan and audit the independent wall ledgers."""
import copy
import json

from audit_moving_surface import audit_case
from continuous_heating_campaign import digest
from moving_surface_campaign import PLAN as NOMINAL, sources
from moving_surface_sensitivities import PLAN, WORK, OUT, AUDIT, cases
from ops import ROOT, atomic, disks, utc


def main():
    disks()
    plan=json.loads(PLAN.read_text()); sha=digest(PLAN)
    assert json.loads((WORK/'complete.json').read_text())['plan_sha256']==sha
    assert plan['sources']==sources() and plan['worker_sha256']==digest(ROOT/'model/moving_surface_sensitivities.py')
    assert plan['parent_plan_sha256']==digest(NOMINAL) and plan['nominal_audit_sha256']==digest(AUDIT)
    assert plan['inherited_scenarios_sha256']==digest(ROOT/'model/run_input_sensitivities.py')
    base={i['case']:i for i in json.loads(NOMINAL.read_text())['cases'] if i['n']==320}
    nominal=json.loads(AUDIT.read_text())['records']
    answers={case:{} for case in base}
    for item in plan['cases']:
        case,name = item['case'],item['scenario']
        x=copy.deepcopy(base[case]['configuration'])
        expected=dict(cases(case))[name]
        assert item['changes']==expected and name not in answers[case]
        for section,patch in expected.items():
            target=x if section=='root' else x[section]
            target.update(patch)
        assert x==item['configuration'] and (item['n'],item['nc'],item['dt'])==(320,80,.04)
        _,record=audit_case(item,plan,sha,WORK,OUT)
        record['departure_from_same_mesh_nominal_s']=record['event_bracket_s'][1]-nominal[base[case]['tag']]['event_bracket_s'][1]
        answers[case][name]=record
    extremes={}
    for case,rows in answers.items():
        assert set(rows)==set(dict(cases(case)))
        ordered=sorted(rows,key=lambda name:rows[name]['event_bracket_s'][1])
        extremes[case]=[ordered[0],ordered[-1]]
    atomic(ROOT/'validation/moving_surface_sensitivity_audit.json',dict(checked_utc=utc(),plan_sha256=sha,
           audit_sha256=digest(__file__),common_audit_sha256=digest(ROOT/'model/audit_moving_surface.py'),
           records=answers,extreme_scenarios=extremes,physical_lifetime=False,
           qualification='One-factor assumed-input comparisons at one mesh/step setting. '
                         'Scope flags and mathematical intact-backing events recorded separately.'))
    for case,(lo,hi) in extremes.items():
        print(case,lo,answers[case][lo]['event_bracket_s'][1],hi,answers[case][hi]['event_bracket_s'][1])


if __name__=='__main__': main()
