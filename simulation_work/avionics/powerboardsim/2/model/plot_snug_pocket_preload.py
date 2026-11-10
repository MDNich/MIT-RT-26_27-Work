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
    mesh=read(ROOT/'validation/snug125/nylon_force_mesh_comparison.json')
    nominal,fine=mesh['runs']
    assert nominal['rst_sha256']==repeat['rst_sha256'] and nominal['times']==t
    assert nominal['force_history']==history and fine['mesh_size_mm']==1.5
    fine_force=[v['resultant_N'] for v in fine['force_history']]
    loads.plot([0,*t],[0,*f],'-o',color='#08357E',lw=1.35,ms=3.7,label='2.0 mm')
    loads.plot([0,*fine['times']],[0,*fine_force],'--s',color='#38761D',lw=1.35,ms=3.4,label='1.5 mm')
    loads.axvline(1,color='.55',ls=':',lw=.8)
    loads.legend(frameon=False,fontsize=8,loc='upper right')
    loads.set(xlabel='Native load-step parameter',ylabel='Case contact resultant [N]',xlim=(-.07,2.10),ylim=(0,None))
    colors=['#08357E','#3C78D8','#38761D']
    signed=read(ROOT/'validation/snug125/snug125_nylon_pocket_unloading.json')
    for i,(axis,color) in enumerate(zip('XYZ',colors,strict=True)):
        records=data['axes'][axis]['integrations']
        p,n=[records['independent'][s]['sample']*1000/65536 for s in ('positive','negative')]
        assert records['independent']['positive']['sample']==signed['axes'][axis]['integrations']['native']['first_crossing']['sample']
        clock.plot([p,n],[i,i],lw=1.2,color=color)
        clock.scatter(p,i,s=36,facecolors='white',edgecolors=color,zorder=3)
        clock.scatter(n,i,s=36,color=color,zorder=3)
        clock.annotate(f'{p:.1f} ms',(p,i),xytext=(0,6),textcoords='offset points',ha='center',va='bottom',fontsize=9)
    clock.scatter([],[],s=27,facecolors='white',edgecolors='#08357E',label='Relieves compression')
    clock.scatter([],[],s=27,color='#08357E',label='Adds compression')
    clock.legend(frameon=False,fontsize=8,loc='lower left',ncol=1)
    clock.set(xlabel='Time from start of base excitation [ms]',xlim=(8,31.6),ylim=(2.96,-.55),
              yticks=range(3),yticklabels=['Base X','Base Y','Base Z'])
    for a in (loads,clock):
        a.spines[['right','top']].set_visible(False);a.grid(axis='x',alpha=.16);a.set_axisbelow(True)
    fig.savefig(ROOT/'docs/figures/snug-pocket-preload.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)

if __name__=='__main__':draw()
