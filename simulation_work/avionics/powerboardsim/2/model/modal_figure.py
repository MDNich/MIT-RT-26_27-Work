"""Plot the ordered frequencies from the accepted bare default-contact repeats."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    fig,ax=plt.subplots(figsize=(7.0,3.15),layout='constrained')
    for case,label,marker,color,offset in [('bare_original_sturm','Original mesh','o','#08357E',-.11),
                                            ('bare_refined','Refined mesh','D','#38761D',.11)]:
        data=json.loads((ROOT/'validation/global'/f'{case}.json').read_text())
        f=np.asarray(data['frequencies_Hz'])
        if len(f)!=20 or np.any(np.diff(f)<=0):
            raise ValueError(f'{case} needs twenty increasing frequencies')
        ax.scatter(np.arange(1,21)+offset,f,s=30,marker=marker,
                   facecolors=color if marker=='o' else 'white',edgecolors=color,linewidths=1.35,label=label,zorder=3)
    ax.set(xlabel='Mode rank within each solution',ylabel='Natural frequency [Hz]',xlim=(.35,20.65),ylim=(0,2500),
           xticks=[1,2,4,6,8,10,12,14,16,18,20],yticks=np.arange(0,2501,500))
    ax.grid(axis='y',color='#dce2eb',linewidth=.7)
    ax.spines[['top','right']].set_visible(False)
    ax.legend(loc='upper left',frameon=False)
    fig.savefig(ROOT/'docs/figures/bare-modal-frequencies.pdf')
    plt.close(fig)

if __name__=='__main__':
    main()
