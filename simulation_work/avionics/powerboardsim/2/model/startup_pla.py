"""Recover the first printed-PLA tensile reference crossings during the original acceleration ramp."""
import argparse
import re

import numpy as np
from scipy.spatial import cKDTree

from audit_local import ROOT, read
from case_stress import case_elements, corners, printed_compliance, source
from basis_comparison import field_files
from curved_cell_contact import contact_solids, sampled_clearance
from motion_surface import displacement_basis
from film_cell_timestep import refined_coordinates
from film_identity import digest, verified, write_json
from installation_material import PLA
from seeded_motion import FS, participation
from startup_proximity import coordinate_window
from study_cases import native_case


def components(stress):
    x,y,z,shear=stress[:,:4].T
    return np.column_stack(((x+y)*.5,(x-y)*.5,shear,z))*1e-6


def values(q,base,shapes,metric):
    if metric=='layer_tension_MPa':
        return q @ shapes[:,3,:].T+base[:,3]
    s=[q @ shapes[:,k,:].T+base[:,k] for k in range(3)]
    return s[0]+np.hypot(s[1],s[2])


def scan(q,base,shapes,metric,eligible):
    """Bound each corner over time, then evaluate every candidate at every station."""
    # For each modal coefficient the midpoint and half-range enclose every sampled value.
    high=q.max(0);low=q.min(0)
    centre=base+shapes@((high+low)*.5)
    radius=np.abs(shapes)@((high-low)*.5)
    upper=(centre[:,3]+radius[:,3] if metric=='layer_tension_MPa' else
           centre[:,0]+radius[:,0]+np.hypot(abs(centre[:,1])+radius[:,1],abs(centre[:,2])+radius[:,2]))
    # Probe times give a lower bound on the true maximum. Retain every corner that
    # could meet either this bound or the coupon reference, including the first crossing.
    probes=q[::256]
    floor=max(float(values(probes,base[b],shapes[b],metric).max()) for b in np.array_split(eligible,16) if len(b))
    limit=PLA[metric]
    possible=eligible[upper[eligible]>=min(floor,limit)-1e-8]
    assert len(possible)
    peak=np.full(len(q),-np.inf)
    for start in range(0,len(possible),256):
        take=possible[start:start+256]
        stress=values(q,base[take],shapes[take],metric)
        assert np.all(stress.max(0)<=upper[take]+1e-8)
        col=stress.argmax(1)
        row=np.arange(len(q))
        larger=stress[row,col]>peak
        peak[larger]=stress[row[larger],col[larger]]
    crossings=np.flatnonzero(peak>=limit)
    imax=int(peak.argmax())
    assert peak[imax]>=floor-1e-8
    def exact(i):
        full=values(q[i:i+1],base[eligible],shapes[eligible],metric).ravel()
        j=int(np.argmax(full))
        return dict(sample=int(i),time_s=i/FS,MPa=float(full[j]),corner=int(eligible[j]))
    top=exact(imax)
    assert abs(top['MPa']-peak[imax])<1e-8
    first=None
    if len(crossings):
        i=int(crossings[0]);assert i>0
        first=[exact(i-1),exact(i)]
        assert first[0]['MPa']<limit<=first[1]['MPa'] and abs(first[1]['MPa']-peak[i])<1e-8
    return dict(limit_MPa=limit,corners=len(eligible),candidates=len(possible),maximum=top,first_crossing=first)


def threshold_clearance(rst,modal,campaign,q,case,history):
    # Independent VTK intersection and signed distances at each first crossing in the all-corner search.
    stations=sorted({r['native']['first_crossing'][1]['sample'] for r in history.values()
                     if r['native']['first_crossing']})
    if not stations:
        return {}
    cap,cells=contact_solids(rst)
    solids=[cells.extract_cells(cells.cell_data['ansys_material_type']==k) for k in (176,191,187)]
    ids=np.unique(np.concatenate([solid.point_data['ansys_node_num'] for solid in [cap,*solids]]))
    indices=np.searchsorted(rst.mesh.nnum,ids)
    assert np.array_equal(ids,rst.mesh.nnum[indices])
    fields=field_files(case,campaign,modal['rst_sha256'],rst.nsets)
    phi=displacement_basis(rst,ids,fields)
    results={}
    for sample in stations:
        xyz=rst.mesh.nodes[indices]+(q[sample]@phi.reshape(len(phi),-1)).reshape(-1,3)
        gaps={key:sampled_clearance([cap,solid],ids,xyz,(2,3)) for key,solid in
              zip(('left','centre','right'),solids,strict=True)}
        assert all(row[2]['intersect']==row[3]['intersect'] for row in gaps.values())
        results[sample]=gaps
    return results


