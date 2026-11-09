"""Plot a matched damage-law pull at first cell contact and through the in-range case response."""
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT,read,table
from compare_pull_laws import loading_curve
from film_identity import digest,verified,write_json


def fine_curve(parent):
    case=parent['case']+'_load8ref1'
    proof=read(ROOT/'validation/local'/(case+'.json'))
    path=ROOT/'validation/refined_pull_force'/(case+'.json')
    control=read(path)
    assert proof['full_requested_path'] and proof['campaign']==control['campaign']==parent['campaign']
    assert control['parent']==parent['case'] and proof['case']==control['case']==case
    assert parent['native_history_sha256']==control['original_inventory_sha256']
    inventory=ROOT/'.runtime/archive'/proof['campaign']/case/'set_inventory.csv'
    verified(inventory,control['refined_inventory_sha256'])
    rows=table(inventory)
    first=int(np.flatnonzero(rows['loadstep']==rows['loadstep'][-1])[0])
    assert first>0
    return rows[first-1:],digest(path)


def draw(branch, refined=False):
    comparison=ROOT/'validation/pull_laws'/(branch+'.json')
    common=read(comparison)
    bare,bare_proof=loading_curve('bare',True)
    case,case_proof=loading_curve(branch,True)
    assert common['sources'][bare_proof['case']]==bare_proof and common['sources'][case_proof['case']]==case_proof
    curves=common['curves']
    bare_bracket=curves[bare_proof['case']]['at_bare_control_force']['bracket']
    case_bracket=curves[case_proof['case']]['at_bare_control_force']['bracket']
    target=common['bare_control_force_N']
    x=case['ux_mm'];total=case['cell_fx_N']
    screws=-case['screw_support_N_x'];neighbour=-case['neighbor_support_N_x']
    clamps=total-screws-neighbour-case['force_N_x']
    snapshots=[]
    for travel in [common['common_travel_mm'],x[-1]]:
        # A different nickel law can end between this model's saved equilibria.
        # Keep the actual lower station when resolving the load into support forces.
        i=int(np.searchsorted(x,travel+1e-8,side='right')-1)
        assert i>=0 and x[i]<=travel+1e-8
        station=dict(native_set=int(case['native_set'][i]),travel_mm=float(x[i]),cell_reaction_N=float(total[i]),
                     case_screws_N=float(screws[i]),fixed_neighbour_N=float(neighbour[i]),original_clamps_N=float(clamps[i]),
                     residual_N=float(case['force_N_x'][i]))
        if not np.isclose(x[i],travel,atol=1e-8,rtol=0):
            assert i+1<len(x)
            station.update(requested_travel_mm=float(travel),next_saved_travel_mm=float(x[i+1]))
        snapshots.append(station)
    fig,axes=plt.subplots(1,2,figsize=(8.15,3.05),layout='constrained')
    fine_checks={}
    for rows,source,colour,label in [(bare,bare_proof,'#08357E','Bare'),
                                     (case,case_proof,'#3C78D8',branch.split('_')[-1].capitalize()+' screws')]:
        if refined:
            series,fine_checks[source['case']]=fine_curve(source)
            brackets=curves[source['case']]['at_bare_control_force']['bracket']
            axes[0].plot([s['travel_mm'] for s in brackets],[s['force_N'] for s in brackets],
                         'o--',ms=3,lw=.85,alpha=.8,color=colour)
            axes[0].plot(series['ux_mm'],series['fx_N'],lw=1.6,color=colour,label=label)
        else:
            keep=(rows['ux_mm']>=.135)&(rows['ux_mm']<=.251)
            axes[0].plot(rows['ux_mm'][keep],rows['cell_fx_N'][keep],'.-',ms=5,color=colour,label=label)
    axes[0].axhline(target,ls='--',lw=1,color='#7A0101',label=f'{target:.2f} N')
    axes[0].set(title='Saved states near the reference load',ylabel='Lateral force [N]')
    if refined:
        axes[0].set_xlim(.1865,.220)
    else:
        axes[0].set_xlim(.134,.253)
        axes[0].set_ylim(bottom=5)
    for values,colour,label,marker in [(total,'#08357E','Applied to cell','o'),(screws,'#3C78D8','Four case screws','s'),
                                      (neighbour,'#38761D','Fixed neighbour','^'),(clamps,'#5A43A0','Original clamps','D')]:
        axes[1].plot(x,values,color=colour,marker=marker,ms=3,lw=1.2,label=label)
    axes[1].set(title='Load carried by the fixture supports',ylabel='Lateral force [N]')
    for ax in axes:
        ax.set_xlabel('Cell travel [mm]');ax.spines[['top','right']].set_visible(False)
        ax.legend(loc='upper left',frameon=False,fontsize=7.5);ax.grid(axis='y',alpha=.18)
    fig.savefig(ROOT/'docs/figures'/(branch+'-damage-pull.pdf'),metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    write_json(ROOT/'validation/pull_laws'/(branch+'_support_loads.json'),dict(branch=branch,
               common_comparison_sha256=digest(comparison),support_history_sha256=digest(ROOT/'.runtime/post'/case_proof['campaign']/case_proof['case']/'whole_fixture_balance.csv'),
               **({'refined_checks_sha256':fine_checks} if refined else {}),
               selected_states=snapshots,bare_travel_bracket_mm=[v['travel_mm'] for v in bare_bracket],
               raised_travel_bracket_mm=[v['travel_mm'] for v in case_bracket],
               scope='Signed X reactions at the fixed case screws and neighbouring-cell pilot; remaining load at the '
                     'original clamps by whole-fixture equilibrium. Limited to material- and contact-screened states.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch',choices=['stand3_nylon','stand3_aluminium'])
    p.add_argument('--refined',action='store_true',help='Overlay the two accepted fine-step histories near the reference load')
    args=p.parse_args()
    draw(args.branch,args.refined)
