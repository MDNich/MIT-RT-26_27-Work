"""Show each cell's net force along the driven axis with the reported assembly configuration."""
from report_plot import plt
import numpy as np

from audit_local import ROOT,read


def draw():
    records=[read(ROOT/'validation/cell_force'/(branch+'.json')) for branch in ('bare','stand3_nylon','stand3_aluminium')]
    cells=sorted(records[0]['geometry'],key=lambda k:records[0]['geometry'][k]['centroid_mm'][0])
    colors=['#08357E','#3C78D8','#38761D']
    names=['Bare board','3 mm / nylon','3 mm / aluminium']
    palette=['o','s','^']
    fig,axes=plt.subplots(1,3,figsize=(8.5,3),sharey=True,layout='constrained')
    for j,(ax,base) in enumerate(zip(axes,'XYZ',strict=True)):
        for i,(model,label,color,mark) in enumerate(zip(records,names,colors,palette,strict=True)):
            data=model['base_cases'][base]['cells']
            values=[data[k]['net_dynamic_force_XYZ_rms_N'][j] for k in cells]
            ax.scatter(np.arange(3)+(i-1)*.19,values,s=38,color=color,marker=mark,label=label,zorder=3)
        ax.set(xticks=[0,1,2],xticklabels=['Left','Centre','Right'],xlim=(-.5,2.5),ylim=(0,33),title='Base '+base)
        ax.grid(axis='y',alpha=.21);ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('Net cell force along base axis [N RMS]')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,fontsize=8,frameon=False)
    fig.savefig(ROOT/'docs/figures/raised-cell-inertial-force.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
