"""Compare the same populated-board nodes after locking all six existing fasteners, with an independent DPF control."""
import json
import numpy as np
from audit_local import ROOT,read
from dpf_readback import export
from native_rst import read_rst
from film_identity import digest


def compare(case,camp='nov08_01'):
    results={};nodes_by={};values_by={};geom_by={};analyses={}
    for key in ('bare_static',case):
        proof=read(ROOT/'validation/global'/f'{key}.json');assert proof['campaign']==camp
        rst=ROOT/'.runtime/archive'/camp/key/'file.rst';r=read_rst(rst)
        folder=export(key,camp,[r.nsets]);stem=folder/f'set_{r.nsets:04d}'
        nums=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        s=np.argsort(nums);nums=nums[s];u=u[s]
        assert len(nums)==len(np.unique(nums)) and np.isfinite(u).all()
        if key=='bare_static':
            n0,v0=r.nodal_displacement(r.nsets-1);assert np.array_equal(n0,nums)
            error=float(np.max(np.abs(v0[:,:3]-u)))
            assert error<1.e-11,error
        raw=ROOT/'.runtime/archive'/camp/key/'bolt_preload_audit.csv'
        clamp=np.loadtxt(raw,delimiter=',',skiprows=1)[-6:]
        i=np.searchsorted(nums,clamp[:,2].astype(int))
        assert np.array_equal(nums[i],clamp[:,2]) and np.max(abs(u[i,0]-clamp[:,3]))<1e-11
        typ=r.grid.cell_data['ansys_elem_type_num'];mat=r.grid.cell_data['ansys_material_type'];out={};nodes_by[key]={};values_by[key]={};geom_by[key]={}
        solid=np.isin(typ,[185,186,187])
        for name,mask in [('all_original_solids',solid&(mat<850)),('pcb',solid&(mat==208)),
            ('cells',solid&np.isin(mat,[176,187,191])),('nickel',solid&np.isin(mat,[174,179,180,186,189,193])),('case',solid&(mat==850))]:
            if not mask.any():continue
            sub=r.grid.extract_cells(mask);tag=sub.point_data['ansys_node_num'];order=np.argsort(tag);ids=tag[order]
            j=np.searchsorted(nums,ids);assert np.array_equal(nums[j],ids)
            vals=u[j]*1000;norm=np.linalg.norm(vals,axis=1);imax=np.argmax(norm)
            out[name]=dict(count=len(ids),peak_total_U_mm=float(norm[imax]),node=int(ids[imax]),peak_abs_XYZ_mm=np.max(abs(vals),axis=0).tolist())
            nodes_by[key][name]=ids;values_by[key][name]=vals;geom_by[key][name]=sub.points[order]
        analyses[key]=dict(source_rst_sha256=proof['rst_sha256'],native_DPF_U_sha256=digest(stem.with_suffix('.u')),
                    native_DPF_ID_sha256=digest(stem.with_suffix('.ids')),locked_bolt_N=clamp[:,4].tolist(),scopes=out)
    for name in nodes_by['bare_static']:
        assert np.array_equal(nodes_by['bare_static'][name],nodes_by[case][name])
        assert np.allclose(geom_by['bare_static'][name],geom_by[case][name],atol=1.e-10,rtol=0)
        u0=values_by['bare_static'][name];u1=values_by[case][name];ids=nodes_by[case][name]
        d=np.linalg.norm(u1-u0,axis=1);j=d.argmax();ratio=np.linalg.norm(u1,axis=1).max()/np.linalg.norm(u0,axis=1).max()
        results[name]=dict(matched_nodes=len(ids),ratio_of_peak_total_U=float(ratio),maximum_pointwise_change_mm=float(d[j]),node_of_maximum_change=int(ids[j]))
    report=dict(bare='bare_static',cased=case,campaign=camp,models=analyses,same_node_comparison=results,bare_DPF_vs_legacy_max_component_error_m=error,
        contact_fields=read(ROOT/'validation/global'/f'{case}.json')['installed_contact_summary'],
        scope='Six original bolts locked; surrogate case attachments and no applied vibration. Maximum displacement is relative to the undeformed geometry.')
    out=ROOT/'validation/static';out.mkdir(exist_ok=True);(out/(case+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    import sys
    q=compare(*sys.argv[1:]);print(q['same_node_comparison'])
