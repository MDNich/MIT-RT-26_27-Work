"""Compare terminal native sustainer Al refinements at common geometry controls."""
import hashlib
import json
import matplotlib.pyplot as plt


def create(root, out, read, resolution):
    names = [
        ('sustainer_al_pulse7_midpoint_space160_geom005_smp10', '160/40 rows'),
        ('sustainer_al_pulse7_midpoint_joint320_geom005_smp10', '320/80 rows, half step'),
    ]
    if not resolution or not all(n in resolution['records'] for n, _ in names):
        return []
    pair = next(c for c in resolution['comparisons'] if c['fine'] == names[-1][0])
    assert pair['configuration_comparison']['kind'] == 'joint_mesh_time'
    assert pair['configuration_comparison']['physical_model_identical']
    records = []
    for name, label in names:
        summary = resolution['records'][name]
        accepted_path = root / 'validation' / f'accepted_{name}.json'
        assert hashlib.sha256(accepted_path.read_bytes()).hexdigest() == summary['accepted_record_sha256']
        audit = read(str(accepted_path.relative_to(root)))
        assert audit['passed'] and audit['status'] == 'COMPLETED_HORIZON'
        runtime = root / 'ansystmp/runs' / name
        assert hashlib.sha256((runtime / 'config.json').read_bytes()).hexdigest() == summary['config_sha256']
        history, digest = [], hashlib.sha256()
        for index in range(1, audit['accepted_steps'] + 1):
            blob = (runtime / 'checkpoints' / f'audit_{index:06d}.json').read_bytes()
            digest.update(index.to_bytes(8, 'big'))
            digest.update(hashlib.sha256(blob).digest())
            a = json.loads(blob)
            history.append({key: a[key] for key in ['time_s', 'Ts_mean_C',
                'case_inner_max_C', 'case_outer_max_C', 'phenolic_remaining_thickness_m',
                'rows_removed', 'rows_scheduled', 'hot_radius_m']})
        assert history[-1]['time_s'] == summary['through_s'] == 127.
        heating = [a for a in history if a['time_s'] <= 7 + 1e-8]
        assert abs(heating[-1]['time_s'] - 7) < 1e-8
        records.append(dict(runtime=name, label=label, history=history,
            hot_face_at_7s_C=heating[-1]['Ts_mean_C'],
            sampled_hot_face_peak=max(heating, key=lambda a:a['Ts_mean_C']),
            accepted_record_sha256=summary['accepted_record_sha256'],
            independent_comparison_sha256=summary['independent_comparison_sha256'],
            config_sha256=summary['config_sha256'], ordered_audit_hash_digest=digest.hexdigest()))
    fine_times = {round(a['time_s'], 8):a for a in records[1]['history']}
    matched = []
    for a in records[0]['history']:
        if a['time_s'] > 7 + 1e-8:
            break
        b = fine_times[round(a['time_s'], 8)]
        assert abs(a['time_s'] - b['time_s']) < 1e-8
        matched.append(dict(time_s=a['time_s'], difference_K=b['Ts_mean_C']-a['Ts_mean_C'],
            coarse_hot_face_C=a['Ts_mean_C'], fine_hot_face_C=b['Ts_mean_C'],
            coarse_rows_removed=a['rows_removed'], fine_rows_removed=b['rows_removed'],
            coarse_hot_radius_m=a['hot_radius_m'], fine_hot_radius_m=b['hot_radius_m']))
    worst = max(matched, key=lambda a:abs(a['difference_K']))
    assert worst['coarse_rows_removed'] == worst['fine_rows_removed'] == 0
    assert worst['coarse_hot_radius_m'] == worst['fine_hot_radius_m']
    delta7 = records[1]['hot_face_at_7s_C'] - records[0]['hot_face_at_7s_C']
    stem = 'native_sustainer_al_refinement'
    data = out / f'{stem}.json'
    data.write_text(json.dumps(dict(records=records, hot_face_at_7s_difference_K=delta7,
        max_matched_heating_difference=worst, comparison=pair,
        qualification='Terminal accepted native histories only. Common 0.05-degree sector, exact straight-sided measures, physical inputs and native tolerance. Radial resolution doubles while all coupling steps halve: a joint mesh/time comparison, not isolated spatial convergence, physical calibration or motor lifetime.'), separators=(',', ':')) + '\n')
    read(str(data.relative_to(root)))
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.2), constrained_layout=True)
    for record, color, style in zip(records, ['#aa632c', '#24547a'], ['--', '-']):
        h = record['history']; heating = [a for a in h if a['time_s'] <= 7 + 1e-8]
        axes[0].plot([a['time_s'] for a in heating], [a['Ts_mean_C'] for a in heating],
                     color=color, ls=style, lw=1.2, label=record['label'])
        axes[1].plot([a['time_s'] for a in h], [a['case_inner_max_C'] for a in h],
                     color=color, ls=style, lw=1.2, label=record['label'])
        peak = max(h, key=lambda a:a['case_inner_max_C'])
        axes[1].plot(peak['time_s'], peak['case_inner_max_C'], 'o', color=color, ms=3)
    axes[0].set(xlabel='Imposed heating time [s]', ylabel=r'Exposed phenolic mean [$^\circ$C]', xlim=(0, 7))
    axes[1].set(xlabel='Time since heating begins [s]', ylabel=r'Inner casing maximum [$^\circ$C]', xlim=(0, 127))
    axes[1].axvline(7, color='gray', ls=':', lw=.8)
    for ax in axes:
        ax.legend(fontsize=7)
    fig.suptitle('Sustainer aluminium: native joint mesh/time refinement')
    fig.savefig(out / f'{stem}.pdf')
    fig.savefig(out / f'{stem}.png', dpi=180)
    plt.close(fig)
    return [r'\subsubsection{Sustainer aluminium at common sector and solver settings}',
        'The 320/80-row native case completed 127 s with 8416 accepted intervals. Its physical inputs, '
        '0.05-degree sector, straight-sided area/volume measures and nonlinear tolerance match the 160/40-row case. '
        'Only radial resolution and coupling time steps change together. The sampled inner/outer casing peaks '
        'change by 1.605 K and retained mesh by 0.01488 mm, below the 5 K and 0.047625 mm targets. '
        'This supports the tested casing and thickness quantities for the imposed seven-second pulse; '
        'it does not separately estimate spatial and temporal errors.',
        f"The exposed phenolic mean at 7 s changes from {records[0]['hot_face_at_7s_C']:.3f} "
        f"to {records[1]['hot_face_at_7s_C']:.3f} degrees Celsius ({delta7:+.3f} K). "
        f"The largest absolute difference at shared heating samples is {abs(worst['difference_K']):.3f} K "
        f"at {worst['time_s']:.6f} s: {worst['coarse_hot_face_C']:.3f} versus "
        f"{worst['fine_hot_face_C']:.3f} degrees Celsius. Neither case has removed a row at that time; "
        'the difference occurs at the same hot-face radius and cannot be explained solely by a boundary jump. '
        'The coupled reaction, available-char consumption and thermal response remain sensitive to mesh/time '
        'resolution before removal. Later surface samples also follow different receding mesh boundaries. '
        'Agreement in casing peaks therefore does not establish convergence of the entire hot-face history. '
        'All three fine-grid row-removal times and subsequent load transfers agree exactly with its own '
        'same-mesh independent reference; its maximum sampled live-profile difference is 0.01505 K. '
        'That implementation check and the coarser-to-finer comparison answer different questions.',
        r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/' + stem +
        r'.pdf}\caption{Completed native sustainer aluminium histories with common geometry and solver controls. '
        r'Left: exposed phenolic mean during heating. Right: inner-casing temperature through the full cooling horizon; '
        r'dots mark sampled peaks. Radial cells double and coupling steps halve together. These are conditional numerical results, not measured motor temperatures or allowable firing times.}\end{figure}']
