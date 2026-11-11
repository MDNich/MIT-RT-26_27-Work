"""Compare independently balanced work on the same native nylon/aluminium pull stations."""
from audit_local import read
from compare_snug_middle_engagement import OUTPUT as TRANSFER
from film_identity import digest, verified, write_json
from snug_pull_steps import ENERGY as NYLON_ENERGY
from stage_snug_fit import AUDIT

ALUMINIUM_ENERGY = AUDIT/'snug125_aluminium_lateral_friction_locked_pin1_m15_ls3_ss15_energy.json'
OUTPUT = AUDIT/'forward_screw_energy_comparison.json'


def compare():
    transfer = read(TRANSFER)
    sources, records, by_set = {}, {}, {}
    for material, path in [('nylon', NYLON_ENERGY), ('aluminium', ALUMINIUM_ENERGY)]:
        energy = read(path)
        checkpoint = path.with_name(path.name.replace('_energy.json', '_checkpoint.json'))
        verified(checkpoint, energy['checkpoint_sha256'])
        proof = read(checkpoint)
        assert proof['rst_sha256'] == energy['cased']['rst_sha256']
        assert energy['bare']['rst_sha256'] == transfer['bare_rst_sha256']
        state = {r['native_set']: r for r in proof['states']}
        by_set[material] = {r['native_set']: r for r in energy['cased']['history']}
        for row in transfer['common_native_travel']:
            old = row[material]; k = old['native_set']; current = by_set[material][k]
            assert state[k] == old and current['within_parent_screens']
            assert abs(current['travel_mm']-old['travel_mm']) < 1e-10
            assert abs(current['cell_force_N']-old['cell_force_N']) < 1e-8
        sources[material] = dict(energy_path=str(path.relative_to(AUDIT.parent.parent)),
                                 energy_sha256=digest(path), checkpoint_sha256=digest(checkpoint),
                                 rst_sha256=proof['rst_sha256'])
        records[material] = energy
    assert records['nylon']['bare'] == records['aluminium']['bare']
    rows = []
    for match in transfer['common_native_travel']:
        k = match['nylon']['native_set']
        records_at = {m: by_set[m][k] for m in by_set}
        for material, row in records_at.items():
            assert abs(row['force_work_balance_error_mJ']) < .001
            for component in ('PLA', 'shanks'):
                # Retain the existing energy audit's 2% + 0.0002 mJ elastic-work screen.
                stored = row['stiffness_energy_change_mJ'][component]
                assert abs(row['work_by_group_mJ'][component]-stored) < .02*abs(stored)+2e-4
        i = next(i for i, r in enumerate(records['nylon']['cased']['history']) if r['native_set']==k)
        bare = records['nylon']['bare_work_at_cased_stations'][i]
        rows.append(dict(native_set=k, travel_mm=match['travel_mm'], bare=bare, **records_at))
    assert rows[-1]['native_set'] == transfer['last_common_native_set'] == 22
    scope = ('Saved-equilibrium trapezoidal external work and independently assembled nodal-force work. '
             'Both branches use identical pre-contact and common travel stations, ending before the refined nylon coupon crossing. '
             'PLA and shank stiffness energies are elastic storage; frictionless net contact work includes enforcement and finite-step effects. '
             'Equal-load work interpolates a force-travel segment and retains its native endpoint bracket; this is not an impact-absorption rating.')
    result = dict(transfer_sha256=digest(TRANSFER), sources=sources, common=rows,
                  equal_force={m: r['at_bare_endpoint_force'] for m, r in records.items()},
                  bare_endpoint=records['nylon']['bare']['history'][-1], scope=scope)
    write_json(OUTPUT,result)
    print('Equal-force work [mJ]:', {m:r['external_work_mJ'] for m,r in result['equal_force'].items()})
    for row in rows[-2:]:
        print(row['travel_mm'], {m: row[m]['actuator_work_mJ'] for m in by_set})


if __name__ == '__main__':
    compare()
