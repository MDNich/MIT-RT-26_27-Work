"""Summarize actual tab clearance and contact error along an audited partial installation."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from audit_local import ROOT,read,table
from film_identity import write_json

def summarize():
    case='flush_nylon_lateral_friction_locked_approach1'
    proof=read(ROOT/'validation/partial_local'/f'{case}.json')
    d=ROOT/'.runtime/post'/proof['campaign']/case
    reactions=table(d/'whole_fixture_balance.csv')
    contacts=table(d/'closed_contacts.csv')
    p=contacts[contacts['pair']==862]
    tabs=read(d/'tab_plane_history.json')
    assert np.array_equal(p['native_set'],reactions['native_set']) and np.array_equal([s['native_set'] for s in tabs],p['native_set'])
    travel=reactions['screw1_u_mm_z'];load=reactions['screw_support_N_z']/1000
    gap=np.array([[row['min_mm'] for row in z['tabs']] for z in tabs])
    median=np.array([[row['median_mm'] for row in z['tabs']] for z in tabs])
    pen=p['max_closed_penetration_mm']
    def bracket(condition):
        i=np.flatnonzero(condition)[0];return travel[i-1:i+1].tolist()
    rec=dict(case=case,states=len(tabs),rst_sha256=proof['rst_sha256'],
             last_screw_travel_mm=float(travel[-1]),last_total_reaction_kN=float(load[-1]),
             first_closed_corner_penetration_over_screen_travel_mm=bracket(pen>.05),
             first_tab_plane_crossing_over_screen_travel_mm=bracket(gap.min(axis=1)<-.05),
             endpoint_minimum_tab_gaps_mm=gap[-1].tolist(),endpoint_median_tab_gaps_mm=median[-1].tolist(),
             maximum_loaded_corner_penetration_mm=float(pen.max()),remaining_commanded_travel_mm=float(3-travel[-1]),
             method='Four prescribed screw tops, local rigid neighbors and co-moving seat springs. Negative gap means a sampled tab point crossed the nominal PCB plane.')
    write_json(ROOT/'validation/pulls/flush_nylon_drawdown.json',rec)
    fig,(left,right)=plt.subplots(1,2,figsize=(8.2,3.05),layout='constrained')
    left.plot(travel,load,color='#08357E',lw=1.8);left.scatter(travel[-1],load[-1],color='#7A0101',s=20,zorder=3)
    left.axvspan(*rec['first_closed_corner_penetration_over_screen_travel_mm'],color='#CE8F89',alpha=.55)
    left.set_ylabel('Four screw reactions, sum [kN]');left.set_title('Computed tightening load',fontsize=10)
    right.fill_between(travel,gap.min(1),gap.max(1),color='#3C78D8',alpha=.45,label='Minimum on each tab')
    right.plot(travel,median.mean(1),color='#08357E',lw=1.5,label='Mean of four tab medians')
    right.axhline(0,color='#7A0101',lw=.9);right.set_ylabel('Tab gap to PCB datum [mm]');right.set_title('Actual tab motion',fontsize=10)
    right.legend(frameon=False,fontsize=8)
    for ax in (left,right):
        ax.set_xlim(0,3);ax.set_xlabel('Screw-head travel [mm]');ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/flush-nylon-installation.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
if __name__=='__main__':summarize()
