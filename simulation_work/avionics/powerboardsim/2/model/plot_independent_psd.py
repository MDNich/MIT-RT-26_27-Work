"""Compare peak board-normal displacement with the excitation axis held fixed."""
from report_plot import plt
import numpy as np
from audit_local import ROOT,read

def draw():
    base=ROOT/'validation/independent_psd'
    records=[read(base/f'{b}_basis.json') for b in ('bare','stand3_nylon','stand3_aluminium')]
    assert all(r['baseline_5pct_screen_passed'] for r in records)
    fig,ax=plt.subplots(figsize=(7.5,2.8),layout='constrained');x=np.arange(3);w=.26
    for j,(r,color,label) in enumerate(zip(records,['#08357E','#3C78D8','#38761D'],['Bare board','3 mm / nylon','3 mm / aluminium'],strict=True)):
        vals=[1000*r['base_cases'][a]['scopes']['pcb']['peak_directional_RMS_mm'][2] for a in 'XYZ']
        bars=ax.bar(x+(j-1)*w,vals,width=w,color=color,label=label)
        ax.bar_label(bars,fmt='%.1f',padding=3,fontsize=9)
    ax.set_xticks(x,['Base X','Base Y','Base Z']);ax.set_ylim(0,188)
    ax.set_ylabel('Peak PCB Z displacement [µm RMS]')
    ax.spines[['top','right']].set_visible(False)
    ax.legend(loc='upper center',ncol=3,frameon=False,fontsize=9)
    fig.savefig(ROOT/'docs/figures/raised-independent-psd.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
if __name__=='__main__':draw()
