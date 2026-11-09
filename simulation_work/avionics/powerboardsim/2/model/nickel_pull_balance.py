"""Apply the October nickel-damage equilibrium checks to every saved lateral-pull state."""
import argparse
from pathlib import Path

import numpy as np

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json


OUT = ROOT/'validation/damage_balance'
LIMITS = dict(relative_x=.001, abs_y_N=.01, abs_z_N=.1)


def screen(sets, travel, cell_fx, residual):
    sets=np.asarray(sets)
    assert len(sets)>0 and np.all(np.diff(sets)>0) and np.array_equal(sets,sets.astype(int))
    assert residual.shape==(len(sets),3) and travel.shape==cell_fx.shape==sets.shape
    assert np.isfinite(residual).all() and np.isfinite(travel).all() and np.isfinite(cell_fx).all()
    values=abs(residual).copy()
    values[:,0]/=np.maximum(1.,abs(cell_fx))
    failed=values>=np.array(list(LIMITS.values()))
    def station(i):
        return dict(native_set=int(sets[i]),pull_row=int(i)+1,travel_mm=float(travel[i]),
                    cell_fx_N=float(cell_fx[i]),signed_residual_xyz_N=residual[i].tolist())
    where=np.flatnonzero(failed.any(axis=1))
    first=int(where[0]) if len(where) else len(sets)
    return dict(pull_states=len(sets),limits=LIMITS,maximum=dict(zip(LIMITS,values.max(0).tolist(),strict=True)),
                failing_counts=dict(zip(LIMITS,failed.sum(0).tolist(),strict=True)),all_states_within_limits=not len(where),
                consecutive_passes_before_failure=first,last_consecutive_pass=station(first-1) if first else None,
                first_failed_station=station(first) if len(where) else None)


def extra_reactions(rows):
    """Supports added to the October cell-and-four-clamp balance in the cased fixtures."""
    if 'screw_support_N_x' not in rows.dtype.names:
        return np.zeros((len(rows),3))
    stems=['screw_support_N','neighbor_support_N']
    stems.extend(name[:-2] for name in rows.dtype.names if name.startswith('seat') and name.endswith('_support_N_x'))
    return np.column_stack([sum(rows[f'{stem}_{axis}'] for stem in stems) for axis in 'xyz'])


def native_check(folder, balance_file, campaign, start):
    case=folder.name
    receipt=ROOT/'.runtime/receipts'/campaign/case
    ledger=read(receipt/'archived.json')
    assert (receipt/'released.txt').is_file() and ledger['case']==case and ledger['campaign']==campaign
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    for name in ('local_job.json','set_inventory.csv','tear.rst','balance.csv','history.csv'):
        verified(folder/name,hashes[name])
    inventory=table(folder/'set_inventory.csv')
    inventory=inventory[inventory['time']>start+1e-9]
    states=table(balance_file)
    states=states[states['time']>start+1e-9]
    original=table(folder/'balance.csv')
    history=table(folder/'history.csv')
    assert np.array_equal(inventory['set'],states['native_set'])
    assert np.array_equal(original['step'],np.arange(1,len(states)+1)) and np.array_equal(history['step'],original['step'])
    assert np.allclose(history['time'],states['time'],atol=1e-7,rtol=0)
    assert np.allclose(states['cell_fx_N'],inventory['fx_N'],atol=1e-5,rtol=1e-7)
    restored=np.column_stack([states['force_N_'+a] for a in 'xyz'])
    old_supports=np.column_stack([original['r'+a+'_N'] for a in 'xyz'])
    added_supports=extra_reactions(states)
    assert np.allclose(restored-added_supports,old_supports,atol=1e-6,rtol=1e-7)
    report=screen(states['native_set'],states['ux_mm'],states['cell_fx_N'],restored)
    report.update(case=case,campaign=campaign,rst_sha256=hashes['tear.rst'],
                  archived_POST1_balance_sha256=hashes['balance.csv'],inventory_sha256=hashes['set_inventory.csv'],
                  recovered_fixture_balance_sha256=digest(balance_file),max_POST1_difference_N=float(
                      np.abs(old_supports+added_supports-restored).max()),
                  scope='External X, Y and Z force residuals during lateral loading. This check preserves the '
                        'historical damage-fixture limits. Material, contact, moments and rupture need their own evidence.')
    write_json(OUT/(case+'.json'),report)
    if not report['all_states_within_limits']:
        state=report['first_failed_station']
        raise ValueError(f"Nickel pull equilibrium failed at native set {state['native_set']}, "
                         f"travel {state['travel_mm']:.7g} mm. See validation/damage_balance/{case}.json.")
    return report


def verify_references(archive):
    data={}
    for case in ('continuous_proof','cont_nominal','cont_force5em5','cont_force5em5_snapshot04','cont_fine_snapshot02'):
        folder=archive/'outputs/battery_tearing_20261005/runtime'/case
        balance=table(folder/'balance.csv')
        history=table(folder/'history.csv')
        inventory=table(folder/'set_inventory.csv')
        inventory=inventory[inventory['loadstep']>=3]
        assert np.array_equal(balance['step'],history['step']) and len(balance)==len(inventory)
        assert np.allclose(history['time'],inventory['time'],atol=1e-7,rtol=0)
        assert np.allclose(history['ux_mm'],inventory['ux_mm'],atol=1e-7,rtol=0)
        residual=np.column_stack([balance['r'+k+'_N'] for k in 'xyz'])
        checked=screen(inventory['set'],history['ux_mm'],history['fx_N'],residual)
        rejection=folder/'REJECTED_BALANCE_AUDIT.json'
        assert checked['all_states_within_limits']==(not rejection.exists())
        if rejection.exists():
            receipt=rejection
            rejected=read(receipt)
            if 'z_failures' in rejected:
                rows=[r['pull_step'] for r in rejected['z_failures']]
            elif 'violating_rows' in rejected:
                rows=[int(r['step']) for r in rejected['violating_rows']]
            else:
                rows=np.flatnonzero(abs(residual[:,2])>=LIMITS['abs_z_N'])+1
                assert len(rows)==rejected['rejected_z_states']
                assert np.isclose(checked['first_failed_station']['travel_mm'],rejected['first_failed_z_ux_mm'])
                assert np.isclose(checked['maximum']['abs_z_N'],rejected['max_abs_z_residual_N'])
            assert np.array_equal(rows,np.flatnonzero(abs(residual[:,2])>=LIMITS['abs_z_N'])+1)
        else:
            receipt=folder/('ACCEPTED.json' if case=='continuous_proof' else 'CONVERGED_STATES_AUDIT.json')
            original=read(receipt)
            for name,key in [('relative_x','max_lateral_relative_balance'),('abs_y_N','max_y_balance_N'),('abs_z_N','max_z_balance_N')]:
                assert np.isclose(checked['maximum'][name],original[key],rtol=1e-8,atol=1e-12)
        checked['source_sha256']={p.name:digest(p) for p in (folder/'set_inventory.csv',folder/'balance.csv',folder/'history.csv',receipt)}
        data[case]=checked
    write_json(OUT/'october_controls.json',dict(cases=data,
        scope='Independent replay of archived pull-balance classifications. Rejected endpoints and snapshots '
              'are retained as negative controls. A row passing force balance alone is not a qualified damage result.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('october_archive',type=Path)
    verify_references(parser.parse_args().october_archive)
