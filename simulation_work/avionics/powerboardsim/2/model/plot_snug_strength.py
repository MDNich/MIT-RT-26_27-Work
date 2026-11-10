"""Plot snug-case tensile demand from the signed vibration histories and directional coupon references."""
import numpy as np

from audit_local import ROOT,read
from installation_material import PLA
from report_plot import plt


def draw():
    fig,axes=plt.subplots(1,3,figsize=(9,2.9),layout='constrained')
    x=np.arange(3);width=.35
    for j,(material,color) in enumerate([('nylon','#3C78D8'),('aluminium','#38761D')]):
        branch='snug125_'+material
        modal=read(ROOT/'validation/global'/(branch+'_basis.json'))
        values=[[],[],[]];away=[[],[]]
        for axis in 'XYZ':
            folder=ROOT/'validation/snug125'
            name=f'{branch}_{axis}_PLA_'
            record=read(folder/(name+'independent.json'))
            native=read(folder/(name+'native.json'))
            motion=read(ROOT/'validation/motion'/f'{branch}_motion_{axis}.json')
            assert native['native_basis_sha256']==modal['rst_sha256'] and native['coordinate_source_sha256']==motion['mcf_sha256']
            assert native['input_sha256']==motion['input_sha256']==record['input_sha256']
            check=read(folder/(name+'exact.json'))
            beam=read(ROOT/'validation/screw_vibration'/f'{branch}_{axis}.json')
            assert record['native_basis_sha256']==check['native_basis_sha256']==beam['native_basis_sha256']==modal['rst_sha256']
            assert record['input_sha256']==check['input_sha256']==beam['input_sha256']
            native_beam=read(ROOT/'validation/screw_vibration'/f'{branch}_{axis}_native_history.json')
            assert native_beam['mcf_sha256']==motion['mcf_sha256'] and native_beam['basis_sha256']==modal['rst_sha256']
            assert native_beam['max_relative_difference_from_independent_peak']<.005
            for i,metric in enumerate(['layer_tension_MPa','in_plane_tension_MPa']):
                for key,series in [('all',values[i]),('2mm_from_bearing',away[i])]:
                    peak=native['scopes'][key][metric]
                    assert abs(peak['maximum_MPa']/record['scopes'][key][metric]['maximum_MPa']-1)<.005
                    exact=check['scopes'][key][metric]
                    assert abs(exact['maximum_MPa']/peak['maximum_MPa']-1)<.005 and peak['coupon_reference_MPa']==PLA[metric]
                    series.append(peak['percent_of_coupon_mean'])
            values[2].append(max(row['tensile_MPa'] for row in native_beam['screws']))
        for i,ax in enumerate(axes):
            xpos=x+(j-.5)*width
            bars=ax.bar(xpos,values[i],width=.92*width,color=color,label=material.capitalize()+' screws')
            ax.bar_label(bars,fmt='%.0f',fontsize=8,padding=2)
            if i<2:
                ax.scatter(xpos,away[i],marker='_',s=48,c='white',linewidths=2.4,zorder=3)
                ax.scatter(xpos,away[i],marker='_',s=45,c='#08357E',linewidths=.9,zorder=4)
    for i,(ax,title) in enumerate(zip(axes,['PLA across layers','PLA in print plane','M4 screw shank'],strict=True)):
        ax.set(xticks=x,xticklabels=list('XYZ'),xlabel='Base excitation axis',title=title)
        ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.15)
        if i<2:
            ax.set_ylabel(r'Peak / coupon mean [\%]');ax.axhline(100,color='#7A0101',ls='--',lw=1)
        else:ax.set_ylabel('Peak longitudinal tension [MPa]')
        ax.set_ylim(0,ax.get_ylim()[1]*1.1)
    handles,labels=axes[2].get_legend_handles_labels()
    fig.legend(handles,labels,ncols=2,frameon=False,loc='outside lower center',fontsize=9)
    fig.savefig(ROOT/'docs/figures/snug-vibration-strength.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
