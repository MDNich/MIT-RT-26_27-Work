"""Freeze an audited comparison prefix, never a terminal acceptance record."""
import argparse
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from ops import ROOT, TMP, atomic, disks
from coupler import fingerprint


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(path):
    disks()
    comparison = json.loads(path.read_text())
    assert comparison['comparison_passed'] and comparison['native_control_checks_passed']
    assert comparison['exact_row_schedule_identical'] and comparison['cooling_transition_passed']
    runtime = TMP / 'runs' / comparison['runtime']
    assert runtime.parent == TMP / 'runs'
    index = comparison['accepted_native_index']
    state_path = runtime / 'checkpoints' / f'state_{index:06d}.json.gz'
    state = json.loads(gzip.decompress(state_path.read_bytes()))
    cfg = json.loads((runtime / 'config.json').read_text())
    assert sha(runtime / 'config.json') == comparison['config_sha256']
    assert state['config_sha256'] == fingerprint(cfg)
    assert state['index'] == index
    assert abs(state['time_s'] - comparison['accepted_native_time_s']) < 1e-8
    manifest = json.loads((runtime / 'input_manifest.json').read_text())
    for name, wanted in manifest.items():
        assert sha(runtime / name) == wanted, name
    assert sha(ROOT / 'model' / 'radial_model.py') == comparison['model_sha256']
    audits = []
    previous = 0.
    g = cfg['geometry']
    pitch = g['phenolic_thickness_m'] / g['phenolic_radial_rows']
    digest = hashlib.sha256()
    for i in range(1, index + 1):
        p = runtime / 'checkpoints' / f'audit_{i:06d}.json'
        a = json.loads(p.read_text())
        digest.update(f'{i}:{sha(p)}\n'.encode())
        assert a['time_s'] > previous and abs(a['time_s'] - previous - a['dt_s']) < 1e-8
        assert a['energy_relative_error'] <= cfg['numerics']['energy_relative_tolerance']
        assert a['hot_power_relative_error'] <= cfg['numerics']['hot_power_relative_tolerance']
        assert abs(a['mass_residual_kg']) <= max(1e-13, 1e-6 * state['mass_initial_kg'])
        assert a['hot_faces'] == g['faces_per_row']
        assert math.isclose(a['phenolic_remaining_thickness_m'], (g['phenolic_radial_rows'] - a['rows_scheduled']) * pitch, abs_tol=1e-12)
        assert a['rows_scheduled'] in [a['rows_removed'], a['rows_removed'] + 1]
        assert a['native_live_elements_before_solve'] == cfg['expected_elements'] - a['rows_removed'] * g['faces_per_row']
        assert a['native_load_step'] == i and a['native_substep'] == 1
        previous = a['time_s']
        audits.append(a)
    assert abs(previous - state['time_s']) < 1e-8
    for sample in comparison['comparisons']:
        assert sample['index'] <= index
        assert sha(runtime / 'checkpoints' / f'state_{sample["index"]:06d}.json.gz') == sample['native_state_sha256']
    result = dict(
        frozen_utc=datetime.now(timezone.utc).isoformat(),
        status='VERIFIED_PREFIX_ONLY_TERMINAL_PENDING',
        qualification='Audited immutable prefix and selected independent comparison times. The running calculation, terminal logs/restarts, full casing peak and spatial convergence pair are not yet accepted.',
        comparison_source_sha256=sha(path), comparison=comparison,
        native_prefix_audit=dict(
            passed=True, steps=index, time_s=state['time_s'],
            max_energy_relative_error=max(a['energy_relative_error'] for a in audits),
            max_hot_power_relative_error=max(a['hot_power_relative_error'] for a in audits),
            max_abs_mass_residual_kg=max(abs(a['mass_residual_kg']) for a in audits),
            audit_sequence_sha256=digest.hexdigest(), checkpoint_sha256=sha(state_path),
            sealed_input_manifest_sha256=sha(runtime / 'input_manifest.json'),
            all_sealed_inputs_match=True, final_audit=audits[-1]))
    atomic(ROOT / 'validation' / 'native_geometry_control_prefix.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('comparison', type=Path)
    args = parser.parse_args()
    result = freeze(args.comparison)
    print(json.dumps({k: v for k, v in result.items() if k != 'comparison'}, indent=2))
