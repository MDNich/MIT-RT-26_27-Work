"""Plot matched-scope peaks after the six original bolt sections are locked."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def draw(case='stand3_nylon_static'):
    report = json.loads((ROOT/'validation/static'/f'{case}.json').read_text())
    names = ['pcb', 'cells', 'nickel']
    fig, ax = plt.subplots(figsize=(7.2, 2.4), layout='constrained')
    x = np.arange(3)
    for model, offset, label, color in [('bare_static', -.19, 'Without case', '#08357E'),
                                         (case, .19, '3 mm stand-off, nylon', '#3C78D8')]:
        values = [1000*report['models'][model]['scopes'][k]['peak_total_U_mm'] for k in names]
        bars = ax.bar(x+offset, values, width=.35, color=color, label=label)
        ax.bar_label(bars, fmt='%.2f', padding=2, fontsize=9)
    ax.set_ylabel('Peak displacement [µm]')
    ax.set_xticks(x, ['PCB', 'Cell bodies', 'Nickel strips'])
    ax.set_ylim(0, 60)
    ax.spines[['right','top']].set_visible(False)
    ax.legend(loc='upper right', frameon=False, ncols=2, fontsize=9)
    fig.savefig(ROOT/'docs/figures'/'raised-static-comparison.pdf', metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)

if __name__=='__main__':draw()
