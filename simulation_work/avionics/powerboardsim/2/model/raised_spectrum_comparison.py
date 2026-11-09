"""Compare the native base spectra for the bare board and both screw materials at one fit."""
from report_plot import plt
import numpy as np
from audit_local import ROOT,read
from film_identity import digest,write_json
from psd_comparison import published_values
from study_cases import native_case


def axis_results(axis,fit='stand3'):
    assert axis in ('X','Y','Z')
    base=ROOT/'validation'
    rows={}
    for variant in ('bare',fit+'_nylon',fit+'_aluminium'):
        name=native_case(variant,'psd_'+axis)
        path=base/'global'/(name+'.json');data=read(path)
        assert data['case']==name and data['campaign']=='nov08_01'
        f=data['native_psd_fields']['scopes']
        if variant=='bare':
            assert data['october_native_comparison']['metric_count']==17
        else:
            proof=read(base/'psd_comparisons'/(variant+'_'+axis+'.json'))
            assert proof['case_evidence_sha256']==digest(path) and proof['bare_evidence_sha256']==rows['bare']['audit_sha256']
            values=published_values(axis,f)
            assert len(values)==17 and all(np.isclose(proof['metrics'][k]['cased'],val,rtol=1e-9) for k,(val,unit) in values.items())
        rows[variant]=dict(case=name,audit_sha256=digest(path),rst_sha256=data['rst_sha256'],
            pcb_Z_displacement_um=1000*f['pcb']['directional_rms_u_mm'][2],
            pcb_equivalent_stress_MPa=f['pcb']['equivalent_stress_rms_Pa']*1e-6,
            pcb_stress_maximum_element=f['pcb']['stress_element'],pcb_stress_maximum_node=f['pcb']['stress_node'],
            nickel_equivalent_stress_MPa=f['nickel']['equivalent_stress_rms_Pa']*1e-6)
    return rows


def draw(data,fit='stand3'):
    snug=fit=='snug125'
    seat='1.25 mm' if snug else '3 mm'
    fig,axes=plt.subplots(1,2,figsize=(8.0,2.8),layout='constrained')
    for j,(key,label,col,mk) in enumerate([('bare','Bare board','#08357E','o'),(fit+'_nylon',seat+' / nylon','#3C78D8','s'),
                                            (fit+'_aluminium',seat+' / aluminium','#38761D','^')]):
        for ax,metric in zip(axes,['pcb_Z_displacement_um','pcb_equivalent_stress_MPa'],strict=True):
            values=[data[a][key][metric] for a in 'XYZ']
            ax.scatter(np.arange(3)+(j-1)*.14,values,color=col,marker=mk,s=35,label=label,zorder=3)
    for ax,title,ylabel in zip(axes,['Peak PCB Z displacement','Peak PCB equivalent stress'],['µm RMS','MPa RMS'],strict=True):
        ax.set_title(title,fontsize=11)
        ax.set(xticks=[0,1,2],xticklabels=['Base X','Base Y','Base Z'],xlim=(-.4,2.4),ylabel=ylabel)
        ax.set_ylim(bottom=0);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
    h,l=axes[0].get_legend_handles_labels()
    fig.legend(h,l,loc='outside lower center',ncol=3,fontsize=8,frameon=False)
    name='snug-native-spectra.pdf' if snug else 'raised-native-spectra.pdf'
    fig.savefig(ROOT/'docs/figures'/name,metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit',choices=('stand3','snug125'),default='stand3')
    fit=parser.parse_args().fit
    records={axis:axis_results(axis,fit) for axis in 'XYZ'}
    draw(records,fit)
    output=('snug125/three_axis_native.json' if fit=='snug125' else 'psd_comparisons/three_axis_native.json')
    write_json(ROOT/'validation'/output,dict(base_cases=records,
        scope='Peak one-sigma responses in three separate 20–2000 Hz base excitations, at the tightened contact states. '
              'Each maximum is taken over the specified material scope. The base axes are separate load cases.'))
