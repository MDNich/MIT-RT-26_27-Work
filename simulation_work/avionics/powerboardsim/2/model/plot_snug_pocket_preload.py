"""Show the native preload force and the first loss of consistency of the installed contact tangent."""
import numpy as np
from audit_local import ROOT,read
from film_identity import verified
from report_plot import plt

def draw():
    data=read(ROOT/'validation/snug125/nylon_pocket_preload.json')
    repeat=read(ROOT/'validation/snug125/snug125_nylon_out2_static_contacts.json')
    assert data['native_force_rst_sha256']==repeat['rst_sha256']
    history=data['force_history']
    assert history==repeat['resultant_force_check']
    t=[v['load_time'] for v in repeat['contact_history']]
    f=[v['resultant_N'] for v in history]
    fig,(loads,clock)=plt.subplots(1,2,figsize=(8.35,2.83),layout='constrained')
    loads.plot([0,*t],[0,*f],'-o',color='#08357E',lw=1.4,ms=4.4)
    loads.axvline(1,color='.55',ls='--',lw=.8)
    loads.text(.48,.91,'Tightening',ha='center',color='#08357E',transform=loads.get_xaxis_transform(),fontsize=9)
    loads.text(1.48,.91,'Bolts locked',ha='center',color='#08357E',transform=loads.get_xaxis_transform(),fontsize=9)
    loads.annotate(f'{f[-1]:.3f} N',(t[-1],f[-1]),(-7,10),textcoords='offset points',ha='right',fontsize=9)
    loads.set(xlabel='Native load-step parameter',ylabel='Middle-pocket resultant [N]',xlim=(-.07,2.10),ylim=(-.35,10.8))
    colors=['#08357E','#3C78D8','#38761D']
    for i,(axis,color) in enumerate(zip('XYZ',colors,strict=True)):
        records=data['axes'][axis]['integrations']
        p,n=[records['independent'][s]['sample']*1000/65536 for s in ('positive','negative')]
        clock.plot([p,n],[i,i],lw=1.2,color=color)
        clock.scatter(p,i,s=36,facecolors='white',edgecolors=color,zorder=3)
        clock.scatter(n,i,s=36,color=color,zorder=3)
        clock.text(max(p,n)+.45,i,f'{max(p,n):.1f} ms',va='center',fontsize=9)
    clock.scatter([],[],s=27,facecolors='white',edgecolors='#08357E',label='Positive increment')
    clock.scatter([],[],s=27,color='#08357E',label='Negative increment')
    clock.legend(frameon=False,fontsize=8,loc='lower left',ncol=1)
    clock.set(xlabel='Time from start of base excitation [ms]',xlim=(8,31.6),ylim=(2.96,-.4),
              yticks=range(3),yticklabels=['Base X','Base Y','Base Z'])
    for a in (loads,clock):
        a.spines[['right','top']].set_visible(False);a.grid(axis='x',alpha=.16);a.set_axisbelow(True)
    fig.savefig(ROOT/'docs/figures/snug-pocket-preload.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)

if __name__=='__main__':draw()
