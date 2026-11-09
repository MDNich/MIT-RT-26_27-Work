"""Plot early material-reference crossings before the local installation loses contact resolution."""
from report_plot import plt
import numpy as np

from audit_local import ROOT,read


def plot():
    case='flush_nylon_lateral_friction_locked_approach1'
    study=read(ROOT/'validation/installation_material'/(case+'.json'))
    path=read(ROOT/'validation/pulls/flush_nylon_drawdown.json')
    assert study['rst_sha256']==path['rst_sha256']
    stop=path['first_closed_corner_penetration_over_screen_travel_mm'][0]
    rows=[r for r in study['history'] if .5<=r['travel_mm']<=stop]
    x=[r['travel_mm'] for r in rows]
    fig,(a,b)=plt.subplots(1,2,figsize=(8.4,2.55),layout='constrained')
    limits=study['reference_properties']
    for key,name,color in [('in_plane_tension_MPa','In-plane tension','#08357E'),
                           ('layer_tension_MPa','Through-layer tension','#38761D')]:
        a.plot(x,[r['all_'+key]/limits[key] for r in rows],label=name,color=color)
    a.axhline(1,color='#7A0101',lw=1,ls='--',label='Coupon tensile strength')
    a.set(ylabel='Peak stress / coupon strength', title='Printed case')
    for key,name,color in [('peak_fiber_tension_MPa','Most tensile fibre','#08357E'),
                           ('maximum_direct_MPa','Direct axial stress','#38761D')]:
        b.plot(x,[max(r['four_screws'][key]) for r in rows],label=name,color=color)
    b.set(ylabel='Axial stress [MPa]',title='Nylon screw shanks')
    for ax in (a,b):
        ax.legend(fontsize=7.8,loc='upper left',frameon=False)
        ax.grid(axis='y',alpha=.18)
        ax.set_xlabel('Imposed screw-head travel [mm]')
        ax.set(xlim=(.5,stop),ylim=(0,None))
        ax.spines[['right','top']].set_visible(False)
        ax.title.set_fontsize(10)
    fig.savefig(ROOT/'docs/figures/flush-local-material.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    plot()
