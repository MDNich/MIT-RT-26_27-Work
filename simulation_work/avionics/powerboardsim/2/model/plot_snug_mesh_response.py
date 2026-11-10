"""Plot board response and printed-case tensile demand on two matched nylon case meshes."""
import numpy as np

from audit_local import ROOT,read
from film_identity import digest
from report_plot import plt
from stage_snug_fit import AUDIT


def draw():
    evidence=read(AUDIT/'nylon_modal_mesh_comparison.json')
    fig,(board,stress)=plt.subplots(1,2,figsize=(8.25,2.73),layout='constrained')
    x=np.arange(3,dtype=float)
    for i,(model,color,marker) in enumerate(zip(evidence['models'],['#08357E','#38761D'],['o','s'],strict=True)):
        name=model['case'];branch=name.removesuffix('_basis')
        specfile=ROOT/'validation/independent_psd'/(name+'.json')
        assert digest(specfile)==model['spectrum_sha256']
        spectrum=read(specfile)
        u=[]
        tension=[]
        for axis in 'XYZ':
            u.append(1000*spectrum['base_cases'][axis]['scopes']['pcb']['peak_directional_RMS_mm'][2])
            record=read(AUDIT/(branch+'_'+axis+'_PLA_independent.json'))
            check=read(AUDIT/(branch+'_'+axis+'_PLA_exact.json'))
            assert record['native_basis_sha256']==check['native_basis_sha256']==spectrum['rst_sha256']==model['basis_rst_sha256']
            assert record['input_sha256']==check['input_sha256']
            peak=record['scopes']['all']['layer_tension_MPa']
            tension.append(peak['percent_of_coupon_mean'])
        label=f"{model['mesh_size_mm']:g} mm case mesh"
        for ax,values in ((board,u),(stress,tension)):
            ax.scatter(x+(i-.5)*.14,values,marker=marker,color=color,label=label,s=35,zorder=3)
    for ax,title,units in ((board,'Board-normal motion',r'Peak PCB displacement [$\mu$m RMS]'),
                           (stress,'Peak through-layer PLA tension',r'Percent of coupon mean [\%]')):
        ax.set(title=title,ylabel=units,xticks=x,xticklabels=['Base X','Base Y','Base Z'],xlim=(-.45,2.45))
        ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.17)
        ax.spines[['top','right']].set_visible(False)
    board.set_ylim(top=155);stress.set_ylim(top=105)
    stress.axhline(100,lw=.75,ls='--',color='#7A0101')
    handles,labels=board.get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=2,frameon=False,fontsize=8)
    fig.savefig(ROOT/'docs/figures/snug-nylon-mesh-response.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
