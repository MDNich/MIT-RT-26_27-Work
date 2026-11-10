"""Show how the peak and a fixed-volume average respond to refinement of the printed tab."""
import numpy as np

from audit_local import ROOT, read
from report_plot import plt
from stage_snug_fit import AUDIT


def draw():
    data=read(AUDIT/'nylon_forward_tab_submodel.json')
    records=data['independent']
    main=sorted((r for r in records if r['radius_mm']==1.8 and not r['alternate_diagonal']
                 and r['stiffness_quadrature_points']==4),key=lambda r:r['subdivisions'])
    assert len(records)==16
    for r in records:
        base=main[int(np.log2(r['subdivisions']))]
        assert r['first_sample_above_coupon_native_set']==base['first_sample_above_coupon_native_set']
        assert abs(r['star_volume_mm3']-data['native'][0]['volume_mm3'])<2.e-6
        assert r['max_free_dof_residual_N']<1.e-6
        if r['stiffness_quadrature_points']==27:
            np.testing.assert_allclose(r['high_Y_root_max_layer_tension_MPa'],base['high_Y_root_max_layer_tension_MPa'],atol=1e-6,rtol=0)
    subdivisions=[r['subdivisions'] for r in main]
    assert subdivisions==[1,2,4,8]
    native=data['native'];travel=np.array([s['travel_mm'] for s in native])
    idx,=np.flatnonzero(np.isclose(travel,.219375,rtol=0,atol=1.e-8))
    assert all(r['high_Y_root_max_layer_tension_MPa'][idx]<40.5 for r in records)
    fig,(ax,bx)=plt.subplots(1,2,figsize=(7.9,2.65),layout='constrained',gridspec_kw={'width_ratios':[1,1.12]})
    pos=np.arange(4)
    def line(field, label, colour,dy):
        values=np.array([r[field][idx] for r in main])
        ax.plot(pos,values,'o-',label=label,color=colour,lw=1.65,ms=3.7)
        for x,y in zip(pos,values,strict=True):
            ax.annotate(f'{y:.1f}',(x,y),xytext=(0,dy),textcoords='offset points',ha='center',fontsize=8)
    line('high_Y_root_max_layer_tension_MPa','Corner peak','#08357E',5)
    line('star_mean_layer_tension_MPa','Volume average','#38761D',5)
    ax.set(title='At 0.2194 mm cell travel',xticks=pos,xticklabels=['Original',r'$h/2$',r'$h/4$',r'$h/8$'],
           ylabel='Through-layer stress [MPa]',ylim=(0,43),xlim=(-.29,3.27))
    ax.legend(loc='upper left',frameon=False,fontsize=8)
    ax.grid(axis='y',alpha=.14)
    bx.set(title='First 40.5 MPa corner crossing',yticks=pos,yticklabels=[r'$h/8$',r'$h/4$',r'$h/2$','Original'],
           xlabel='Prescribed left-cell travel [mm]',ylim=(-.42,3.64),xlim=(.207,.318))
    for rank,r in enumerate(main):
        above=r['first_sample_above_coupon_native_set']
        assert native[above-1]['native_set']==above
        v=travel[above-2:above]
        assert r['high_Y_root_max_layer_tension_MPa'][above-2]<40.5<=r['high_Y_root_max_layer_tension_MPa'][above-1]
        y=3-rank
        bx.plot(v,[y,y],'o-',ms=4,lw=2.1,color='#08357E')
        bx.annotate(f'{v[0]:.3f}--{v[1]:.3f}',(v.mean(),y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
    bx.grid(axis='x',alpha=.14)
    for a in (ax,bx):
        a.set_axisbelow(True);a.spines[['right','top']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/snug-tab-local-refinement.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw()
