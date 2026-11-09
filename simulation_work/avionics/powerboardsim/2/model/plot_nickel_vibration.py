"""Compare native RMS peaks on the same six nickel strips and element corners."""
from report_plot import plt
import numpy as np

from audit_local import ROOT, read


def plot():
    files = ROOT/'validation/nickel_vibration'
    cases = [('bare','Bare board','#08357E'),('stand3_nylon','Nylon screws','#3C78D8'),
             ('stand3_aluminium','Aluminium screws','#38761D')]
    data = [read(files/(case+'_X.json')) for case, _, _ in cases]
    # Two ends of each cell; order comes from the registered unstrained body centres.
    baseline = data[0]['strips']
    groups = sorted(baseline, key=lambda tag: tuple(round(v) for v in baseline[tag]['original_centre_mm'][:2]))
    assert len(groups)==6
    x = np.array([0,1,2.5,3.5,5,6])
    fig, ax = plt.subplots(figsize=(7.7,2.65),layout='constrained')
    for j, (record, (_, label, color)) in enumerate(zip(data,cases,strict=True)):
        vals = [record['strips'][tag]['native_equivalent_RMS_MPa'] for tag in groups]
        for tag in groups:
            assert record['strips'][tag]['peak'] == baseline[tag]['peak']
        ax.bar(x+.23*(j-1), vals, width=.218, color=color, label=label)
    ax.legend(loc='upper left',ncols=3,frameon=False,fontsize=8,bbox_to_anchor=(0,1.14))
    ax.set_xticks(x, ['Low Y','High Y']*3, fontsize=8)
    for i, label in enumerate(['Left cell','Middle cell','Right cell']):
        ax.text(x[2*i]+.5,-.17,label,transform=ax.get_xaxis_transform(),fontsize=9,ha='center',color='#08357E')
    ax.set_ylim(0,315)
    ax.set_ylabel('Peak strip stress [MPa RMS]',fontsize=9)
    ax.grid(axis='y',alpha=.16)
    ax.set_axisbelow(True)
    ax.spines[['right','top']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/raised-nickel-stress.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    plot()
