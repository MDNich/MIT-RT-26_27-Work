"""Measure sensitivity of the three-axis PCB stress maxima to truncation of the native modal basis."""
import argparse

import numpy as np
from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from independent_psd import moments,spectrum_input
from native_rst import read_rst
from pcb_dynamic_stress import equivalent
from seeded_motion import participation
from study_cases import native_case


def signed_basis(variant,campaign):
    name=variant+'_basis'
    proof=read(ROOT/'validation/global'/(name+'.json'))
    assert proof['case']==name and proof['campaign']==campaign
    archive=ROOT/'.runtime/archive'/campaign/name
    verified(archive/'file.rst',proof['rst_sha256'])
    cache=ROOT/'.runtime/post'/campaign/(variant+'_films')/'pcb_stress'
    meta=read(cache/'basis.json');assert meta['rst_sha256']==proof['rst_sha256']
    assert np.array_equal(proof['frequencies_Hz'],meta['frequencies_Hz'])
    tensor=np.load(cache/'tensors.npy',mmap_mode='r')
    with np.load(cache/'locations.npz') as z:
        elements=z['element'];counts=z['counts'];nodes=z['node']
    assert tensor.shape==(len(meta['frequencies_Hz']),len(nodes),6)
    manifest=ROOT/'validation/pcb_stress_cutoff'/(name+'_sources.json')
    if manifest.is_file():
        saved=read(manifest);assert saved['rst_sha256']==proof['rst_sha256']
        for path,key in [('locations.npz','locations_sha256'),('tensors.npy','tensors_sha256')]:
            verified(cache/path,saved[key])
    else:
        modal=read_rst(archive/'file.rst')
        g=modal.grid.cell_data;mask=(g['ansys_material_type']==208)&np.isin(g['ansys_elem_type_num'],[185,186,187])
        assert np.array_equal(np.sort(g['ansys_elem_num'][mask]),elements)
        assert np.array_equal(modal.time_values,meta['frequencies_Hz'])
        for k in range(modal.nsets):
            enum,stress,labels=modal.element_solution_data(k,'ENS')
            ix=np.searchsorted(enum,elements);assert np.array_equal(enum[ix],elements)
            assert np.array_equal([len(labels[i]) for i in ix],counts) and np.array_equal(np.concatenate([labels[i] for i in ix]),nodes)
            original=np.concatenate([stress[i].reshape(len(labels[i]),-1)[:,:6] for i in ix])
            assert np.array_equal(original,tensor[k])
        write_json(manifest,dict(case=name,rst_sha256=proof['rst_sha256'],locations_sha256=digest(cache/'locations.npz'),
                   tensors_sha256=digest(cache/'tensors.npy'),modes=modal.nsets,corners=len(nodes),elements=len(elements)))
    ledger=read(ROOT/'.runtime/receipts'/campaign/name/'archived.json')
    h=next(v['sha256'] for v in ledger['files'] if v['name']=='solve.out')
    verified(archive/'solve.out',h)
    return tensor,elements,counts,nodes,np.array(meta['frequencies_Hz']),(archive/'solve.out').read_text(errors='replace'),manifest


def combine(tensor,cov,check_components):
    eigen,vectors=np.linalg.eigh(cov)
    assert eigen.min()>-1.e-12*eigen.max()
    L=(vectors*np.sqrt(np.maximum(0,eigen))).T
    rows=tensor.shape[1];n=len(eigen)
    out=np.empty(rows)
    components=np.empty((rows,6)) if check_components else None
    for lo in range(0,rows,4096):
        hi=min(lo+4096,rows)
        samples=(L@np.ascontiguousarray(tensor[:n,lo:hi]).reshape(n,-1)).reshape(n,hi-lo,6)
        out[lo:hi]=np.linalg.norm(equivalent(samples),axis=0)
        if check_components:components[lo:hi]=np.linalg.norm(samples,axis=0)
    return out,components


def run(variant,campaign,axes):
    tensor,elements,counts,nodes,freq,listing,manifest=signed_basis(variant,campaign)
    numbered=np.repeat(elements,counts)
    for axis in axes:
        name=native_case(variant,'psd_'+axis)
        proof=read(ROOT/'validation/global'/(name+'.json'))
        assert proof['case']==name and proof['campaign']==campaign
        src=ROOT/'.runtime/archive'/campaign/name/'file.rst';verified(src,proof['rst_sha256'])
        rst=read_rst(src);enum,values,labels=rst.element_solution_data([3,1],'ENS')
        ii=np.searchsorted(enum,elements)
        assert np.array_equal(enum[ii],elements) and np.array_equal(np.concatenate([labels[i] for i in ii]),nodes)
        actual=np.concatenate([values[i].reshape(-1,11) for i in ii])
        assert actual.shape==(len(nodes),11)
        del values,labels
        path,fk,sk,damping=spectrum_input(axis)
        gamma=participation(listing,axis)
        cov,_=moments(freq,gamma,fk,sk,damping,.125)
        record={}
        for cutoff in (2000,3000,3500,4000):
            n=int(np.searchsorted(freq,cutoff,side='right'));assert n
            full=cutoff==4000
            field,components=combine(tensor,cov[:n,:n],full)
            peak=int(field.argmax())
            record[cutoff]=dict(modes=n,peak_MPa=float(field[peak]*1e-6),element=int(numbered[peak]),node=int(nodes[peak]))
            if full:
                diff=np.column_stack([components,field])-actual[:,[0,1,2,3,4,5,10]]
                rel=np.linalg.norm(diff,axis=0)/np.linalg.norm(actual[:,[0,1,2,3,4,5,10]],axis=0)
                assert n==len(freq) and np.max(rel)<.001,rel
                native=proof['native_psd_fields']['scopes']['pcb']
                assert (record[cutoff]['element'],record[cutoff]['node'])==(native['stress_element'],native['stress_node'])
                assert np.isclose(record[cutoff]['peak_MPa'],native['equivalent_stress_rms_Pa']*1.e-6,rtol=.001)
        for v in record.values():v['peak_change_from_full_percent']=100*(v['peak_MPa']/record[4000]['peak_MPa']-1)
        out=dict(case=name,campaign=campaign,rst_sha256=proof['rst_sha256'],signed_modes_sha256=digest(manifest),
                 spectrum_sha256=digest(path),matched_corners=len(nodes),cutoff_Hz=record,full_field_relative_L2=rel.tolist(),
                 scope='Independent modal covariance applied to signed tensor components before equivalent stress. Input spectrum '
                       'and damping are fixed. These cutoffs test the modes available through 4 kHz.')
        write_json(ROOT/'validation/pcb_stress_cutoff'/(name+'.json'),out)
        print(name,record[4000],record[3500],max(rel),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('variant');p.add_argument('axes',nargs='?',default='XYZ')
    p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();assert a.axes and all(c in 'XYZ' for c in a.axes);run(a.variant,a.campaign,a.axes)
