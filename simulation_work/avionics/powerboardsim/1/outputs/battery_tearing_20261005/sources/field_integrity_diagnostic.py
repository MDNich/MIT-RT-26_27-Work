"""Audit export integrity without claiming physical acceptance of a case."""
from pathlib import Path
import numpy as np
import json, datetime, sys, hashlib

S = Path(__file__).resolve().parent.parent
D = S / 'runtime' / sys.argv[1]
assert (D / 'POST_PASSED.json').exists()
h = np.genfromtxt(D / 'history.csv', delimiter=',', names=True)
cfg = json.loads((D / 'config.json').read_text())
mesh = json.loads((D / 'mesh.json').read_text())
maxdamage = 0.
for row in h:
    step = int(row['step'])
    a = np.genfromtxt(D / f'damage_{step}.csv', delimiter=',', names=True)
    b = np.genfromtxt(D / f'nodes_{step}.csv', delimiter=',', names=True)
    assert len(a) == cfg['shell_elements'] and len(b) == mesh['pilot'] - 1
    assert np.array_equal(a['element'], np.arange(1, len(a) + 1))
    assert np.array_equal(b['node'], np.arange(1, len(b) + 1))
    assert all(np.all(np.isfinite(a[k])) for k in a.dtype.names)
    assert all(np.all(np.isfinite(b[k])) for k in b.dtype.names)
    for k in ('damage_top', 'damage_mid', 'damage_bot'):
        assert np.all(a[k] >= -1e-8) and np.all(a[k] <= 1 + 1e-6)
        maxdamage = max(maxdamage, float(np.max(a[k])))
audit = {
    'case': D.name, 'time': datetime.datetime.now().astimezone().isoformat(),
    'pull_states': len(h), 'all_expected_fields_present': True,
    'ids_counts_finite_values_damage_bounds': 'PASS',
    'maximum_exported_summary_damage': maxdamage,
    'qualification': 'Export integrity only. This is not physical acceptance, a force-balance audit, or evidence of geometric tearing.',
    'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
}
dest = D / 'FIELD_INTEGRITY_DIAGNOSTIC.json'
tmp = dest.with_suffix('.json.tmp')
tmp.write_text(json.dumps(audit, indent=2) + '\n')
tmp.replace(dest)
print(json.dumps(audit, indent=2))
