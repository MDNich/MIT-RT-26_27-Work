"""Plot locked native frequencies, independent RMS responses and sampled cell clearances."""
import argparse
import numpy as np

from audit_local import ROOT, read
from film_identity import digest
from report_plot import plt


def plots(screws):
    fig, (modes, motion)=plt.subplots(1,2,figsize=(8.4,2.65),layout='constrained')
    branches=['bare',*['snug125_'+s for s in screws]]
    labels=['Bare',*[s.capitalize() for s in screws]]
    colors=['#08357E',*['#3C78D8' if s=='nylon' else '#38761D' for s in screws]]
    bare=read(ROOT/'validation/global/bare_basis.json')
    positions=np.arange(3);width=.76/len(branches)
    for i,(branch,label,color) in enumerate(zip(branches,labels,colors,strict=True)):
        name=branch+'_basis'
        proof=read(ROOT/'validation/global'/(name+'.json'))
        rms_path=ROOT/'validation/independent_psd'/(name+'.json')
        rms=read(rms_path)
        cutoff=read(ROOT/'validation/modal_cutoff'/(name+'.json'))
        assert rms['rst_sha256']==cutoff['native_rst_sha256']==proof['rst_sha256']
        assert cutoff['full_response_sha256']==digest(rms_path) and rms['baseline_5pct_screen_passed']
        y=len(branches)-1-i
        f=np.asarray(proof['frequencies_Hz']);modes.vlines(f[f<=1300],y-.15,y+.15,color=color,lw=1.5)
        if branch!='bare':
            match=read(ROOT/'validation/modal_pairs'/(name+'.json'))
            assert match['native_source_sha256']=={'bare_basis':bare['rst_sha256'],name:proof['rst_sha256']}
        z=[rms['base_cases'][ax]['scopes']['pcb']['peak_directional_RMS_mm'][2]*1000 for ax in 'XYZ']
        motion.bar(positions+(i-(len(branches)-1)/2)*width,z,width=width*.9,label=label,color=color)
    modes.set(xlabel='Natural frequency [Hz]',title='Native modes after bolt lock',
              yticks=np.arange(len(branches))[::-1],yticklabels=labels,xlim=(200,1300),ylim=(-.5,len(branches)-.5))
    modes.tick_params(axis='y',length=0)
    motion.set(xticks=positions,xticklabels=['Base X','Base Y','Base Z'],title='Independent spectrum integration',
               ylabel=r'Peak PCB Z motion [$\mu$m RMS]')
    motion.legend(frameon=False,ncol=len(branches),fontsize=8,loc='upper left')
    motion.set_ylim(0,motion.get_ylim()[1]*1.12)
    for ax in [modes,motion]:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='x' if ax is modes else 'y',alpha=.15)
        ax.set_axisbelow(True)
    fig.savefig(ROOT/'docs/figures/snug-locked-vibration.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)

    fig,axes=plt.subplots(1,len(screws),figsize=(8.4,2.6),layout='constrained',sharey=True,squeeze=False)
    axes=axes[0]
    observed_frames=None
    for ax,screw in zip(axes,screws,strict=True):
        name='snug125_'+screw
        rec=read(ROOT/'validation/snug125'/(name+'_seeded_contact.json'))
        assert rec['native_basis_sha256']==read(ROOT/'validation/global'/(name+'_basis.json'))['rst_sha256']
        samples=rec['axes']['Z']['samples'];frames=[s['frame_one_based'] for s in samples]
        if observed_frames is not None:assert frames==observed_frames
        observed_frames=frames
        series=[rec['locked_geometry'],*[s['gaps'] for s in samples]]
        for j,(rows,station,color) in enumerate(zip(series,['Bolt lock',*[f'Frame {f}' for f in frames]],
                                                ['#08357E','#3C78D8','#38761D'],strict=True)):
            by_body={r['body']:r for r in rows if r['subdivision']==3}
            gaps=[by_body[body]['minimum_signed_target_vertex_gap_mm']*1000 for body in (4,19,15)]
            ax.bar(positions+(j-1)*.25,gaps,width=.23,color=color,label=station)
        ax.axhline(0,color='.25',lw=.75)
        ax.set(xticks=positions,xticklabels=['Left cell','Middle','Right cell'],title=screw.capitalize()+' screws')
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    axes[0].set_ylabel(r'Signed sampled gap [$\mu$m]')
    axes[-1].legend(frameon=False,fontsize=8,ncol=3,loc='lower center',bbox_to_anchor=(.5,-.37))
    fig.savefig(ROOT/'docs/figures/snug-seeded-gaps.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('screws',nargs='+',choices=('nylon','aluminium'))
    plots(parser.parse_args().screws)
