"""Plot audited native default-contact frequencies and shape correlations on the original solids."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT,read


def draw():
    validation=ROOT/'validation'
    ranks=np.arange(1,21)
    fig,(freq,mac)=plt.subplots(2,1,sharex=True,figsize=(7.2,5.15),layout='constrained',
                                gridspec_kw={'height_ratios':[1.35,1]})
    bare=read(validation/'global/bare_refined.json')
    freq.plot(ranks,bare['frequencies_Hz'],'o-',label='Bare board',color='#08357E',ms=4)
    for material,label,style,color in [('nylon','3 mm / nylon','s--','#3C78D8'),
                                       ('aluminium','3 mm / aluminium','^:','#38761D')]:
        key='stand3_'+material+'_refined'
        trial=read(validation/'global'/(key+'.json'))
        matches=read(validation/'modal_matches'/(key+'.json'))
        assert matches['reference_rst_sha256']==bare['rst_sha256']
        assert matches['candidate_rst_sha256']==trial['rst_sha256']
        rows=matches['modes']
        assert np.array_equal([m['reference_rank'] for m in rows],ranks)
        freq.plot(ranks,trial['frequencies_Hz'],style,label=label,color=color,ms=4)
        mac.plot(ranks,[m['equal_rank_MAC'] for m in rows],style,color=color,ms=4)
    freq.legend(frameon=False,fontsize=9)
    freq.set_ylabel('Natural frequency [Hz]')
    mac.set(xlabel='Mode in ascending frequency order',ylabel='Same-rank MAC',ylim=(-.04,1.08),
            xticks=[1,3,5,7,9,11,13,15,17,20])
    for ax in [freq,mac]:
        ax.grid(axis='y',alpha=.22)
        ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/default-mode-comparison.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
