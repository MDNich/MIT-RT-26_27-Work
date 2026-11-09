"""Compare the six bonded attachments under X and Z base excitation."""
from report_plot import plt
import numpy as np

from audit_local import ROOT,read


def draw():
    fig,axes=plt.subplots(1,2,figsize=(8.2,3.35),layout='constrained')
    for i,(branch,label,color,marker) in enumerate([
        ('bare','Bare board','#08357E','o'),('stand3_nylon','3 mm / nylon','#3C78D8','s'),
        ('stand3_aluminium','3 mm / aluminium','#38761D','^')]):
        record=read(ROOT/'validation/cell_attachment'/f'{branch}.json')
        cell=read(ROOT/'validation/cell_force'/f'{branch}.json')
        ids=sorted(cell['geometry'],key=lambda k:cell['geometry'][k]['centroid_mm'][0])
        for ax,base,direction in zip(axes,['X','Z'],[0,1],strict=True):
            cells=record['spectrum'][base]['cells']
            for j,k in enumerate(ids):
                lo,hi=cells[k]['ends']
                assert lo['face_y_mm']<hi['face_y_mm']
                x=np.array([0.,.72])+2*j+(i-1)*.14
                y=[e['transfer_XYZ_N_rms'][direction] for e in (lo,hi)]
                ax.plot(x,y,marker=marker,color=color,ms=5,lw=1,label=label if j==0 else None)
    for ax,title,ylabel in zip(axes,['Base X','Base Z'],['Transverse X force [N RMS]','Lengthwise Y force [N RMS]'],strict=True):
        ax.set(xlim=(-.44,5.12),xticks=[.36,2.36,4.36],xticklabels=['Left cell','Centre cell','Right cell'],
               ylabel=ylabel,title=title)
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
    axes[0].set_ylim(11,16);axes[1].set_ylim(0,4.6)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False,fontsize=9)
    fig.savefig(ROOT/'docs/figures/cell-attachment-force.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
