"""Plot a matched damage-law pull at first cell contact and through the in-range case response."""
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT,read
from compare_pull_laws import loading_curve
from film_identity import digest,write_json


def draw(branch):
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
        i,=np.flatnonzero(np.isclose(x,travel,rtol=0,atol=1e-8))
        snapshots.append(dict(native_set=int(case['native_set'][i]),travel_mm=float(x[i]),cell_reaction_N=float(total[i]),
                              case_screws_N=float(screws[i]),fixed_neighbour_N=float(neighbour[i]),original_clamps_N=float(clamps[i]),
                              residual_N=float(case['force_N_x'][i])))
    fig,axes=plt.subplots(1,2,figsize=(8.15,3.05),layout='constrained')
    for rows,colour,label in [(bare,'#08357E','Bare'),(case,'#3C78D8','Raised case')]:
        keep=(rows['ux_mm']>=.135)&(rows['ux_mm']<=.251)
        axes[0].plot(rows['ux_mm'][keep],rows['cell_fx_N'][keep],'.-',ms=5,color=colour,label=label)
    axes[0].axhline(target,ls='--',lw=1,color='#7A0101',label=f'{target:.2f} N')
    axes[0].set(title='Saved states near the reference load',xlim=(.14,.253),ylim=(5,24),ylabel='Lateral force [N]')
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
               selected_states=snapshots,bare_travel_bracket_mm=[v['travel_mm'] for v in bare_bracket],
               raised_travel_bracket_mm=[v['travel_mm'] for v in case_bracket],
               scope='Signed X reactions at the fixed case screws and neighbouring-cell pilot; remaining load at the '
                     'original clamps by whole-fixture equilibrium. Limited to material- and contact-screened states.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch',choices=['stand3_nylon','stand3_aluminium'])
    draw(p.parse_args().branch)
