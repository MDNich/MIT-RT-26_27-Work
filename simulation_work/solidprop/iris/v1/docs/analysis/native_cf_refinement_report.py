"""Plot terminal, verified sustainer CF refinements without extending scope stops."""
import hashlib
import json
import matplotlib.pyplot as plt


def create(root, out, read, resolution):
    names = [
        ('sustainer_cf_pulse7_n80_midpoint_tight', '80 rows, original step'),
        ('sustainer_cf_pulse7_midpoint_time_quarter', '80 rows, quarter step'),
        ('sustainer_cf_pulse7_midpoint_space160_geom005_smp10', '160 rows, corrected sector'),
    ]
    if not resolution or not all(n in resolution['records'] for n, _ in names):
        return []
    records = []
    for name, label in names:
        summary = resolution['records'][name]
        accepted = root / 'validation' / f'accepted_{name}.json'
        assert hashlib.sha256(accepted.read_bytes()).hexdigest() == summary['accepted_record_sha256']
        audit = read(str(accepted.relative_to(root)))
        assert audit['passed'] and audit['status'] == 'CASE_PROPERTY_LIMIT_REACHED'
        runtime = root / 'ansystmp/runs' / name
        assert hashlib.sha256((runtime / 'config.json').read_bytes()).hexdigest() == summary['config_sha256']
        history = []
        digest = hashlib.sha256()
        for index in range(1, audit['accepted_steps'] + 1):
            p = runtime / 'checkpoints' / f'audit_{index:06d}.json'
            blob = p.read_bytes()
            digest.update(index.to_bytes(8, 'big'))
            digest.update(hashlib.sha256(blob).digest())
            a = json.loads(blob)
            history.append({key: a[key] for key in
                ['time_s', 'Ts_mean_C', 'case_inner_max_C', 'case_outer_max_C']})
        assert history[-1]['time_s'] == summary['through_s']
        records.append(dict(runtime=name, label=label, history=history,
            accepted_record_sha256=summary['accepted_record_sha256'],
            independent_comparison_sha256=summary['independent_comparison_sha256'],
            config_sha256=summary['config_sha256'],
            ordered_audit_hash_digest=digest.hexdigest()))
    data = out / 'native_sustainer_cf_refinement.json'
    data.write_text(json.dumps(dict(records=records,
        qualification='Terminal accepted native histories only. The 80-to-160 comparison changes radial mesh, sector geometry/measures and solver tolerance together. All curves stop at their material-scope flag; no later cooling peak or motor lifetime is inferred.'),
        separators=(',', ':')) + '\n')
    read(str(data.relative_to(root)))
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.2), constrained_layout=True)
    for record, color, style in zip(records, ['#777777', '#aa632c', '#24547a'], [':', '--', '-']):
        h = record['history']; heating = [a for a in h if a['time_s'] <= 7 + 1e-8]
        axes[0].plot([a['time_s'] for a in heating], [a['Ts_mean_C'] for a in heating],
                     color=color, ls=style, lw=1.2, label=record['label'])
        axes[1].plot([a['time_s'] for a in h], [a['case_inner_max_C'] for a in h],
                     color=color, ls=style, lw=1.2, label=record['label'])
        axes[1].plot(h[-1]['time_s'], h[-1]['case_inner_max_C'], 'x', color=color, ms=7)
    axes[0].set(xlabel='Imposed heating time [s]', ylabel=r'Exposed phenolic mean [$^\circ$C]', xlim=(0, 7))
    axes[1].set(xlabel='Time since heating begins [s]', ylabel=r'Inner casing maximum [$^\circ$C]')
    axes[1].axhline(150, color='#a63232', ls=':', lw=.8)
    axes[1].axvline(7, color='gray', ls=':', lw=.8)
    for ax in axes:
        ax.legend(fontsize=6.5)
    fig.suptitle('Sustainer CF native refinements: scope timing remains sensitive')
    fig.savefig(out / 'native_sustainer_cf_refinement.pdf')
    fig.savefig(out / 'native_sustainer_cf_refinement.png', dpi=180)
    plt.close(fig)
    return [r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/native_sustainer_cf_refinement.pdf}\caption{Accepted native sustainer CF histories. Lines join accepted samples; x marks each provisional 150-degree casing-property stop. Left: exposed phenolic during the seven-second heating pulse. Right: delayed inner-casing heating. The newer 160-row case also changes sector geometry/measures and solver tolerance, so its difference is not an isolated radial-mesh error. No curve is extended past its scope stop.}\end{figure}']
