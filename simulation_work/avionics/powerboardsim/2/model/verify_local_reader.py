"""Cross-check binary support reactions against the archived native POST1 equilibrium exports."""
import argparse
import json
from pathlib import Path

import numpy as np

from local_equilibrium import recover, reference_movements

ROOT = Path(__file__).resolve().parents[1]


def max_difference(path, rows, keys, columns):
    reference = np.loadtxt(path, delimiter=',', skiprows=1, ndmin=2)
    actual = np.array([[row[key] for key in keys] for row in rows])
    return float(np.max(np.abs(reference[:, columns] - actual)))


def verify(archive):
    cases = []
    for name in ('friction_locked','friction_locked_minus','friction_locked_fine','grip_lagrange'):
        folder = archive / 'outputs/battery_side_pull_20261005/runtime' / name
        source = ROOT / '.runtime/local_inputs' / ('lateral_'+name)
        rows = recover(folder/'pull.rst', source, reference_movements(folder,source))
        errors = dict(force_N=max_difference(folder/'balance.csv', rows, ['force_N_'+a for a in 'xyz'], [-3,-2,-1]),
                      pilot_force_N=max_difference(folder/'history.csv', rows, ['cell_fx_N'], [3]))
        if (folder/'moment_balance.csv').is_file():
            errors['moment_Nmm'] = max_difference(folder/'moment_balance.csv', rows, ['moment_origin_Nmm_'+a for a in 'xyz'], [-3,-2,-1])
        if errors['force_N']>1e-5 or errors['pilot_force_N']>1e-5 or errors.get('moment_Nmm',0.)>.001:
            raise ValueError(f'{name} differs from native POST1: {errors}')
        cases.append(dict(case=name,converged_sets=len(rows),maximum_absolute_difference=errors))
    out=dict(scope='Archived bare fixtures. Native POST1 support translations, sparse RST reactions, and force and moment balance on physical supports.', cases=cases)
    (ROOT/'validation/local_equilibrium_reader.json').write_text(json.dumps(out,indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    verify(parser.parse_args().archive)
