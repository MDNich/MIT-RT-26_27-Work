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
    coarse=read(AUDIT/'nylon_outer_startup_mesh_comparison_3_to_2mm_X.json')
    assert [m['mesh_mm'] for m in coarse['models']]==[3,2]
    for ax,drive,limits in zip(axes,('X','Z'),[(11,49),(5,83)],strict=True):
        result=read(AUDIT/f'nylon_event_order_mesh_{drive}.json')
        assert result['axis']==drive and all(x['both_after_middle_bound'] for x in result['models'])
        assert result['nickel_mesh_sha256']==digest(AUDIT/f'nylon_nickel_startup_mesh_{drive}.json')
        ax.set_xlim(*limits)
        ax.set_ylim(-.6,3.7)
        for entry,offset,color,mk in zip(result['models'],(0,-.28),('#08357E','#38761D'),('o','s'),strict=True):
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
        if drive=='X':
            rough,nominal=coarse['models']
            assert nominal['basis_sha256']==result['models'][0]['basis_sha256']
            witness_file=AUDIT/(rough['variant']+'_outer_onset_X_exact_witness.json')
            witness=read(witness_file)
            assert rough['witness_sha256']==digest(witness_file)
            t=[np.mean(rough['cells'][side]['time_interval_ms']) for side in ('left','right')]
            for side in ('left','right'):
                assert rough['cells'][side]['time_interval_ms']==witness['cells'][side]['first_intersection_interval_ms']
            y=np.array([2,1])+.28
            ax.scatter(t,y,marker='^',s=28,color='#a7332e',zorder=3,label='3 mm (X pockets)')
            for x,row in zip(t,y,strict=True):
                ax.annotate(f'{x:.1f}',(x,row),xytext=(5,0),textcoords='offset points',
                            color='#a7332e',ha='left',va='center',fontsize=8)
        ax.set(yticks=[3,2,1,0],yticklabels=names if drive=='X' else [],xlabel='Time from start [ms]')
        ax.tick_params(axis='y',length=0);ax.grid(axis='y',lw=.5,color='#dddddd')
        ax.spines[['top','right','left']].set_visible(False)
        ax.set_title('Base '+drive+' excitation',fontsize=11,color='#08357E',loc='left')
    handles,labels=axes[0].get_legend_handles_labels()
    axes[1].legend(handles,labels,loc='upper right',frameon=False,fontsize=8,title='Case mesh',title_fontsize=8)
    fig.savefig(ROOT/'docs/figures/snug-mesh-event-order.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
