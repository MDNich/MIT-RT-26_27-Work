"""Report audited independent early-heating mesh/time diagnostics."""
import hashlib
import matplotlib.pyplot as plt


def create(root, out, read):
    d = read('validation/early_surface_resolution.json')
    if not d or not d['complete']:
        return []
    assert d['independent_only'] and len(d['results']) == 6
    for source, path in d['archived_sources'].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == d['source_hashes'][source]
    records = {x['tag']: x for x in d['results']}
    for x in records.values():
        assert x['max_energy_error'] < 1e-6 and x['max_mass_error'] < 1e-8
        assert abs(x['history'][-1]['time_s'] - 2) < 1e-8
        assert all(a['layer'] == 0 and not a['case_property_range_exceeded'] for a in x['history'])
    def sample(tag, t):
        return next(x['hot_C'] for x in records[tag]['samples'] if abs(x['time_s'] - t) < 1e-8)
    timed = [abs(sample(f'n{n}_tight_dt', 1.24375)-sample(f'n{n}_native_dt', 1.24375)) for n in [160, 320]]
    fixed_mesh_difference = sample('n320_tight_dt', 1.24375)-sample('n160_tight_dt', 1.24375)
    last = sample('n1280_tight_dt', 1.24375)-sample('n640_tight_dt', 1.24375)
    stem = 'independent_early_surface_resolution'
    fig, ax = plt.subplots(figsize=(8.5, 2.9), constrained_layout=True)
    for n, color, style in zip([160, 320, 640, 1280], ['#aa632c', '#24547a', '#39845b', '#845392'], ['--', '-', '-.', ':']):
        rec = records[f'n{n}_tight_dt']; h = rec['history']
        ax.plot([a['time_s'] for a in h], [a['hot_C'] for a in h],
                color=color, ls=style, lw=1.3, label=f'{n} liner cells; dt={rec["dt_s"]:.7f} s')
    ax.axvline(1.24375, color='gray', ls=':', lw=.8)
    ax.set(xlabel='Time since imposed heating begins [s]', ylabel=r'Exposed phenolic [$^\circ$C]', xlim=(0, 2),
           title='Independent early-heating mesh checks; no layer removal')
    ax.legend(fontsize=7)
    fig.savefig(out / f'{stem}.pdf'); fig.savefig(out / f'{stem}.png', dpi=180); plt.close(fig)
    rows = []
    for x in d['results']:
        tag = x['tag']
        rows.append(f"{x['phenolic_rows']}/{x['casing_rows']} & {x['dt_s']:.8f} & "
                    f"{sample(tag,1.24375):.3f} & {sample(tag,2):.3f} " + r'\\')
    return [r'\subsection{Independent diagnosis of the early surface discrepancy}',
        'Six short independent calculations isolate the first two seconds of the sustainer Al heating model. '
        'They use the same physical inputs as the completed native 320/80-row case, retain the same '
        'surface-consumption rule, and do not modify any native package. Every calculation completes 2 s '
        'without row removal or a casing-property flag. Maximum relative equation-balance residuals are '
        f"{max(x['max_energy_error'] for x in d['results']):.3g} for energy and "
        f"{max(x['max_mass_error'] for x in d['results']):.3g} for mass. At the three shared sampling times, "
        'the matching 160- and 320-row independent cases reproduce the accepted native surface temperatures '
        f"within {max(abs(x['difference_K']) for x in d['native_spot_checks']):.5f} K.",
        r'\begin{table}[H]\centering\scriptsize\begin{tabular}{rrrr}\toprule Liner/casing cells & Step [s] & Surface at 1.24375 s [$^\circ$C] & Surface at 2 s [$^\circ$C]\\\midrule',
        '\n'.join(rows), r'\bottomrule\end{tabular}\caption{Independent early-heating results, not new ANSYS runs. The first and third rows match the completed native schedules; other rows are diagnostic refinements.}\end{table}',
        f"At the disputed 1.24375 s sample, reducing the step at fixed mesh changes the 160- and 320-row "
        f"values by only {timed[0]:.3f} and {timed[1]:.3f} K. At the common smaller step, their radial-mesh "
        f"difference remains {fixed_mesh_difference:.3f} K. The 640-to-1280-row pair still changes this sample "
        f"by {last:.3f} K; that last pair also quarters the step and is explicitly a joint comparison. "
        'The large early discrepancy is therefore predominantly a mesh effect in these tests, rather than '
        'a native/reference mismatch or a whole-row transfer jump. No complete hot-face convergence claim follows.',
        'The implemented available-char cap uses the mass and mean conversion of the current surface row. '
        'Refinement changes that mass, the sampled reaction state and their coupled surface energy sink. '
        'These checks do not isolate one term as the sole cause or calibrate this cell-based removal closure. '
        'Passing casing-peak and retained-mesh targets does not settle this local surface-history sensitivity. '
        'The two-second diagnostics are neither a longer firing calculation nor a burnthrough-time estimate.',
        r'\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/' + stem +
        r'.pdf}\caption{Independent early surface histories for the smaller-step mesh checks. The vertical line marks the disputed sample. The 160/320/640-cell curves share one time step; the 1280-cell curve uses a step four times smaller. No material row has been removed anywhere in these histories.}\end{figure}']
