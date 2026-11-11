"""Compare the two closed nominal damage runs, retaining their numerical limits."""
import re

import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from report_plot import plt


def closed(material_name, expected_states, expected_first):
    case = f'snug125_{material_name}_damage_cont_nominal_pin1_m15'
    audit = ROOT / 'validation/snug125'
    receipt = ROOT / '.runtime/receipts/nov08_01' / case
    folder = ROOT / '.runtime/archive/nov08_01' / case
    verdict_path = ROOT / 'validation/partial_local' / (case + '.json')
    verdict = read(verdict_path)
    status = read(receipt / 'status.json')
    ledger = read(receipt / 'archived.json')
    hashes = {r['name']: r['sha256'] for r in ledger['files']}
    assert (receipt / 'released.txt').exists() and status['phase'] == 'solver_complete'
    assert status['exit'] == 1 and not status['native_clean'] and not verdict['full_requested_path']
    for name in ('model.inp', 'tear.rst', 'solve.out'):
        verified(folder / name, hashes[name])
    listing = (folder / 'solve.out').read_text(errors='replace')
    assert 'substep 999999' in listing and 'RUN COMPLETED' in listing
    if material_name == 'nylon':
        stop = re.search(r'Solution not converged at time ([\d.]+) \(load step (\d+) substep (\d+)\)', listing)
        assert stop
        termination = dict(reason='Native nonconvergence', rejected_time=float(stop[1]),
                           rejected_load_step=int(stop[2]), rejected_substep=int(stop[3]))
    else:
        assert re.search(r'REASON FOR TERMINATION\.[^\n]*ERROR IN ELEMENT FORMULATION', listing)
        final_error = listing.rsplit('*** ERROR ***', 1)[1]
        assert 'Element 1865 has excessive thickness change.' in final_error
        assert 'time 2.5 substep 999999' in final_error
        termination = dict(reason='Native element-formulation error: excessive shell thickness change',
                           element=1865, rejected_load_step=4, rejected_substep=7,
                           diagnostic_time=2.5)
    paths = dict(pair=audit / (case + '_matched_damage.json'),
                 material=ROOT / 'validation/pull_material' / (case + '.json'),
                 limits=ROOT / 'validation/pulls' / (case + '_damage_scope.json'),
                 balance=ROOT / 'validation/damage_balance' / (case + '.json'),
                 initiation=audit / (case + '_nickel_initiation.json'),
                 evolution=audit / (case + '_nickel_evolution.json'))
    pair, material, limits, balance, initiation, evolution = [read(paths[k]) for k in paths]
    assert pair['fixture_sha256'][1] == limits['fixture_audit_sha256'] == digest(verdict_path)
    assert pair['mounted_material_scope_sha256'] == digest(paths['limits'])
    assert limits['material_audit_sha256'] == digest(paths['material'])
    assert balance['all_states_within_limits']
    assert balance['rst_sha256'] == verdict['rst_sha256'] == hashes['tear.rst']
    assert initiation['verdict_sha256'] == evolution['verdict_sha256'] == digest(verdict_path)
    assert initiation['field_replay_verified'] and initiation['native_evolution_sha256'] == digest(paths['evolution'])
    assert evolution['native_converged_sets'] == verdict['states'] == expected_states
    assert evolution['excluded_diagnostic_sets'] == 1
    first = min(limits['first_criterion_sets'].values())
    key = next(k for k, v in limits['first_criterion_sets'].items() if v == first)
    crossing = material['first_reference_crossings'][key]
    assert first == expected_first and evolution['supported_sets'] == first - 1
    assert evolution['last_supported']['native_max_point_damage'] == 0
    assert not evolution['reconstruction_checked_at_positive_damage']
    assert pair['snug_onset_within_recorded_screens'] is None
    nickel = verdict['damage_onset_bracket']
    assert nickel[0]['native_set'] > first and verdict['damage_reporting_threshold'] == 1e-4
    output = dict(case=case, input_sha256=hashes['model.inp'], rst_sha256=hashes['tear.rst'],
                  listing_sha256=hashes['solve.out'], status_sha256=digest(receipt / 'status.json'),
                  archive_manifest_sha256=digest(receipt / 'archived.json'),
                  fixture_sha256=digest(verdict_path), source_sha256={k: digest(p) for k, p in paths.items()},
                  termination=termination, no_restart_in_finite_scope=True,
                  converged_states=expected_states, excluded_diagnostic_sets=1,
                  last_converged_travel_mm=verdict['last_ux_mm'], all_saved_force_checks_pass=True,
                  first_PLA_criterion=key,
                  first_PLA_reference_bracket_mm=[crossing['last_below_mm'], crossing['first_above_mm']],
                  nickel_reporting_bracket=nickel, maximum_recorded_section_damage=verdict['peak_damage'],
                  last_parent_screened=evolution['last_supported'],
                  last_screened_initiation_criterion=initiation['native_trace'][-1][3],
                  positive_damage_reconstruction_verified=False,
                  equal_force_reference_N=pair['equal_force_reference_N'],
                  equal_force_travel=pair['at_reference_force'])
    return output, pair


