"""Summarize the closed nylon nominal damage run without treating later damage as failure."""
import re

import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from report_plot import plt


def run():
    case='snug125_nylon_damage_cont_nominal_pin1_m15'
    audit=ROOT/'validation/snug125'
    receipt=ROOT/'.runtime/receipts/nov08_01'/case
    folder=ROOT/'.runtime/archive/nov08_01'/case
    verdict_path=ROOT/'validation/partial_local'/(case+'.json')
    verdict=read(verdict_path);status=read(receipt/'status.json');ledger=read(receipt/'archived.json')
    hashes={r['name']:r['sha256'] for r in ledger['files']}
    assert (receipt/'released.txt').exists() and status['phase']=='solver_complete'
    assert status['exit']==1 and not status['native_clean'] and not verdict['full_requested_path']
    for name in ('model.inp','tear.rst','solve.out'):
        verified(folder/name,hashes[name])
    listing=(folder/'solve.out').read_text(errors='replace')
    stop=re.search(r'Solution not converged at time ([\d.]+) \(load step (\d+) substep (\d+)\)',listing)
    assert stop and 'substep 999999' in listing and 'RUN COMPLETED' in listing
    paths=dict(pair=audit/(case+'_matched_damage.json'),
               material=ROOT/'validation/pull_material'/(case+'.json'),
               limits=ROOT/'validation/pulls'/(case+'_damage_scope.json'),
               balance=ROOT/'validation/damage_balance'/(case+'.json'),
               initiation=audit/(case+'_nickel_initiation.json'),
               evolution=audit/(case+'_nickel_evolution.json'))
    pair,material,limits,balance,initiation,evolution=[read(paths[k]) for k in paths]
    assert pair['fixture_sha256'][1]==limits['fixture_audit_sha256']==digest(verdict_path)
    assert pair['mounted_material_scope_sha256']==digest(paths['limits'])
    assert limits['material_audit_sha256']==digest(paths['material'])
    assert balance['all_states_within_limits'] and balance['rst_sha256']==verdict['rst_sha256']==hashes['tear.rst']
    assert initiation['verdict_sha256']==evolution['verdict_sha256']==digest(verdict_path)
    assert initiation['field_replay_verified'] and initiation['native_evolution_sha256']==digest(paths['evolution'])
    assert evolution['native_converged_sets']==verdict['states']==28 and evolution['excluded_diagnostic_sets']==1
    first=min(limits['first_criterion_sets'].values())
    key=next(k for k,v in limits['first_criterion_sets'].items() if v==first)
    crossing=material['first_reference_crossings'][key]
    assert first==23 and evolution['supported_sets']==first-1
    assert evolution['last_supported']['native_max_point_damage']==0
    assert pair['snug_onset_within_recorded_screens'] is None
    nickel=verdict['damage_onset_bracket']
    assert nickel[0]['native_set']>first and verdict['damage_reporting_threshold']==1e-4
    fig,(load,events)=plt.subplots(1,2,figsize=(8.2,2.35),layout='constrained',gridspec_kw={'width_ratios':[1,1.35]})
    for y,name,label,color in [(1,'bare','Bare','#08357E'),(0,'snug','Nylon case','#38761D')]:
        row=pair['at_reference_force'][name]
        lo,hi=[r['travel_mm'] for r in row['bracket']];x=row['travel_mm']
        load.errorbar(x,y,xerr=np.array([[x-lo],[hi-x]]),fmt='o',color=color,capsize=5,lw=2,ms=5)
        load.annotate(f'{x:.2f} mm',xy=(x,y),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9,color=color)
    load.set(yticks=[0,1],yticklabels=['Nylon case','Bare'],ylim=(-.5,1.6),xlim=(0,.24),
             xlabel='Cell travel [mm]',title='Same nominal nickel law, 8.5 N')
    lo,hi=crossing['last_below_mm'],crossing['first_above_mm']
    events.axvspan(hi,.365,color='#CE8F89',alpha=.20,lw=0)
    for y,values,color in [(1,[lo,hi],'#7A0101'),(0,[r['cell_ux_mm'] for r in nickel],'#5A43A0')]:
        a,b=values
        events.plot([a,b],[y,y],color=color,lw=4)
        events.plot([a,b],[y,y],linestyle='none',marker='|',color=color,ms=11)
    events.set(yticks=[0,1],yticklabels=[r'Nickel $D>10^{-4}$','PLA coupon'],ylim=(-.5,1.6),
               xlim=(.26,.365),xlabel='Nylon-case cell travel [mm]',title='PLA reference crossed first')
    events.set_xticks([.28,.30,.32,.34,.36])
    events.annotate('0.28--0.29 mm',xy=((lo+hi)/2,1),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9,color='#7A0101')
    events.annotate('About 0.35 mm',xy=(nickel[-1]['cell_ux_mm'],0),xytext=(-8,9),textcoords='offset points',ha='right',fontsize=9,color='#5A43A0')
    for ax in (load,events):
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',alpha=.15);ax.title.set_fontsize(11)
    figure=ROOT/'docs/figures/snug-nominal-damage.pdf'
    fig.savefig(figure,metadata={'CreationDate':None,'ModDate':None});plt.close(fig)
    output=dict(case=case,input_sha256=hashes['model.inp'],rst_sha256=hashes['tear.rst'],
                status_sha256=digest(receipt/'status.json'),archive_manifest_sha256=digest(receipt/'archived.json'),
                fixture_sha256=digest(verdict_path),source_sha256={k:digest(p) for k,p in paths.items()},
                termination='Native nonconvergence; no restart under the finite main-validation scope.',
                rejected_time=float(stop[1]),rejected_load_step=int(stop[2]),rejected_substep=int(stop[3]),
                converged_states=28,excluded_diagnostic_sets=1,last_converged_travel_mm=verdict['last_ux_mm'],
                all_saved_force_checks_pass=True,first_PLA_reference_bracket_mm=[lo,hi],
                nickel_reporting_bracket=nickel,maximum_recorded_section_damage=verdict['peak_damage'],
                last_parent_screened=evolution['last_supported'],
                last_screened_initiation_criterion=initiation['native_trace'][-1][3],
                equal_force_reference_N=pair['equal_force_reference_N'],equal_force_travel=pair['at_reference_force'],
                figure_sha256=digest(figure),scope='Nominal multilinear nickel law on both fixtures. '
                'Brackets are adjacent saved states; left dots interpolate. The damage threshold occurs after '
                'the parent-mesh PLA reference crossing and does not establish tearing or a safe load. '
                'Earlier bilinear corner-refinement bounds are not transferred to this different deck.')
    write_json(audit/'nylon_nominal_damage_completion.json',output)
    print({'last_converged_mm':verdict['last_ux_mm'],'PLA_bracket_mm':[lo,hi],'screened_point_damage':0})


if __name__=='__main__':
    run()
