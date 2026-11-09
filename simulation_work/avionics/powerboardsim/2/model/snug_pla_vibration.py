"""Search every printed-case corner and every integration station for the largest signed tensile stress."""
import argparse
import re

import numpy as np
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS
from scipy.spatial import cKDTree

from audit_local import ROOT, read
from audit_motion import native_series
from case_stress import case_elements, corners, printed_compliance, source
from film_identity import verified, write_json
from film_cell_timestep import refined_coordinates
from installation_material import PLA
from seeded_motion import FS, FRAMES, integrate, participation
from startup_pla import components, values


def interval_upper(low,high,base,shapes,metric):
    # Interval arithmetic bounds the simultaneous in-plane principal stress from above.
    centre=base+shapes@((low+high)*.5)
    radius=abs(shapes)@((high-low)*.5)
    if metric=='layer_tension_MPa':
        return centre[:,3]+radius[:,3]
    return centre[:,0]+radius[:,0]+np.hypot(abs(centre[:,1])+radius[:,1],abs(centre[:,2])+radius[:,2])


def maximum(q,base,shapes,indices,metric):
    # Start with a valid lower bound from evaluated corners and times.
    probes=q[::max(1,len(q)//64)]
    best=-np.inf
    for group in np.array_split(indices,min(32,len(indices))):
        sample=values(probes,base[group],shapes[group],metric)
        row,col=np.unravel_index(sample.argmax(),sample.shape)
        if sample[row,col]>best:
            best=float(sample[row,col]);lead=int(group[col])
    seed=values(q,base[lead:lead+1],shapes[lead:lead+1],metric).ravel()
    station=int(seed.argmax());best=float(seed[station]);corner=lead
    bound=interval_upper(q.min(0),q.max(0),base,shapes,metric)
    possible=indices[bound[indices]>=best-1.e-8]
    # Every other corner is bounded by an already observed value. Tighten the bound
    # for each time block before multiplying the retained modal stress vectors.
    coeff=shapes[possible];locked=base[possible]
    evaluations=0
    for start in range(0,len(q),4096):
        block=q[start:start+4096]
        upper=interval_upper(block.min(0),block.max(0),locked,coeff,metric)
        active=np.flatnonzero(upper>=best-1.e-8)
        evaluations+=len(block)*len(active)
        for i in range(0,len(active),64):
            take=active[i:i+64]
            stress=values(block,locked[take],coeff[take],metric)
            assert np.all(stress.max(0)<=upper[take]+1.e-8)
            row,col=np.unravel_index(stress.argmax(),stress.shape)
            if stress[row,col]>best:
                best=float(stress[row,col]);station=start+int(row);corner=int(possible[take[col]])
    full=values(q[station:station+1],base[indices],shapes[indices],metric).ravel()
    assert abs(full.max()-best)<1.e-7
    return corner,dict(sample=station,time_s=station/FS,maximum_MPa=best,
                       coupon_reference_MPa=PLA[metric],percent_of_coupon_mean=100*best/PLA[metric],
                       corners_in_scope=len(indices),possible_corners=len(possible),evaluated_corner_stations=evaluations)


def check_bounds():
    rng=np.random.default_rng(1285)
    q=rng.normal(size=(8201,6));shapes=rng.normal(size=(23,4,6));base=rng.normal(size=(23,4))
    for metric in ('layer_tension_MPa','in_plane_tension_MPa'):
        ids=np.arange(1,23,2)
        a=values(q,base[ids],shapes[ids],metric);row,col=np.unravel_index(a.argmax(),a.shape)
        i,r=maximum(q,base,shapes,ids,metric)
        assert (row,ids[col])==(r['sample'],i) and abs(a.max()-r['maximum_MPa'])<1.e-10


def setup(variant,campaign):
    modal,folder,rst=source(variant+'_basis',campaign)
    preload,base_dir,static=source(variant+'_static',campaign)
    elements=case_elements(rst,variant)
    assert np.array_equal(elements,case_elements(static,variant))
    ids,locked=corners(static,static.nsets-1,'ENS',elements,6)
    base=components(locked)
    ledger=read(ROOT/'.runtime/receipts'/campaign/preload['case']/'archived.json')
    deck=base_dir/'model.inp';verified(deck,next(r['sha256'] for r in ledger['files'] if r['name']=='model.inp'))
    text=deck.read_text()
    masters=re.findall(r'(?im)^CERIG,(95000[1357]),(\d+),UXYZ\s*$',text)
    assert {int(m) for m,_ in masters}=={950001,950003,950005,950007}
    tied=np.array(sorted({int(n) for _,n in masters}))
    node_ids=static.mesh.nnum
    assert np.array_equal(node_ids[np.searchsorted(node_ids,tied)],tied)
    assert np.array_equal(node_ids[np.searchsorted(node_ids,ids)],ids)
    xyz=1000*static.mesh.nodes[np.searchsorted(node_ids,ids)]
    distance=cKDTree(1000*static.mesh.nodes[np.searchsorted(node_ids,tied)]).query(xyz)[0]
    order=np.argsort(rst._eeqv);pos=order[np.searchsorted(rst._eeqv[order],elements)]
    assert np.array_equal(rst.mesh.enum[pos],elements) and np.array_equal(rst._eeqv[pos],elements)
    assert np.array_equal(np.stack([rst.mesh.elem[i][10:14] for i in pos]).ravel(),ids)
    shapes=np.empty((len(ids),4,rst.nsets));law,shear=printed_compliance(text);errors=[]
    for mode in range(rst.nsets):
        pointers,_,off=rst._element_solution_header(mode)
        def field(tag,width):
            data=rst._cfile.read_element_data(pointers[pos],ELEMENT_INDEX_TABLE_KEYS.index(tag),off)
            rows=np.stack(data)
            assert rows.shape==(len(elements),4*width) and np.isfinite(rows).all()
            return rows.reshape(-1,width).astype(float)
        stress=field('ENS',6);strain=field('EEL',7)
        if mode in (0,rst.nsets-1):
            control_ids,control=corners(rst,mode,'ENS',elements,6)
            assert np.array_equal(control_ids,ids) and np.array_equal(control,stress)
        predicted=np.column_stack((stress[:,:3]@law,stress[:,3:]/shear))
        errors.append(float(np.linalg.norm(predicted-strain[:,:6])/np.linalg.norm(strain[:,:6])))
        shapes[:,:,mode]=components(stress)
    assert max(errors)<.005
    return modal,folder,rst.time_values,preload,elements,ids,base,shapes,xyz,distance,max(errors)


def run(variant,campaign,method,axes):
    check_bounds()
    modal,folder,freq,preload,elems,ids,base,shapes,xyz,distance,error=setup(variant,campaign)
    assert np.array_equal(freq,modal['frequencies_Hz'])
    for axis in axes:
        motion=variant+'_motion_'+axis
        clip=read(ROOT/'validation/independent_motion'/(motion+'.json'))
        assert clip['basis_rst_sha256']==modal['rst_sha256']
        if method=='independent':
            listing=folder/'solve.out'
            verified(listing,clip['modal_listing_sha256'])
            _,q,_=integrate(freq,participation(listing.read_text(errors='replace'),axis),axis,slice(None))
            cache=ROOT/'.runtime/post'/campaign/motion/'independent/coordinates.npz'
            verified(cache,clip['clip_sha256'])
            with np.load(cache) as data:assert np.array_equal(q[FRAMES],data['coordinates'])
            coordinate_source=clip['modal_listing_sha256']
        elif method=='exact':
            listing=folder/'solve.out'
            verified(listing,clip['modal_listing_sha256'])
            load=ROOT/'.runtime/motion_loads'/(axis+'.txt');verified(load,clip['input_sha256'])
            forcing=np.loadtxt(load,skiprows=1)
            samples=np.arange(9*FS+1)
            assert np.allclose(forcing[:,0],samples/FS,rtol=0,atol=5.1e-13)
            q,_=refined_coordinates('linear_input_exact',forcing[:,1],samples,freq,
                                     participation(listing.read_text(errors='replace'),axis))
            coordinate_source=clip['input_sha256']
        else:
            native=read(ROOT/'validation/motion'/(motion+'.json'))
            assert native['basis_rst_sha256']==modal['rst_sha256']
            mcf=ROOT/'.runtime/archive'/campaign/motion/'file.mcf';verified(mcf,native['mcf_sha256'])
            q=native_series(mcf,freq)
            coordinate_source=native['mcf_sha256']
        assert q.shape==(9*FS+1,len(freq)) and np.isfinite(q).all()
        records={}
        for group,indices in [('all',np.arange(len(ids))),('2mm_from_bearing',np.flatnonzero(distance>=2.))]:
            records[group]={}
            for metric in ('layer_tension_MPa','in_plane_tension_MPa'):
                i,peak=maximum(q,base,shapes,indices,metric)
                peak.update(element=int(elems[i//4]),node=int(ids[i]),xyz_mm=xyz[i].tolist(),
                            distance_to_bearing_nodes_mm=float(distance[i]))
                records[group][metric]=peak
                print(variant,method,axis,group,metric,peak['maximum_MPa'],'MPa',flush=True)
        write_json(ROOT/'validation/snug125'/f'{variant}_{axis}_PLA_{method}.json',dict(
            variant=variant,method=method,campaign=campaign,axis=axis,native_basis_sha256=modal['rst_sha256'],
            native_static_sha256=preload['rst_sha256'],coordinate_source_sha256=coordinate_source,
            input_sha256=clip['input_sha256'],modal_stress_strain_error=error,history_samples=len(q),
            scopes=records,scope='Largest signed layer-normal and in-plane principal tension over all eligible '
            'unaveraged PLA element corners and all 589,825 samples. Preload and modal tensors are combined '
            'at the same corner and instant. The fixed-contact elastic calculation uses the reported coupon '
            'means as material references; local bearing compliance and changing cell contact affect interpretation.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=('snug125_nylon','snug125_aluminium'))
    p.add_argument('--campaign',default='nov08_01')
    p.add_argument('--method',choices=('native','independent','exact'),default='independent')
    p.add_argument('--axes',choices=('XYZ','X','Y','Z'),default='XYZ')
    args=p.parse_args()
    run(args.variant,args.campaign,args.method,args.axes)