def run():
    nylon, npair = closed('nylon', 28, 23)
    aluminium, apair = closed('aluminium', 23, 18)
    assert npair['at_reference_force']['bare'] == apair['at_reference_force']['bare']
    assert npair['equal_force_reference_N'] == apair['equal_force_reference_N']
    assert npair['histories'][0] == apair['histories'][0]
    for key in ('mesh_sha256', 'washer_preload_N', 'nickel_thickness_mm', 'washer_friction', 'yield_MPa'):
        assert len({h[key] for p in (npair, apair) for h in p['histories']}) == 1
    assert npair['inputs_sha256'] == apair['inputs_sha256']
    fig, (load, events) = plt.subplots(1, 2, figsize=(8.2, 2.5), layout='constrained',
                                     gridspec_kw={'width_ratios': [1, 1.35]})
    for y, row, label, color in [(2, npair['at_reference_force']['bare'], 'Bare', '#08357E'),
                                 (1, nylon['equal_force_travel']['snug'], 'Nylon', '#38761D'),
                                 (0, aluminium['equal_force_travel']['snug'], 'Aluminium', '#FF7F0E')]:
        lo, hi = [r['travel_mm'] for r in row['bracket']]
        x = row['travel_mm']
        load.errorbar(x, y, xerr=np.array([[x-lo], [hi-x]]), fmt='o', color=color, capsize=5, lw=2, ms=5)
        load.annotate(f'{x:.2f} mm', xy=(x, y), xytext=(0, 9), textcoords='offset points',
                      ha='center', fontsize=9, color=color)
    load.set(yticks=[0, 1, 2], yticklabels=['Aluminium', 'Nylon', 'Bare'], ylim=(-.5, 2.6), xlim=(0, .24),
             xlabel='Cell travel [mm]', title='Same nominal nickel law, 8.5 N')
    labels = []
    for base, record, name in [(2, nylon, 'Nylon'), (0, aluminium, 'Aluminium')]:
        for offset, values, label, color in [(1, record['first_PLA_reference_bracket_mm'], 'PLA', '#7A0101'),
                (0, [r['cell_ux_mm'] for r in record['nickel_reporting_bracket']], 'nickel', '#5A43A0')]:
            a, b = values
            y = base + offset
            events.plot([a, b], [y, y], color=color, lw=4)
            events.plot([a, b], [y, y], linestyle='none', marker='|', color=color, ms=10)
            text = f'{a:.2f}--{b:.2f} mm' if label == 'PLA' else f'About {b:.2f} mm'
            events.annotate(text, xy=((a+b)/2, y), xytext=(0, 7), textcoords='offset points',
                            ha='center', fontsize=9, color=color)
            labels.append((y, f'{name}: {label}'))
    labels.sort()
    events.set(yticks=[r[0] for r in labels], yticklabels=[r[1] for r in labels], ylim=(-.55, 3.65),
               xlim=(.235, .375), xticks=[.25, .30, .35], xlabel='Cased cell travel [mm]',
               title='PLA reference crossed first')
    for ax in (load, events):
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='x', alpha=.15)
        ax.title.set_fontsize(11)
        ax.tick_params(labelsize=10)
    figure = ROOT / 'docs/figures/snug-nominal-damage-pair.pdf'
    fig.savefig(figure, metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)
    scope = ('Nominal multilinear nickel law on all three fixtures. Bars span adjacent saved native states; '
             'left dots interpolate. Both cased travel brackets are 0.025--0.050 mm at 8.5 N; their overlap '
             'does not resolve a screw-material ordering. PLA is the first parent-mesh coupon reference '
             '(nylon: through-layer stress; aluminium: through-layer strain). Nickel is section-summary '
             'D > 0.0001 after that crossing, not a tearing load. Positive-damage reconstruction is not '
             'verified before the case material screen. Prior bilinear corner limits are not transferred '
             'to these different decks. No physical failure load or converged PLA limit is established.')
    audit = ROOT / 'validation/snug125'
    aluminium['scope'] = scope
    write_json(audit / 'aluminium_nominal_damage_completion.json', aluminium)
    write_json(audit / 'nominal_damage_pair_completion.json', dict(nylon=nylon, aluminium=aluminium,
               bare_history=npair['histories'][0], figure_sha256=digest(figure),
               source_sha256={'aluminium_completion': digest(audit / 'aluminium_nominal_damage_completion.json')},
               scope=scope))
    print({'converged_states': [nylon['converged_states'], aluminium['converged_states']],
           'first_PLA_criteria': [nylon['first_PLA_criterion'], aluminium['first_PLA_criterion']],
           'figure': str(figure)})


if __name__ == '__main__':
    run()
