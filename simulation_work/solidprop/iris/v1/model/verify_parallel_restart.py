"""Compare the accepted one/ten-core continuation of the same native checkpoint."""
import gzip
import hashlib
import json
from ops import ROOT, TMP, atomic, disks, guest, utc


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    disks()
    reference = TMP/'runs/booster_cf_core_restart_reference1'
    successor = TMP/'runs/booster_cf_pulse7_midpoint_time_quarter_smp10'
    lineage = json.loads((successor/'restart_lineage.json').read_text())
    ref_lineage = json.loads((reference/'restart_lineage.json').read_text())
    assert lineage['native_restart_sha256'] == ref_lineage['native_restart_sha256']
    assert lineage['copied_prefix_sha256'] == ref_lineage['copied_prefix_sha256']
    accepted = ROOT/'validation/accepted_booster_cf_core_restart_reference1.json'
    assert json.loads(accepted.read_text())['passed']
    configs = [json.loads((r/'config.json').read_text()) for r in (reference, successor)]
    assert [c['ranks'] for c in configs] == [1, 10]
    assert all(c['parallel_mode'] == 'smp' for c in configs)
    # Only execution identity and the short reference horizon may differ.
    for c in configs:
        for key in ('ranks', 'windows_root', 'host_runtime', 'end_time_s', 'campaign_role'):
            c.pop(key, None)
        c['provenance'].pop('parallel_execution_parent')
    assert configs[0] == configs[1]
    for filename in ('model_base.inp','mesh_map.json','material_v0.apdl',
                     'export_fields.mac','coupler.py','usermatth.F','usermatthLib.dll'):
        assert sha(reference/filename) == sha(successor/filename), filename
    end = json.loads((reference/'state.json').read_text())['index']
    assert json.loads((successor/'state.json').read_text())['index'] >= end
    maxima = {}
    files = []

    def compare(x, y, field):
        assert type(x) == type(y), field
        if isinstance(x, dict):
            assert x.keys() == y.keys(), field
            for k in x:
                compare(x[k], y[k], field)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            difference = abs(x-y)
            maxima[field] = max(maxima.get(field, 0), difference)
            # Strict repeatability gate; physical acceptance gates are separate.
            assert difference <= (1e-8 if 'temperature' in field or '_C' in field else 1e-12), field
        else:
            assert x == y, field

    for index in range(lineage['accepted_index']+1, end+1):
        for kind in ('state', 'audit'):
            name = f'{kind}_{index:06d}.json' + ('.gz' if kind == 'state' else '')
            paths = [r/'checkpoints'/name for r in (reference, successor)]
            if kind == 'state':
                with gzip.open(paths[0], 'rt') as f: a = json.load(f)
                with gzip.open(paths[1], 'rt') as f: b = json.load(f)
                a.pop('config_sha256'); b.pop('config_sha256')
            else:
                a, b = [json.loads(p.read_text()) for p in paths]
                for audit in (a, b):
                    assert audit['energy_relative_error'] <= configs[0]['numerics']['energy_relative_tolerance']
                    assert audit['hot_power_relative_error'] <= configs[0]['numerics']['hot_power_relative_tolerance']
                    assert audit['native_load_step'] == index and audit['native_substep'] == 1
                    assert audit['native_live_elements_before_solve'] == configs[0]['expected_elements']
            # Reference stops at its short horizon; production continues.
            a.pop('status'); b.pop('status')
            assert a.keys() == b.keys()
            for key in a:
                compare(a[key], b[key], kind+'_'+key)
            files.append(dict(name=name, reference_sha256=sha(paths[0]), successor_sha256=sha(paths[1])))
    native_root = json.loads((successor/'config.json').read_text())['windows_root']
    script = "$r='"+native_root+"';$p=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^ANSYS(261)?\\.exe$'}|Select-Object ProcessId,Name,CommandLine);"
    script += "$e=@(Get-ChildItem -LiteralPath $r -Filter 'solve_*.out'|ForEach-Object{Select-String -LiteralPath $_.FullName -Pattern 'SHARED MEMORY PARALLEL REQUESTED','SINGLE PROCESS WITH','TOTAL OF.*CORES REQUESTED'}|ForEach-Object{$_.Line.Trim()});"
    script += "@{processes=$p;native_log_lines=$e}|ConvertTo-Json -Depth 4"
    evidence = json.loads(guest(script))
    assert any('10 THREADS REQUESTED' in x for x in evidence['native_log_lines'])
    assert any('10 CORES REQUESTED' in x for x in evidence['native_log_lines'])
    assert any('-smp -np 10' in (p['CommandLine'] or '') and native_root in p['CommandLine'] for p in evidence['processes'])
    result = dict(checked_utc=utc(),passed=True,reference=reference.name,successor=successor.name,
        restart_index=lineage['accepted_index'],restart_time_s=lineage['accepted_time_s'],
        compared_steps=end-lineage['accepted_index'],last_compared_index=end,
        last_compared_time_s=json.loads((reference/'state.json').read_text())['time_s'],
        maximum_absolute_differences=maxima,checkpoint_hashes=files,
        reference_acceptance_sha256=sha(accepted),restart_lineage_sha256=sha(successor/'restart_lineage.json'),
        native_execution_evidence=evidence,
        qualification='Native one-core versus ten-core repeatability over 32 resumed heating steps. This interval contains no row deletion or cooling transition; all later production audits and independent comparisons remain mandatory. No performance speedup is inferred.')
    atomic(ROOT/'validation/parallel_restart_comparison.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('checkpoint_hashes','maximum_absolute_differences','native_execution_evidence')},indent=2))


if __name__ == '__main__':
    main()
