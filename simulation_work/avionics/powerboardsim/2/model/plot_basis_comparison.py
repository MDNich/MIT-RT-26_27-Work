"""Render prestressed spectra and a few named shape matches from accepted receipts."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from audit_local import ROOT,read

def draw():
    p=read(ROOT/'validation/modal_pairs/stand3_nylon_basis.json')
    freq=[np.array([r['bare_Hz'] for r in p['bare_modes']]),np.array([r['Hz'] for r in p['cased_modes']])]
    fig,ax=plt.subplots(figsize=(7.7,2.55),layout='constrained')
    screws=read(ROOT/'validation/screw_modal_comparison/stand3.json')
    metal=read(ROOT/'validation/global/stand3_aluminium_basis.json')
    assert metal['rst_sha256']==screws['native_sources']['stand3_aluminium_basis']
    freq.append(np.asarray(metal['frequencies_Hz']))
    colors=['#08357E','#3C78D8','#38761D'];den=[2,1,0]
    for f,c,y in zip(freq,colors,den):
        f=f[f<=2000];ax.vlines(f,y-.14,y+.14,lw=1.6,color=c)
    for i in (3,7,8,10,11):
        row=p['bare_modes'][i];assert row['assigned_MAC']>.94 and row['best_available_rank']==row['candidate_rank']
        ax.plot([row['bare_Hz'],row['candidate_Hz']],[1.85,1.15],color='#799b9a',lw=1.1)
    for row in screws['rows']:
        if (row.get('full_solid_MAC',0)>=.97 and row['aluminium_mode']==row['best_aluminium_mode']
                and max(row['nylon_Hz'],row['aluminium_Hz'])<=2000):
            ax.plot([row['nylon_Hz'],row['aluminium_Hz']],[.85,.15],color='#86a67a',lw=1.1)
    ax.annotate('320 Hz',xy=(freq[2][0],-.12),xytext=(freq[2][0],-.43),ha='center',fontsize=9,color=colors[2])
    ax.set_xlim(0,2000);ax.set_ylim(-.57,2.35);ax.set_xlabel('Natural frequency [Hz]')
    ax.set_yticks([0,1,2],['Raised / aluminium','Raised / nylon','Bare board'])
    ax.tick_params(axis='y',length=0);ax.spines[['left','top','right']].set_visible(False)
    ax.set_xticks(np.arange(0,2001,250))
    fig.savefig(ROOT/'docs/figures'/'raised-prestressed-modes.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
if __name__=='__main__':draw()
