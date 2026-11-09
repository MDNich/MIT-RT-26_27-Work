"""Exercise the reporting threshold against the archived continuous October pull without a new solve."""
import sys
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from nickel_damage import summarize


def check(archive):
    source = read(ROOT/'validation/local_inputs.json')['damage_cont_nominal']
    folder = archive/source['source_path']
    for name, sha in source['files'].items():
        verified(folder/name, sha)
    pilot = read(folder/'mesh.json')['pilot']
    r = reader.read_binary(str(folder/'tear.rst'))
    inventory = table(folder/'set_inventory.csv')
    kinematics = table(folder/'history.csv')
    cfg = read(folder/'config.json')
    states = []
    for i, ((ls, ss, _), t) in enumerate(zip(r._resultheader['ls_table'], r.time_values, strict=True)):
        if ss == 999999:
            continue
        row = inventory[len(states)]
        assert (int(row['set']), int(row['loadstep']), int(row['substep'])) == (i+1, ls, ss)
        f, nodes, dofs = r.nodal_reaction_forces(i)
        pilot_fx = f[(nodes == pilot) & (dofs == 1)].sum()
        ux = np.clip(t-cfg['pull_start_time'], 0., cfg['displacement_mm'])
        states.append(dict(native_set=i+1, time=float(t), ux_mm=float(ux), cell_fx_N=float(pilot_fx)))
    pulled = inventory[inventory['time'] > cfg['pull_start_time']]
    for field in ('ux_mm', 'fx_N', 'time'):
        assert np.allclose(pulled[field], kinematics[field], rtol=1e-7, atol=1e-7)
    assert np.allclose(pulled['damage'], np.maximum.reduce([kinematics[x] for x in ('dtop','dmid','dbot')]), atol=1e-8)
    result = summarize(inventory, states)
    bracket = result['damage_onset_bracket']
    assert [p['native_set'] for p in bracket] == [100,101]
    assert np.allclose([p['cell_ux_mm'] for p in bracket], [3.250,3.275], atol=1e-7)
    assert np.allclose([p['cell_fx_N'] for p in bracket], [42.870,43.372], atol=5e-4, rtol=0)
    result.update(converged_native_sets=len(states), excluded_diagnostic_sets=r.nsets-len(states),
                  source=source['source_path'], source_hashes={f:digest(folder/f) for f in ('tear.rst','set_inventory.csv','history.csv')},
                  scope='October bare fixture with the continuous nominal nickel law. The bracket measures modeled damage onset. The archived path ended before separation.')
    write_json(ROOT/'validation/october_damage_reference.json', result)


if __name__ == '__main__':
    check(Path(sys.argv[1]))
