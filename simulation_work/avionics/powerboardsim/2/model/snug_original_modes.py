"""Identify the low coarse-board mode and its participating mass from the recovered native spectra."""
import re
import numpy as np

from audit_local import ROOT,read
from dpf_readback import export
from film_identity import digest,verified,write_json
from modal_correspondence import native_points
from native_rst import read_rst
from stage_snug_fit import AUDIT


def inspect(campaign='nov08_01'):
    base='bare_original_sturm'
    def result(case):
        proof=read(ROOT/'validation/global'/f'{case}.json')
        assert proof['case']==case and proof['campaign']==campaign and proof['sets']==20
        path=ROOT/'.runtime/archive'/campaign/case/'file.rst';verified(path,proof['rst_sha256'])
        return read_rst(path),proof
    r0,p0=result(base)
    ids,xyz=native_points(r0)
    num,u=r0.nodal_displacement(0)
    idx=np.searchsorted(num,ids);assert np.array_equal(num[idx],ids)
    base_vector=u[idx,:3].ravel();base_vector/=np.linalg.norm(base_vector)
    output={}
    for screw in ('nylon','aluminium'):
        name='snug125_'+screw+'_original_sturm'
        run,proof=result(name)
        candidate,points=native_points(run)
        assert np.array_equal(ids,candidate) and np.allclose(points,xyz,rtol=0,atol=1e-10)
        retry=read(ROOT/'validation'/f'{name}_input.json');directory=ROOT/'.runtime/archive'/campaign/name
        ledger=read(ROOT/'.runtime/receipts'/campaign/name/'archived.json')
        listing=directory/'solve.out';shas={f['name']:f['sha256'] for f in ledger['files']}
        verified(listing,shas['solve.out']);verified(directory/'model.inp',retry['retry_input_sha256'])
        body_name=re.search(r"Elements for Body 107 '([^']+)'",(directory/'model.inp').read_text())[1]
        assert body_name.split('|')==['COMP_L3','COMP_L3']
        folder=export(name,campaign,[1,2,3]);grid=run.grid
        flags=np.isin(grid.cell_data['ansys_elem_type_num'],(185,186,187))
        tags=grid.cell_data['ansys_material_type']
        l3=grid.extract_cells(flags & (tags==107));assert l3.n_cells==1
        nums=np.unique(l3.point_data['ansys_node_num'])
        others=np.unique(grid.extract_cells(flags & (tags!=107)).point_data['ansys_node_num'])
        vectors=[]
        for k in (1,2,3):
            stem=folder/f'set_{k:04d}'
            n=np.fromfile(stem.with_suffix('.ids'),'<i4');v=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
            order=np.argsort(n)
            def select(nodes):
                i=order[np.searchsorted(n[order],nodes)];assert np.array_equal(n[i],nodes)
                return v[i]
            selected=select(ids).ravel();mac=float((np.dot(selected,base_vector)/np.linalg.norm(selected))**2)
            amp=np.linalg.norm(v,axis=1);peak=int(n[amp.argmax()])
            vectors.append(dict(rank=k,Hz=float(run.time_values[k-1]),maximum_nodal_id=peak,
                L3_to_overall_peak=float(np.linalg.norm(select(nums),axis=1).max()/amp.max()),
                other_solids_to_overall_peak=float(np.linalg.norm(select(others),axis=1).max()/amp.max()),
                MAC_to_bare_original_first_mode=mac,U_sha256=digest(stem.with_suffix('.u'))))
        txt=listing.read_text(errors='replace');mass=float(re.search(r'^\s*TOTAL MASS\s*=\s*(\S+)',txt,re.M)[1])
        fractions={}
        for axis in 'XYZ':
            m=re.search(r'PARTICIPATION FACTOR CALCULATION \*+\s*'+axis+r'\s+DIRECTION(.*?)^\s*sum\s+',txt,re.S|re.M|re.I)
            a=np.array([[float(v) for v in line.split()] for line in m[1].splitlines() if line.split() and line.split()[0].isdigit()])
            assert a.shape==(20,8) and np.allclose(run.time_values,a[:,1],atol=.006,rtol=2e-6)
            assert np.isclose(a[0,7],a[0,5]/mass,atol=1e-10,rtol=2e-4)
            fractions[axis]=float(a[0,7])
        output[screw]=dict(case=name,rst_sha256=proof['rst_sha256'],bare_rst_sha256=p0['rst_sha256'],
            checked_listing_sha256=shas['solve.out'],matched_common_solid_nodes=len(ids),component=body_name,
            component_elements=l3.n_cells,mode1_effective_fraction_of_total_mass=fractions,modes=vectors,
            incomplete_first_attempt_modes=retry['produced_modes'])
    write_json(AUDIT/'original_mode_identity.json',dict(cases=output,
        scope='Original unpreloaded board mesh only. Displacements are normalized eigenvectors, and MAC uses unweighted translations on the identical original solids.'))


if __name__=='__main__':inspect()
