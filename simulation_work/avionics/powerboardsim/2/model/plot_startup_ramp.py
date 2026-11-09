"""Compare the chronology of gap closure and coupon stress crossings for the raised mounts."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT, read
from film_identity import digest, write_json
from installation_material import PLA
from seeded_motion import FS


DIRECTORY=ROOT/'validation/startup_ramp'
BRANCHES=('stand3_nylon','stand3_aluminium')
METRICS=('layer_tension_MPa','in_plane_tension_MPa')


def encounters(gaps):
    assert all(not c['unresolved_intervals_samples'] for c in gaps['cells'].values())
    return [(a,cell) for cell,c in gaps['cells'].items() for a,b in c['crossing_intervals_samples']]


def comparison():
    cases={}
    for branch in BRANCHES:
        for axis in 'XYZ':
            key=f'{branch}_{axis}'
            sp=DIRECTORY/(key+'_PLA.json');gp=DIRECTORY/(key+'_gap.json')
            stress,gap=read(sp),read(gp)
            assert stress['native_motion_sha256']==gap['native_motion_sha256']
            assert stress['basis_rst_sha256']==gap['basis_rst_sha256']
            assert stress['samples']==gap['samples']==int(np.ceil(FS*.1))+1
            assert stress['maximum_modal_constitutive_relative_L2']<.005
            closure=min(encounters(gap),default=None)
            out=dict(stress_audit_sha256=digest(sp),skin_audit_sha256=digest(gp),
                     first_sampled_intersection=(dict(cell=closure[1],sample=closure[0],
                         bracket_ms=[(closure[0]-1)*1000/FS,closure[0]*1000/FS]) if closure else None))
            for metric in METRICS:
                full=stress['scopes']['all'][metric]
                away=stress['scopes']['at_least_2mm_from_bearings'][metric]
                prior=full['native']['first_crossing']
                comp={}
                for method in ('independent_exact','native_3500_Hz'):
                    other=full[method]['first_crossing']
                    assert bool(prior)==bool(other)
                    comp[method]=dict(first_crossing_change_samples=other[1]['sample']-prior[1]['sample'] if prior else None,
                        maximum_change_MPa=full[method]['maximum']['MPa']-full['native']['maximum']['MPa'])
                row=dict(maximum_MPa=full['native']['maximum']['MPa'],away_maximum_MPa=away['native']['maximum']['MPa'],
                         first_bracket_ms=[v['time_s']*1000 for v in prior] if prior else None,sensitivity=comp)
                if prior:
                    k=prior[1]['sample'];skins=stress['cells_at_first_native_stress_crossings'][str(k)]
                    for cell,b in gap['cells'].items():
                        found=any(start<=k<=end for start,end in b['crossing_intervals_samples'])
                        assert skins[cell]['2']['intersect']==skins[cell]['3']['intersect']==found
                    row['sampled_min_cell_vertex_gap_mm']=min(s['3']['minimum_signed_vertex_gap_mm'] for s in skins.values())
                out[metric]=row
            if axis=='X':
                assert closure
                sensitivity={}
                for method in ('independent_exact','native_3500_Hz'):
                    path=DIRECTORY/f'{key}_gap_{method}.json'
                    variant=read(path)
                    assert variant['native_motion_sha256']==gap['native_motion_sha256'] and variant['coordinate_method']==method
                    sample,cell=min(encounters(variant))
                    sensitivity[method]=dict(audit_sha256=digest(path),cell=cell,sample=sample,delta_samples=sample-closure[0])
                out['first_X_intersection_sensitivity']=sensitivity
            cases[key]=out
    write_json(DIRECTORY/'comparison.json',dict(cases=cases,sampling_Hz=FS,
        scope='Sampled sequence in the original ramp of each raised linear vibration model. The printed PLA '
              'screens use the reported uniaxial tensile means. The computed surface encounters indicate when '
              'the open-gap assumption breaks down. The nickel yield comparison is reported separately.'))
    return cases


def draw(cases):
    fig,axes=plt.subplots(1,2,figsize=(8.1,3.2),layout='constrained',sharey=True)
    for ax,metric,title in zip(axes,METRICS,('Across layers','In the print plane'),strict=True):
        for i,(branch,colour,label) in enumerate(zip(BRANCHES,('#3C78D8','#38761D'),('Nylon screws','Aluminium screws'),strict=True)):
            rows=[cases[f'{branch}_{a}'][metric] for a in 'XYZ']
            x=np.arange(3)+(i-.5)*.34
            ax.bar(x,[r['maximum_MPa'] for r in rows],color=colour,width=.31,label=label)
            ax.scatter(x,[r['away_maximum_MPa'] for r in rows],facecolors='white',edgecolors='#242424',
                       linewidths=.8,s=25,zorder=3,label='At least 2 mm from bearing nodes' if i==0 else None)
        limit=PLA[metric]
        ax.axhline(limit,ls='--',lw=1,color='#7A0101')
        ax.set(title=f'{title} ({limit:.1f} MPa)',xticks=range(3),xticklabels=['Base X','Base Y','Base Z'],ylim=(0,110),xlim=(-.55,2.55))
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('Maximum in the startup ramp [MPa]')
    handles,labels=axes[0].get_legend_handles_labels()
    by_label=dict(zip(labels,handles))
    ordered=['Nylon screws','Aluminium screws','At least 2 mm from bearing nodes']
    fig.legend([by_label[k] for k in ordered],ordered,loc='outside lower center',ncol=3,frameon=False,fontsize=8.5)
    fig.savefig(ROOT/'docs/figures/startup-pla-stress.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw(comparison())
