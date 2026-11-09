"""Match the final global force residual at each accepted preload substep to the pocket force."""
import re

import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from stage_snug_fit import AUDIT, input_record


NUMBER = r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?'
FORCE = re.compile(r'^\s*FORCE CONVERGENCE VALUE\s*=\s*('+NUMBER+r')\s+CRITERION=\s*('+NUMBER+r')(.*)$')
ACCEPT = re.compile(r'SOLUTION CONVERGED AFTER EQUILIBRIUM ITERATION\s+(\d+)')
DONE = re.compile(r'\*\*\* LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED\.\s+CUM ITER =\s*(\d+)')
TIME = re.compile(r'\*\*\* TIME =\s*('+NUMBER+r')\s+TIME INC')


def accepted_substeps(listing):
    """Use only the force line associated with the final accepted Newton iteration."""
    rows = []
    force = accepted = completed = None
    for line in listing.splitlines():
        match = FORCE.match(line)
        if match:
            force = (float(match[1]), float(match[2]), '<<< CONVERGED' in match[3])
            accepted = None
        match = ACCEPT.search(line)
        if match:
            assert force and force[2] and 0 <= force[0] <= force[1]
            accepted = (int(match[1]), force[0], force[1])
        match = DONE.search(line)
        if match:
            assert accepted and completed is None
            completed = tuple(map(int,match.groups()))
        match = TIME.search(line)
        if match and completed is not None:
            step, substep, cumulative = completed
            iterations, residual, criterion = accepted
            rows.append(dict(step=step, substep=substep, cumulative_iterations=cumulative,
                             final_attempt_iterations=iterations, load_time=float(match[1]),
                             force_residual_N=residual, force_criterion_N=criterion))
            force = accepted = completed = None
    assert rows and completed is None
    return rows


def audit(case, campaign):
    archive = ROOT/'.runtime/archive'/campaign/case
    receipt = ROOT/'.runtime/receipts'/campaign/case
    ledger = read(receipt/'archived.json')
    assert ledger['case']==case and ledger['campaign']==campaign and (receipt/'released.txt').is_file()
    files = {item['name']:item['sha256'] for item in ledger['files']}
    record = input_record(case)
    assert files['model.inp']==record['input_sha256']
    contact_path = AUDIT/(case+'_contacts.json')
    contact = read(contact_path)
    assert contact['case']==case and contact['campaign']==campaign and contact['rst_sha256']==files['file.rst']
    assert contact['native_force_csv_sha256']==files['snug_contact_force.csv']
    for name in ('solve.out','file.mntr','snug_contact_force.csv'):
        verified(archive/name,files[name])
    rows = accepted_substeps((archive/'solve.out').read_text(errors='replace'))
    monitor = {}
    for line in (archive/'file.mntr').read_text().splitlines():
        fields = line.split()
        if len(fields)>=8 and all(v.isdigit() for v in fields[:5]):
            step, substep, attempt, iters, total = map(int,fields[:5])
            monitor[step,substep,total] = (attempt,iters,float(fields[6]))
    for row, surface, resultant in zip(rows, contact['contact_history'], contact['resultant_force_check'],strict=True):
        step, substep = row['step'], row['substep']
        attempt, iterations, t = monitor[step,substep,row['cumulative_iterations']]
        assert iterations==row['final_attempt_iterations'] and step==surface['loadstep']
        assert np.isclose(t,surface['load_time'],rtol=5e-5,atol=1e-8)
        assert np.isclose(row['load_time'],surface['load_time'],rtol=5e-6,atol=1e-8)
        assert surface['native_set']==resultant['native_set']
        if 'absolute_force_criterion_N' in record:
            assert np.isclose(row['force_criterion_N'],record['absolute_force_criterion_N'],rtol=1e-5,atol=0)
        row.update(native_set=surface['native_set'],attempt=attempt,pocket_resultant_N=resultant['resultant_N'])
    assert rows[-1]['load_time']==2. and any(r['load_time']==1. for r in rows)
    write_json(AUDIT/(case+'_residuals.json'),dict(case=case,campaign=campaign,
        input_sha256=files['model.inp'],rst_sha256=files['file.rst'],listing_sha256=files['solve.out'],
        monitor_sha256=files['file.mntr'],contact_audit_sha256=digest(contact_path),states=rows,
        interpretation='The global L2 force imbalance and the local resultant are different quantities. '
                       'A same-mesh tolerance rerun measures sensitivity of the pocket force to the stopping criterion.'))


if __name__=='__main__':
    import sys
    audit(*sys.argv[1:])
