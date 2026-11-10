"""Show how the first outer-cell crossings and nickel reference change with case mesh."""
import numpy as np
from audit_local import ROOT,read
from film_identity import digest
from report_plot import plt
from stage_snug_fit import AUDIT


def draw():
    fig,axes=plt.subplots(1,2,figsize=(7.6,2.70),layout='constrained',
                          gridspec_kw={'wspace':.12})
    names=['Middle load bound','Left pocket','Right pocket','Nickel reference']
    for ax,drive,limits in zip(axes,('X','Z'),[(11,49),(5,83)],strict=True):
        result=read(AUDIT/f'nylon_event_order_mesh_{drive}.json')
        assert result['axis']==drive and all(x['both_after_middle_bound'] for x in result['models'])
        assert result['nickel_mesh_sha256']==digest(AUDIT/f'nylon_nickel_startup_mesh_{drive}.json')
        ax.set_xlim(*limits)
        ax.set_ylim(-.6,3.7)
        for entry,offset,color,mk in zip(result['models'],(.16,-.16),('#08357E','#38761D'),('o','s'),strict=True):
            signed=read(AUDIT/(entry['variant']+'_pocket_unloading.json'))
            assert signed['modal_rst_sha256']==entry['basis_sha256']
            clock=signed['axes'][drive]['integrations']['exact_linear_input']['first_crossing']
            bound_ms=1000*clock['time_bracket_s'][1]
            assert bound_ms<=entry['pressure_redistribution_by_ms']
            t=[bound_ms,
               np.mean(entry['outer_brackets_ms']['left']),np.mean(entry['outer_brackets_ms']['right']),
               np.mean(entry['trial_yield_bracket_ms'])]
            y=np.array([3,2,1,0])+offset
            ax.scatter(t,y,marker=mk,s=24,color=color,zorder=3,label=f"{entry['mesh_mm']:g} mm")
            for x,row in zip(t,y,strict=True):
                ax.annotate(f'{x:.1f}',(x,row),xytext=(5,0),textcoords='offset points',
                            color=color,ha='left',va='center',fontsize=8)
        ax.set(yticks=[3,2,1,0],yticklabels=names if drive=='X' else [],xlabel='Time from start [ms]')
        ax.tick_params(axis='y',length=0);ax.grid(axis='y',lw=.5,color='#dddddd')
        ax.spines[['top','right','left']].set_visible(False)
        ax.set_title('Base '+drive+' excitation',fontsize=11,color='#08357E',loc='left')
    axes[1].legend(loc='upper right',frameon=False,fontsize=8,title='Case mesh',title_fontsize=8)
    fig.savefig(ROOT/'docs/figures/snug-mesh-event-order.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