def run(variant,campaign):
    modal,folder,rst=source(variant+'_basis',campaign)
    preload,pre_dir,static=source(variant+'_static',campaign)
    elements=case_elements(rst,variant)
    assert np.array_equal(elements,case_elements(static,variant))
    ids,locked=corners(static,static.nsets-1,'ENS',elements,6)
    base=components(locked)
    xyz=static.mesh.nodes[np.searchsorted(static.mesh.nnum,ids)]*1000
    deck=pre_dir/'model.inp'
    ledger=read(ROOT/'.runtime/receipts'/campaign/preload['case']/'archived.json')
    verified(deck,next(x['sha256'] for x in ledger['files'] if x['name']=='model.inp'))
    ties=re.findall(r'(?im)^CERIG,(95000[1357]),(\d+),UXYZ\s*$',deck.read_text())
    assert {int(a) for a,b in ties}=={950001,950003,950005,950007}
    attached=sorted({int(b) for a,b in ties})
    where=np.searchsorted(static.mesh.nnum,attached)
    assert np.array_equal(static.mesh.nnum[where],attached)
    dist=cKDTree(1000*static.mesh.nodes[where]).query(xyz)[0]
    scopes={'all':np.arange(len(ids)),'at_least_2mm_from_bearings':np.flatnonzero(dist>=2)}
    compliance,shear_moduli=printed_compliance(deck.read_text())
    constitutive_errors=[]
    shapes=np.empty((len(ids),4,rst.nsets))
    for k in range(rst.nsets):
        mode_ids,stress=corners(rst,k,'ENS',elements,6)
        assert np.array_equal(mode_ids,ids)
        strain_ids,strain=corners(rst,k,'EEL',elements,7)
        assert np.array_equal(strain_ids,ids)
        predicted=np.column_stack((stress[:,:3]@compliance,stress[:,3:]/shear_moduli))
        constitutive_errors.append(float(np.linalg.norm(predicted-strain[:,:6])/np.linalg.norm(strain[:,:6])))
        shapes[:,:,k]=components(stress)
    assert max(constitutive_errors)<.005,max(constitutive_errors)
    assert np.array_equal(rst.time_values,modal['frequencies_Hz'])
    samples=np.arange(int(np.ceil(.1*FS))+1)
    for axis in 'XYZ':
        q,motion_path,motion=coordinate_window(variant,axis,campaign,modal,samples)
        spectrum=native_case(variant,'psd_'+axis)
        proof_path=ROOT/'validation/pla_stress'/(spectrum+'.json')
        proof=read(proof_path)
        assert proof['basis_sha256']==modal['rst_sha256'] and proof['preload_sha256']==preload['rst_sha256']
        critical=proof['independent_signed_waveform']
        key=(elements.repeat(4)==critical['critical_element']) & (ids==critical['critical_corner_node'])
        corner,=np.flatnonzero(key)
        ref=ROOT/'.runtime/post'/campaign/spectrum/'PLA_critical_history.npz'
        verified(ref,critical['cache_sha256'])
        with np.load(ref) as previous:
            assert np.allclose(shapes[corner,3],previous['modal_Z_Pa']*1e-6,rtol=1e-12,atol=1e-11)
            assert np.isclose(base[corner,3],float(previous['mean_MPa']),rtol=1e-12)
        inputs=ROOT/'.runtime/motion_loads'/(axis+'.txt')
        verified(inputs,motion['input_sha256'])
        forcing=np.loadtxt(inputs,skiprows=1,max_rows=len(samples))
        assert np.allclose(forcing[:,0],samples/FS,rtol=0,atol=5.1e-13)
        log=folder/'solve.out'
        src=read(ROOT/'validation/independent_motion'/(motion['case']+'.json'))
        verified(log,src['modal_listing_sha256'])
        gamma=participation(log.read_text(errors='replace'),axis)
        exact,ctrl=refined_coordinates('linear_input_exact',forcing[:,1],samples,rst.time_values,gamma)
        data={}
        for group,indices in scopes.items():
            for metric in ('in_plane_tension_MPa','layer_tension_MPa'):
                methods={}
                for method,coords,keep in [('native',q,slice(None)),('independent_exact',exact,slice(None)),
                                           ('native_3500_Hz',q,slice(0,np.searchsorted(rst.time_values,3500.,side='right')))]:
                    rec=scan(coords[:,keep],base,shapes[:,:,keep],metric,indices)
                    rec['retained_modes']=len(rst.time_values[keep])
                    for event in [rec['maximum'],*(rec['first_crossing'] or [])]:
                        j=event.pop('corner')
                        event.update(element=int(elements[j//4]),node=int(ids[j]),distance_to_bearing_nodes_mm=float(dist[j]))
                    methods[method]=rec
                data.setdefault(group,{})[metric]=methods
        gaps=threshold_clearance(rst,modal,campaign,q,modal['case'],data['all'])
        write_json(ROOT/'validation/startup_ramp'/f'{variant}_{axis}_PLA.json',
                   dict(variant=variant,campaign=campaign,base_axis=axis,samples=len(samples),through_s=samples[-1]/FS,
                        basis_rst_sha256=modal['rst_sha256'],static_rst_sha256=preload['rst_sha256'],
                        maximum_modal_constitutive_relative_L2=max(constitutive_errors),
                        native_motion_sha256=digest(motion_path),forcing_sha256=motion['input_sha256'],
                        original_PLA_corner_check_sha256=digest(proof_path),independent_check=ctrl,scopes=data,
                        cells_at_first_native_stress_crossings=gaps,
                        scope='Signed prestressed modal stresses added to the locked tightening stress at each '
                              'unaveraged PLA element corner. The plane and layer directions are those of the printed '
                              'material. Crossings are comparisons with uniaxial coupon stresses in a fixed-contact '
                              'elastic model. Actual print failure or impact loads require separate evidence.'))
        print(variant,axis,[(k,v['native']['maximum']['MPa'],(v['native']['first_crossing'] or [{}])[-1].get('time_s')) for k,v in data['all'].items()],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('variant',choices=['stand3_nylon','stand3_aluminium'])
    p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();run(a.variant,a.campaign)
