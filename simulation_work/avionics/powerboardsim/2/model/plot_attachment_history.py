"""Plot time-coincident force magnitudes and components at the governing cell attachment."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from attachment_history import BRANCHES
from audit_local import ROOT, read
from film_identity import verified


def draw():
    fig,axs=plt.subplots(1,2,figsize=(8.2,3.4),layout='constrained')
    colors=['#08357E','#3C78D8','#38761D']
    names=['Bare board','3 mm / nylon','3 mm / aluminium']
    common=[]
    for i,branch in enumerate(BRANCHES):
        proof=read(ROOT/'validation/cell_attachment'/f'{branch}_native_history.json')
        verified(ROOT/'validation/cell_attachment'/f'{branch}.json',proof['shape_source_sha256'])
        peak=[proof['axes'][a]['maximum'] for a in 'XYZ']
        z=peak[2]
        assert z['cell']=='right' and z['end']=='low Y'
        common.append(z['sample'])
        x=np.arange(3)+(i-1)*.24
        axs[0].bar(x,[p['magnitude_N'] for p in peak],width=.22,color=colors[i],label=names[i])
        axs[1].bar(x,z['components_N'],width=.22,color=colors[i])
    assert len(set(common))==1
    axs[0].set(title='Largest load at one cell end',ylabel='Dynamic force magnitude [N]',
               xticks=range(3),xticklabels=['Base X','Base Y','Base Z'],ylim=(0,75))
    axs[1].set(title='Right cell at the base-Z peak',ylabel='Signed dynamic force [N]',
               xticks=range(3),xticklabels=['X','Y (lengthwise)','Z'],ylim=(-33,20))
    axs[1].axhline(0,color='#666',lw=.7)
    for ax in axs:
        ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        ax.spines[['top','right']].set_visible(False)
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False)
    fig.savefig(ROOT/'docs/figures/attachment-native-history.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw()
