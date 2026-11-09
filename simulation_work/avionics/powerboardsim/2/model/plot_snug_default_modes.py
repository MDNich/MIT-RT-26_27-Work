"""Plot the matched 20-mode refined-default controls on the shared original board assembly."""
import numpy as np

from audit_local import ROOT,read
from report_plot import plt


def draw():
    bare=read(ROOT/'validation/global/bare_refined.json')
    modes=np.arange(1,21)
    fig,(freq,shape)=plt.subplots(1,2,figsize=(7.8,2.8),layout='constrained')
    freq.plot(modes,np.array(bare['frequencies_Hz'])/1000,'.-',ms=4,lw=1.25,color='#08357E',label='Bare')
    for screw,color in [('nylon','#3C78D8'),('aluminium','#38761D')]:
        case=f'snug125_{screw}_refined'
        proof=read(ROOT/'validation/global'/f'{case}.json')
        match=read(ROOT/'validation/modal_matches'/f'{case}.json')
        assert proof['case']==case and proof['campaign']==bare['campaign']
        assert match['reference_rst_sha256']==bare['rst_sha256'] and match['candidate_rst_sha256']==proof['rst_sha256']
        assert np.allclose([r['reference_Hz'] for r in match['modes']],bare['frequencies_Hz'])
        freq.plot(modes,np.asarray(proof['frequencies_Hz'])/1000,'.-',ms=4,lw=1.25,color=color,label=screw.capitalize())
        shape.plot(modes,[r['equal_rank_MAC'] for r in match['modes']],'.-',ms=4,lw=1.25,color=color,label=screw.capitalize())
    freq.set(ylabel='Frequency [kHz]',title='Ordered frequencies')
    shape.set(ylabel='Same-rank MAC',title='Mode shape against bare board',ylim=(-.04,1.06))
    for ax in (freq,shape):
        ax.set(xlabel='Mode rank',xticks=[1,5,10,15,20]);ax.legend(frameon=False,fontsize=8);ax.grid(alpha=.18)
        ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/snug-default-modes.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
