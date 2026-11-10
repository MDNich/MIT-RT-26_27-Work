"""Compare signed lateral travel of the same cell and clamp reference for bare and both snug mounts."""
import numpy as np

from audit_local import ROOT, read
from film_identity import digest, write_json
from report_plot import plt
from stage_snug_fit import AUDIT

MODELS=('bare','snug125_nylon','snug125_aluminium')


def interval(result,axis):
    return np.array([result['axes'][axis][sign]['simultaneous_relative_xyz_mm'][0]
                     for sign in ('negative_X','positive_X')])


def summarize():
    records={};sources={};errors=[]
    for variant in MODELS:
        entries={}
        for method in ('native','exact'):
            path=AUDIT/f'{variant}_edge_cell_travel_{method}.json'
            row=read(path);assert row['variant']==variant and row['method']==method
            entries[method]=row;sources[path.name]=digest(path)
        native,exact=entries['native'],entries['exact']
        assert native['geometry']==exact['geometry']
        for axis in 'XYZ':
            assert native['axes'][axis]['excitation_sha256']==exact['axes'][axis]['excitation_sha256']
            a,b=interval(native,axis),interval(exact,axis)
            assert np.all(a*[-1,1]>0)
            errors.extend(abs(b-a)/abs(a))
        records[variant]=native
    fine_path=AUDIT/'snug125_nylon_mesh15_edge_cell_travel_exact.json'
    fine=read(fine_path);sources[fine_path.name]=digest(fine_path)
    for entry in [*records.values(),fine]:
        geom=entry['geometry'];reference=records['bare']['geometry']
        for k in ('washer_face_nodes_sha256','washer_faces','local_deck_sha256','local_pilot_mm'):
            assert geom[k]==reference[k]
        assert abs(geom['face_area_mm2']/reference['face_area_mm2']-1)<1e-6
        for axis in 'XYZ':
            assert entry['axes'][axis]['excitation_sha256']==records['bare']['axes'][axis]['excitation_sha256']
    result={}
    for axis in 'XYZ':
        limits={branch:1000*interval(r,axis) for branch,r in records.items()}
        peaks={key:float(abs(v).max()) for key,v in limits.items()}
        trimmed=max(1000*r['axes'][axis]['maximum_change_from_excluding_inner_rim_mm'] for r in records.values())
        fine_peak=float(1000*abs(interval(fine,axis)).max())
        nominal_exact=read(AUDIT/'snug125_nylon_edge_cell_travel_exact.json')
        fine_pct=100*(fine_peak/(1000*abs(interval(nominal_exact,axis)).max())-1)
        result[axis]=dict(signed_native_um={k:v.tolist() for k,v in limits.items()},peak_absolute_um=peaks,
                     change_vs_bare_pct={k:100*(peaks[k]/peaks['bare']-1) for k in MODELS[1:]},
                     trimmed_vs_full_washer_max_um=trimmed,independent_fine_nylon_peak_um=fine_peak,
                     fine_nylon_change_vs_nominal_exact_pct=float(fine_pct))
    write_json(AUDIT/'edge_travel_comparison.json',dict(axes=result,inputs=sources,
               largest_extremum_change_from_exact_integration_pct=100*float(max(errors)),
               scope='Nine-second seeded records, native nominal and independently integrated fine nylon. '
                     'All histories use the installed linearized contact state.'))
    return result


def draw(result):
    names=['Bare','Nylon','Aluminium'];colours=['#08357E','#3C78D8','#38761D']
    fig,(ax,bx)=plt.subplots(1,2,figsize=(7.7,2.65),layout='constrained',gridspec_kw={'width_ratios':[1.15,1]})
    for pos,name,variant,colour in zip([2,1,0],names,MODELS,colours,strict=True):
        a,b=result['X']['signed_native_um'][variant]
        ax.plot([a,b],[pos,pos],lw=2.4,color=colour,solid_capstyle='round')
        ax.scatter([a,b],[pos,pos],s=20,color=colour,zorder=3)
        ax.annotate(f'{a:.1f}',(a,pos),xytext=(0,6),textcoords='offset points',ha='center',fontsize=9)
        ax.annotate(f'{b:.1f}',(b,pos),xytext=(0,6),textcoords='offset points',ha='center',fontsize=9)
    ax.axvline(0,color='#888888',lw=.7,zorder=0)
    ax.set(yticks=[2,1,0],yticklabels=names,xlim=(-58,58),ylim=(-.35,2.55),
           xlabel=r'Signed travel along PCB X [$\mu$m]',title='Base X')
    for i,(variant,label,colour) in enumerate(zip(MODELS,names,colours,strict=True)):
        x=np.array([0,1])+(i-1)*.24
        vals=[result[a]['peak_absolute_um'][variant] for a in 'YZ']
        bars=bx.bar(x,vals,width=.22,color=colour,label=label)
        bx.bar_label(bars,fmt='%.2f',fontsize=8,padding=2)
    bx.set(xticks=[0,1],xticklabels=['Base Y','Base Z'],ylabel=r'Peak absolute X travel [$\mu$m]',
           title='Cross-axis response',ylim=(0,8.2))
    bx.legend(loc='upper right',frameon=False,fontsize=7)
    for panel in (ax,bx):
        panel.spines[['top','right']].set_visible(False)
        panel.set_axisbelow(True)
    ax.grid(axis='x',alpha=.15);bx.grid(axis='y',alpha=.15)
    fig.savefig(ROOT/'docs/figures/snug-edge-cell-travel.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw(summarize())
