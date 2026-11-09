"""Compare all three native base spectra on the bare board and both raised installations."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from audit_local import ROOT,read
from film_identity import digest,write_json
from psd_comparison import published_values
from study_cases import native_case


def axis_results(axis):
    assert axis in ('X','Y','Z')
    base=ROOT/'validation'
    rows={}
    for variant in ('bare','stand3_nylon','stand3_aluminium'):
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


def draw(data):
    fig,axes=plt.subplots(1,2,figsize=(8.0,2.8),layout='constrained')
    for j,(key,label,col,mk) in enumerate([('bare','Bare board','#08357E','o'),('stand3_nylon','3 mm / nylon','#3C78D8','s'),
                                            ('stand3_aluminium','3 mm / aluminium','#38761D','^')]):
        for ax,metric in zip(axes,['pcb_Z_displacement_um','pcb_equivalent_stress_MPa'],strict=True):
            values=[data[a][key][metric] for a in 'XYZ']
            ax.scatter(np.arange(3)+(j-1)*.14,values,color=col,marker=mk,s=35,label=label,zorder=3)
    for ax,title,ylabel in zip(axes,['Peak PCB Z displacement','Peak PCB equivalent stress'],['µm RMS','MPa RMS'],strict=True):
        ax.set_title(title,fontsize=11)
        ax.set(xticks=[0,1,2],xticklabels=['Base X','Base Y','Base Z'],xlim=(-.4,2.4),ylabel=ylabel)
        ax.set_ylim(bottom=0);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
    h,l=axes[0].get_legend_handles_labels()
    fig.legend(h,l,loc='outside lower center',ncol=3,fontsize=8,frameon=False)
    fig.savefig(ROOT/'docs/figures/raised-native-spectra.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    records={axis:axis_results(axis) for axis in 'XYZ'};draw(records)
    write_json(ROOT/'validation/psd_comparisons/three_axis_native.json',dict(base_cases=records,
        scope='Peak one-sigma responses in three separate 20–2000 Hz base excitations, at the tightened contact states. '
              'Each maximum is taken over the specified material scope. The base axes are separate load cases.'))
