"""Measure remaining geometric overlap inside both contact domains on the common physical mesh."""
import sys
import numpy as np
import pyvista as pv
from audit_contact_patch import native_field
from audit_local import ROOT,read
from basis_comparison import field_files
from clearance_response import surface
from contact_patch import BRANCH,FS,integrate,local_fields,nodal_field
from film_identity import verified,write_json
from native_rst import read_rst

def compare(campaign):
    case=BRANCH+'_basis'
    proof=read(ROOT/'validation/global'/f'{case}.json')
    store=ROOT/'.runtime/archive'/campaign
    verified(store/case/'file.rst',proof['rst_sha256'])
    modes=read_rst(store/case/'file.rst')
    stems=field_files(case,campaign,proof['rst_sha256'],modes.nsets)
    state=local_fields(campaign,9)
    _,q,_=integrate(state['freq'],state['gamma'],'X',np.array([state['sample']]))
    shells={}
    for label,materials in [('PLA',[850]),('cells',[176,187,191])]:
        shell,_,ids,_=surface(modes,materials)
        shell.points+=sum(nodal_field(stems[i+1],ids)*w for i,w in enumerate(q[0]))
        assert shell.n_open_edges==0
        shells[label]=(shell,ids)
    def overlap(pla,cell):
        ans={}
        for name,source,target in [('cell_inside_PLA',cell,pla),('PLA_inside_cell',pla,cell)]:
            xyz=np.vstack([source.points,source.cell_centers().points])
            delta=xyz-state['center']
            select=(delta[:,0]**2+delta[:,2]**2<.008**2)&(xyz[:,1]>=state['axial_span'][0]-.006)&(xyz[:,1]<=state['axial_span'][1]+.006)
            cloud=pv.PolyData(xyz[select])
            sd=cloud.compute_implicit_distance(target).point_data['implicit_distance']
            ans[name]=dict(samples=len(sd),inside_by_more_than_1um=int((sd< -1.e-6).sum()),largest_sampled_depth_mm=float(max(0,-sd.min())*1000))
        return ans
    parent=overlap(shells['PLA'][0],shells['cells'][0])
    cases={}
    for radius in (9,15):
        state=local_fields(campaign,radius)
        for label,kind in [('free','free_v1'),('contact','contact_eq1')]:
            key=f'patch_{BRANCH}_span{radius}_{kind}'
            evidence=read(ROOT/'validation/contact_patch'/f'{key}.json')
            verified(store/key/'file.rst',evidence['rst_sha256'])
            r=read_rst(store/key/'file.rst')
            k=int(np.flatnonzero(np.isclose(r.time_values,2.,rtol=0,atol=1e-9))[0])
            local_xyz=state['xyz']+native_field(r,k,state['nodes'])
            surfaces={}
            for body,(template,ids) in shells.items():
                new=template.copy();mask=np.isin(ids,state['nodes'])
                new.points[mask]=local_xyz[np.searchsorted(state['nodes'],ids[mask])]
                surfaces[body]=new
            row=evidence['force_history'][k]
            cases[key]=dict(radius_mm=radius,contact=label=='contact',parent_rst_sha256=evidence['rst_sha256'],
                force_vector_N=row['cells_reaction_N'],force_norm_N=float(np.linalg.norm(row['cells_reaction_N'])),
                worst_force_imbalance_N=max(a['imbalance_N'] for a in evidence['force_history']),
                max_free_PLA_departure_from_parent_um=evidence['endpoint_checks']['2']['max_free_PLA_departure_from_parent_um'],
                active_faces=row.get('closed_faces',0),loaded_faces_touching_domain_cut=row.get('loaded_cut_edge_faces',0),
                native_loaded_corner_penetration_mm=row.get('maximum_loaded_corner_penetration_mm'),
                geometric_screen=overlap(surfaces['PLA'],surfaces['cells']))
    f=[r['force_norm_N'] for r in cases.values() if r['contact']]
    rec=dict(campaign=campaign,global_basis_sha256=proof['rst_sha256'],source_sample_s=state['sample']/FS,
             parent_screen=parent,cases=cases,relative_force_change_9_to_15=f[1]/f[0]-1,
             scope='Quasistatic force for prescribed lateral motion of the cells and outer cut, sampled at the peak linear state. Signed distances use vertices and facet centres of closed assembled skins within the common central 8 mm band.')
    write_json(ROOT/'validation/contact_patch_comparison.json',rec)
    from report_plot import plt
    fig,ax=plt.subplots(figsize=(7.2,2.7),layout='constrained')
    for radius,color in [(9,'#08357E'),(15,'#38761D')]:
        result=read(ROOT/'validation/contact_patch'/f'patch_{BRANCH}_span{radius}_contact_eq1.json')
        history=result['force_history']
        for loading,style in [(True,'-'),(False,'--')]:
            samples=[r for r in history if (1<=r['time']<=2 if loading else 2<=r['time']<=3)]
            fraction=np.array([r['time']-1 if loading else 3-r['time'] for r in samples])
            loads=np.array([np.linalg.norm(r['cells_reaction_N']) for r in samples])*1.e-3
            ax.plot(fraction,loads,style,color=color,lw=1.6,label=f'{radius} mm, '+('loading' if loading else 'unloading'))
    ax.set_xlabel('Fraction of the prescribed board motion at 2.9276 s')
    ax.set_ylabel('Resultant cell reaction [kN]')
    ax.set_xlim(0,1.02);ax.set_ylim(bottom=0);ax.legend(frameon=False,fontsize=8)
    ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/raised-nylon-contact-replay.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    for k,v in cases.items():print(k,round(v['force_norm_N'],2),[(s,round(x['largest_sampled_depth_mm'],4)) for s,x in v['geometric_screen'].items()])
if __name__=='__main__':compare(sys.argv[1])
