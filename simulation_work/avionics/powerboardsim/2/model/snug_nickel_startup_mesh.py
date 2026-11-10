"""Resolve the nickel trial-yield event on both case meshes under an identical base acceleration."""
import argparse
import re
import numpy as np

from audit_local import ROOT,read
from case_fit import GROUPS
from case_stress import corners,source
from film_cell_timestep import refined_coordinates
from film_identity import digest,verified,write_json
from nickel_vibration import early_crossing,element_set,signed_cache
from seeded_motion import FS,participation
from stage_snug_fit import AUDIT


def run(material,axis,campaign):
    mesh_file=AUDIT/(material+'_modal_mesh_comparison.json')
    meshes=read(mesh_file)['models']
    assert [m['mesh_size_mm'] for m in meshes]==[2,1.5]
    fit=read(ROOT/'validation/rigid_case_drawdown.json')
    bodies={r['native_material']:r['STEP_body'] for r in fit['records'] if r['STEP_body'] in GROUPS['nickel']}
    assert len(bodies)==6
    config=ROOT/'.runtime/local_inputs/damage_cont_nominal/config.json'
    verified(config,read(ROOT/'validation/local_inputs.json')['damage_cont_nominal']['files']['config.json'])
    limit=read(config)['yield_MPa']*1e6
    native_path=ROOT/'validation/motion'/f'snug125_{material}_motion_{axis}.json'
    native=read(native_path)
    path=ROOT/'.runtime/motion_loads'/(axis+'.txt')
    verified(path,native['input_sha256'])
    samples=np.arange(int(.1*FS)+2);acc=np.loadtxt(path,skiprows=1,max_rows=len(samples))
    assert np.allclose(acc[:,0],samples/FS,atol=5.1e-13,rtol=0)
    results=[];reference=None;mesh_rotation_delta=None
    for m in meshes:
        base,folder,modes=source(m['case'],campaign)
        static,st_folder,st=source(m['preload'],campaign)
        assert base['rst_sha256']==m['basis_rst_sha256'] and static['rst_sha256']==m['installed_rst_sha256']
        if reference is None:
            assert native['basis_rst_sha256']==base['rst_sha256']
        variant=m['case'].removesuffix('_basis')
        ctrl=read(ROOT/'validation/independent_motion'/f'{variant}_motion_{axis}.json')
        assert ctrl['basis_rst_sha256']==base['rst_sha256'] and ctrl['input_sha256']==native['input_sha256']
        log=folder/'solve.out';verified(log,ctrl['modal_listing_sha256'])
        ledger=read(ROOT/'.runtime/receipts'/campaign/m['preload']/'archived.json')
        deck=st_folder/'model.inp';verified(deck,next(row['sha256'] for row in ledger['files'] if row['name']=='model.inp'))
        cards=deck.read_text().upper()
        for mat in bodies:
            assert re.search(rf'^MP,EX,{mat},220000000000,',cards,re.M) and re.search(rf'^MP,NUXY,{mat},0\.305,',cards,re.M)
            assert not re.search(rf'^TB,[^,]*,{mat},',cards,re.M)
        elements,mats=element_set(st,bodies);other,assigned=element_set(modes,bodies)
        assert np.array_equal(elements,other) and np.array_equal(mats,assigned)
        nodes,mean=corners(st,st.nsets-1,'ENS',elements,6)
        original=st.mesh.nodes[np.searchsorted(st.mesh.nnum,nodes)]
        keys,axes=corners(st,st.nsets-1,'EUL',elements,3)
        keys2,axes2=corners(modes,0,'EUL',elements,3)
        assert np.array_equal(keys,keys2) and np.max(abs(axes-axes2))<1e-5
        if reference is None:
            reference=(elements.copy(),mats.copy(),nodes.copy(),original.copy(),axes.copy())
        else:
            assert all(np.array_equal(a,b) for a,b in zip((elements,mats,nodes),reference[:3],strict=True))
            assert np.max(abs(original-reference[3]))<1e-9
            # Each mesh has its own locked pose. Von Mises is invariant across those frames;
            # the preload and the perturbations must share a frame *within* each history.
            mesh_rotation_delta=float(np.max(abs(axes-reference[4])))
        shape,seal=signed_cache(campaign,base,static,modes,elements,nodes,mean)
        q,integration=refined_coordinates('linear_input_exact',acc[:,1],samples,modes.time_values,
                                          participation(log.read_text(errors='replace'),axis))
        events={}
        for cutoff in (4000,3500):
            n=int((modes.time_values<=cutoff).sum());assert n and (n==len(modes.time_values))==(cutoff==4000)
            index,event=early_crossing(shape[:n],mean,q[:,:n],limit)
            if event is not None:
                event.update(element=int(elements[index//4]),node=int(nodes[index]),STEP_body=bodies[mats[index//4]],
                             original_xyz_mm=(original[index]*1000).tolist())
            events[str(cutoff)]=dict(modes=n,first_crossing=event)
        results.append(dict(variant=variant,mesh_mm=m['mesh_size_mm'],basis_sha256=base['rst_sha256'],
                            preload_sha256=static['rst_sha256'],signed_tensor_sha256=digest(seal),
                            corner_count=len(nodes),events=events))
        print(variant,axis,[(k,x['first_crossing']['time_bracket_s'] if x['first_crossing'] else None)
                            for k,x in events.items()],flush=True)
    n=native['nickel_trial_crossing']
    nominal=results[0]['events']['4000']['first_crossing']
    assert (nominal is None)==(n is None)
    difference=None if nominal is None else nominal['sample']-round(n['time_bracket_s'][1]*FS)
    assert difference is None or abs(difference)<=2
    write_json(AUDIT/f'{material}_nickel_startup_mesh_{axis}.json',dict(axis=axis,models=results,
               nominal_native_minus_exact_samples=None if difference is None else -difference,
               maximum_cross_mesh_native_EUL_difference=mesh_rotation_delta,nominal_native_motion_sha256=digest(native_path),modal_comparison_sha256=digest(mesh_file),
               input_sha256=native['input_sha256'],reference_file_sha256=digest(config),
               reference_MPa=limit*1e-6,sample_rate_Hz=FS,window_s=samples[-1]/FS,integration=integration,
               scope='First sampled exceedance of the 185 MPa exploratory nickel yield reference by a signed '
                     'elastic von Mises trial stress at any unaveraged strip corner. Both meshes hold contact at bolt lock.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('material',choices=('nylon','aluminium'))
    p.add_argument('--axis',choices=('X','Y','Z'),required=True)
    p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();run(a.material,a.axis,a.campaign)
