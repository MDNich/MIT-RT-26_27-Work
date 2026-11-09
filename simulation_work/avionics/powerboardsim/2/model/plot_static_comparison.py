"""Plot matched-scope displacement peaks from the accepted 3 mm stand-off preload repeats."""
import argparse
import json
from pathlib import Path

from report_plot import plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def draw(metal=False):
    cases = [('stand3_nylon_static', 'Nylon screws', '#3C78D8')]
    if metal:
        cases.append(('stand3_aluminium_static', 'Aluminium screws', '#38761D'))
    series = []
    bare = None
    for case, label, color in cases:
        proof = json.loads((ROOT/'validation/static'/f'{case}.json').read_text())
        ref = proof['models']['bare_static']
        if bare is None:
            bare = ref
            series.append(('Without case','#08357E',bare['scopes']))
        assert bare == ref and proof['cased'] == case
        series.append((label,color,proof['models'][case]['scopes']))
    fig, ax = plt.subplots(figsize=(7.3,2.65),layout='constrained')
    x = np.arange(3)
    width = .78/len(series)
    for i,(label,color,scopes) in enumerate(series):
        values = [1000*scopes[name]['peak_total_U_mm'] for name in ('pcb','cells','nickel')]
        bars = ax.bar(x+(i-(len(series)-1)/2)*width,values,width=.93*width,label=label,color=color)
        ax.bar_label(bars,fmt='%.2f',padding=2,fontsize=8)
    ax.set_ylabel('Peak displacement [µm]')
    ax.set_xticks(x,['PCB','Cell bodies','Nickel strips'])
    ax.set_ylim(0,60)
    ax.spines[['right','top']].set_visible(False)
    ax.legend(loc='upper right',frameon=False,ncols=len(series),fontsize=8)
    fig.savefig(ROOT/'docs/figures/raised-static-comparison.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aluminium',action='store_true')
    draw(parser.parse_args().aluminium)
