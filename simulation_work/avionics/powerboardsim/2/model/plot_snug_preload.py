"""Plot the matched PCB/cell/strip displacement peaks and the snug case contact history at bolt lock."""
import argparse
import numpy as np

from audit_local import ROOT,read
from report_plot import plt
from stage_snug_fit import AUDIT


def draw(materials):
    fig,(motion,contact)=plt.subplots(1,2,figsize=(7.8,3.12),gridspec_kw={'width_ratios':[1.45,1]},layout='constrained')
    names=['pcb','cells','nickel']
    colours={'bare':'#08357E','nylon':'#3C78D8','aluminium':'#38761D'}
    x=np.arange(len(names))
    bars=[]
    for material in materials:
        case=f'snug125_{material}_static'
        comp=read(ROOT/'validation/static'/f'{case}.json')
        installed=read(AUDIT/f'{case}_installed.json')
        assert comp['bare']=='bare_static' and comp['cased']==case
        assert comp['models'][case]['source_rst_sha256']==installed['rst_sha256']
        if not bars:
            bars.append(('bare',comp['models']['bare_static']))
        else:
            assert bars[0][1]==comp['models']['bare_static']
        bars.append((material,comp['models'][case]))
        states=installed['contact_history']
        contact.plot([r['time_s'] for r in states],[r['p_max']*1e-6 for r in states],
                     '.-',ms=5,lw=1.5,color=colours[material],label=material.capitalize())
    width=.79/len(bars)
    for i,(name,model) in enumerate(bars):
        y=[1000*model['scopes'][s]['peak_total_U_mm'] for s in names]
        art=motion.bar(x+(i-(len(bars)-1)/2)*width,y,width=.90*width,color=colours[name],label=name.capitalize())
        motion.bar_label(art,fmt='%.1f',fontsize=8,padding=2)
    motion.set(xticks=x,xticklabels=['PCB','Cell bodies','Nickel strips'],ylabel=r'Peak displacement [$\mu$m]',ylim=(0,58))
    motion.set_title('Six original fasteners locked',fontsize=10)
    motion.legend(frameon=False,ncol=len(bars),fontsize=8)
    contact.axvline(1.,lw=.8,ls='--',color='#555555')
    contact.set(xlabel='Static load-step time',ylabel='Peak corner pressure [MPa]',xlim=(0,2.08),ylim=(0,None))
    contact.set_title('Case contact during tightening',fontsize=10)
    if len(materials)>1:contact.legend(frameon=False,fontsize=8)
    for ax in (motion,contact):ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18)
    fig.savefig(ROOT/'docs/figures/snug-preload.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--aluminium',action='store_true')
    draw(['nylon','aluminium'] if p.parse_args().aluminium else ['nylon'])
