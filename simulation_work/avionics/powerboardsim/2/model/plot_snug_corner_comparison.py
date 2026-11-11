"""Show unresolved sharp-corner refinement for both forward-pull mounts."""
import numpy as np
from audit_local import ROOT, read
from film_identity import verified
from report_plot import plt
from stage_snug_fit import AUDIT


def draw():
    audit=read(AUDIT/'forward_material_scope_reassessment.json')
    path=AUDIT/'aluminium_forward_corner_submodel.json';verified(path,audit['submodel_sha256'])
    aluminium=read(path)['regions']['native_layer_peak']
    nylon=read(AUDIT/'nylon_forward_tab_submodel.json')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(7.9,2.85),layout='constrained')
    for name,data,color,y in [('Nylon',nylon,'#38761D',1),('Aluminium',aluminium,'#7A0101',0)]:
        rows=sorted((r for r in data['independent'] if r['radius_mm']==1.8 and
             not r['alternate_diagonal'] and r['stiffness_quadrature_points']==4),key=lambda r:r['subdivisions'])
        assert [r['subdivisions'] for r in rows]==[1,2,4,8]
        i,=np.flatnonzero([abs(r['travel_mm']-.219375)<1e-9 for r in data['native']])
        peak=[r['high_Y_root_max_layer_tension_MPa'][i] for r in rows]
        avg=[r['star_mean_layer_tension_MPa'][i] for r in rows]
        ax.plot(range(4),peak,'o-',color=color,ms=4,label=name+', corner')
        ax.plot(range(4),avg,'s--',color=color,ms=3,label=name+', volume mean')
        high=rows[-1]['first_sample_above_coupon_native_set']
        bracket=[r['travel_mm'] for r in data['native'] if r['native_set'] in (high-1,high)]
        assert len(bracket)==2
        bx.plot(bracket,[y,y],'o-',color=color,lw=3,ms=5)
        bx.annotate(f'{bracket[0]:.3f}--{bracket[1]:.3f}',(np.mean(bracket),y),xytext=(0,8),
                    textcoords='offset points',ha='center',fontsize=9)
    ax.axhline(40.5,color='#777777',ls=':',lw=1)
    ax.set(xticks=range(4),xticklabels=['Original',r'$h/2$',r'$h/4$',r'$h/8$'],
           ylim=(0,82),ylabel='Through-layer stress [MPa]',title='At 0.219 mm imposed travel')
    ax.legend(fontsize=7.4,frameon=False,loc='upper left',labelspacing=.2)
    bx.set(yticks=[1,0],yticklabels=['Nylon','Aluminium'],ylim=(-.5,1.55),
           xlim=(.09,.245),xlabel='Cell travel [mm]',title='Finest tested reference crossing')
    bx.text(.5,.02,'Crossing is not mesh-converged',transform=bx.transAxes,ha='center',fontsize=8,color='#7A0101')
    for a in (ax,bx):
        a.spines[['top','right']].set_visible(False);a.grid(alpha=.12);a.tick_params(labelsize=9)
    fig.savefig(ROOT/'docs/figures/snug-corner-local-refinement.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
