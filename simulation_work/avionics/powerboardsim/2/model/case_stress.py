"""Recover signed tightening and direction-specific random stresses on the printed case."""
import argparse
import re

import numpy as np

from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from independent_psd import spectrum_input,moments
from native_rst import read_rst
from pcb_dynamic_stress import equivalent
from seeded_motion import FS,integrate,participation
from scipy.spatial import cKDTree
from study_cases import native_case


def source(case,campaign):
    proof=read(ROOT/'validation/global'/f'{case}.json')
    assert proof['case']==case and proof['campaign']==campaign
    folder=ROOT/'.runtime/archive'/campaign/case
    verified(folder/'file.rst',proof['rst_sha256'])
    return proof,folder,read_rst(folder/'file.rst')


def case_elements(raw):
    data=raw.grid.cell_data
    elements=np.sort(data['ansys_elem_num'][(data['ansys_material_type']==850)&(data['ansys_elem_type_num']==187)])
    assert len(elements)==16108 and len(np.unique(elements))==len(elements)
    return elements


def corners(raw,k,field,elements,width):
    enum,values,nodes=raw.element_solution_data(k,field)
    i=np.searchsorted(enum,elements)
    assert np.array_equal(enum[i],elements)
    node=np.asarray([nodes[j] for j in i])
    v=np.asarray([values[j] for j in i],dtype=np.float64)
    assert node.shape==(len(elements),4) and v.shape==(len(elements),4*width) and np.isfinite(v).all()
    return node.ravel(),v.reshape(-1,width)


def static(variant,campaign):
    case=native_case(variant,'static')
    proof,folder,r=source(case,campaign)
    elements=case_elements(r);k=r.nsets-1
    ids,stress=corners(r,k,'ENS',elements,6)
    sb,eps=corners(r,k,'EEL',elements,7)
    sa,euler=corners(r,k,'EUL',elements,3)
    assert np.array_equal(ids,sb) and np.array_equal(ids,sa)
    # Check the orthotropic law using the actual input card for each property.
    deck=(folder/'model.inp').read_text()
    def prop(key):
        return float(re.search(r'(?im)^MP,'+key+r',850,([^\s!]+)',deck)[1])
    e=np.array([prop('EX'),prop('EY'),prop('EZ')])
    nu=np.array([prop('PRXY'),prop('PRYZ'),prop('PRXZ')])
    compliance=np.diag(1/e)
    for i,j,v in ((0,1,nu[0]),(1,2,nu[1]),(0,2,nu[2])):
        compliance[i,j]=compliance[j,i]=-v/e[i]
    predicted=np.column_stack([stress[:,:3]@compliance,stress[:,3:]/[prop('GXY'),prop('GYZ'),prop('GXZ')]])
    err=np.linalg.norm(eps[:,:6]-predicted)/np.linalg.norm(eps[:,:6])
    assert err<.005,err
    def peak(col):
        i=int(np.argmax(col))
        return dict(MPa=float(col[i]*1e-6),element=int(elements[i//4]),node=int(ids[i]))
    axes={a:dict(tension=peak(stress[:,j]),compression_magnitude=peak(-stress[:,j])) for j,a in enumerate('XYZ')}
    rec=dict(case=case,campaign=campaign,rst_sha256=proof['rst_sha256'],printed_SOLID187=len(elements),
             element_corners=len(ids),normal_stress=axes,equivalent_peak=peak(equivalent(stress)),
             largest_local_axis_rotation_component_deg=float(abs(euler).max()),elastic_law_relative_L2=float(err),
             scope='Signed stress on the case after tightening. XYZ are its material axes; Z is the assumed print-layer normal.')
    write_json(ROOT/'validation/pla_stress'/f'{case}.json',rec)
    return rec


def spectrum(variant,axis,campaign):
    case=native_case(variant,'psd_'+axis)
    proof,folder,result=source(case,campaign)
    basis,bfolder,modal=source(native_case(variant,'basis'),campaign)
    elements=case_elements(result)
    assert np.array_equal(elements,case_elements(modal))
    nodes,stored=corners(result,[3,1],'ENS',elements,11)
    _,angles=corners(result,[3,1],'EUL',elements,3)
    target=np.column_stack([stored[:,:6],stored[:,10]])
    assert np.min(target)>=0
    deck,frequency_knots,density,zeta=spectrum_input(axis)
    table=bfolder/'solve.out'
    ledger=read(ROOT/'.runtime/receipts'/campaign/basis['case']/'archived.json')
    verified(table,next(r['sha256'] for r in ledger['files'] if r['name']=='solve.out'))
    f=np.asarray(basis['frequencies_Hz']);assert np.array_equal(f,modal.time_values)
    gamma=participation(table.read_text(errors='replace'),axis)
    cov,_=moments(f,gamma,frequency_knots,density,zeta,.125)
    eig,vec=np.linalg.eigh(cov)
    assert eig.min()>=-1e-13*eig.max()
    factor=vec*np.sqrt(np.maximum(eig,0))
    tensor=np.empty((len(nodes),6,len(f)))
    for k in range(len(f)):
        ordered,s=corners(modal,k,'ENS',elements,6)
        assert np.array_equal(ordered,nodes)
        tensor[:,:,k]=s
    predicted=np.empty_like(target)
    for i in range(0,len(nodes),4096):
        a=tensor[i:i+4096]@factor
        predicted[i:i+4096,:6]=np.linalg.norm(a,axis=2)
        # Apply the von Mises quadratic form to the signed correlated stresses.
        v=equivalent(a.transpose(0,2,1))
        predicted[i:i+4096,6]=np.linalg.norm(v,axis=1)
    keys=['XX','YY','ZZ','XY','YZ','XZ','equivalent']
    relative=np.linalg.norm(predicted-target,axis=0)/np.linalg.norm(target,axis=0)
    peak_diff=abs(predicted.max(axis=0)/target.max(axis=0)-1)
    assert max(relative.max(),peak_diff.max())<.01,(relative,peak_diff)
    j=np.searchsorted(result.mesh.nnum,nodes)
    assert np.array_equal(result.mesh.nnum[j],nodes)
    drive=read(ROOT/'validation/pla_stress'/f"{native_case(variant,'static')}.json")
    static_proof,static_dir,base=source(drive['case'],campaign)
    assert static_proof['rst_sha256']==drive['rst_sha256']
    n0,mean=corners(base,base.nsets-1,'ENS',elements,6)
    assert np.array_equal(n0,nodes)
    static_deck=static_dir/'model.inp'
    static_ledger=read(ROOT/'.runtime/receipts'/campaign/drive['case']/'archived.json')
    verified(static_deck,next(row['sha256'] for row in static_ledger['files'] if row['name']=='model.inp'))
    coupled=re.findall(r'(?im)^CERIG,(95000[1357]),(\d+),UXYZ\s*$',static_deck.read_text())
    assert {int(p) for p,n in coupled}=={950001,950003,950005,950007}
    attached=np.array(sorted(set(int(n) for p,n in coupled)));positions=base.mesh.nnum
    bearing=cKDTree(1000*base.mesh.nodes[np.searchsorted(positions,attached),:3])
    locations=1000*base.mesh.nodes[np.searchsorted(positions,nodes),:3]
    distance=bearing.query(locations)[0]
    by_distance=[]
    for clearance in (0,2,5,10):
        keep=np.flatnonzero(distance>=clearance);i=keep[np.argmax(target[keep,2])]
        by_distance.append(dict(minimum_distance_from_bearing_nodes_mm=clearance,corner_count=len(keep),
                                Z_RMS_MPa=float(target[i,2]*1e-6),element=int(elements[i//4]),node=int(nodes[i])))
    critical=int(np.argmax(target[:,2]))
    times,coords,_=integrate(f,gamma,axis,slice(None))
    history=1e-6*(coords@tensor[critical,2]+mean[critical,2])
    rms=float(np.std(history[FS:-1]));expected=float(target[critical,2]*1e-6)
    assert abs(rms/expected-1)<.025,(rms,expected)
    def event(i):
        return dict(time_s=float(times[i]),stress_MPa=float(history[i]))
    peak=int(np.argmax(history));minimum=int(np.argmin(history))
    clip=ROOT/'.runtime/post'/campaign/case/'PLA_critical_history.npz'
    clip.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(clip,signed_stress_MPa=history,modal_Z_Pa=tensor[critical,2],mean_MPa=mean[critical,2]*1e-6)
    response=dict(source='Independent Newmark integration of the October single-axis realization',
        number_of_samples=len(times),sample_rate_Hz=FS,critical_corner_node=int(nodes[critical]),
        critical_element=int(elements[critical//4]),distance_from_bearing_nodes_mm=float(distance[critical]),
        stationary_1_to_9_s_RMS_MPa=rms,maximum=event(peak),minimum=event(minimum),cache_sha256=digest(clip))
    peaks={}
    for k,name in enumerate(keys):
        i=int(np.argmax(target[:,k]))
        peaks[name]=dict(native_RMS_MPa=float(target[i,k]*1e-6),independent_peak_RMS_MPa=float(predicted[:,k].max()*1e-6),
            element=int(elements[i//4]),node=int(nodes[i]),position_mm=(1000*result.mesh.nodes[j[i],:3]).tolist(),
            field_relative_L2=float(relative[k]),peak_relative_difference=float(peak_diff[k]))
        if k<6:peaks[name]['signed_static_MPa_at_same_corner']=float(mean[i,k]*1e-6)
    rec=dict(case=case,campaign=campaign,basis_sha256=basis['rst_sha256'],rst_sha256=proof['rst_sha256'],
             preload_sha256=drive['rst_sha256'],excitation_deck_sha256=digest(deck),element_corners=len(nodes),fields=peaks,
             bearing_proximity=by_distance,independent_signed_waveform=response,
             largest_local_axis_rotation_component_deg=float(abs(angles).max()),
             scope='Native one-sigma stress in the element material axes at the tightened contact state. Complete corner fields checked by independent covariance integration. Static mean and random RMS are reported separately.')
    write_json(ROOT/'validation/pla_stress'/f'{case}.json',rec)
    return rec


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant')
    parser.add_argument('load',choices=['static','X','Y','Z'])
    parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args()
    q=static(args.variant,args.campaign) if args.load=='static' else spectrum(args.variant,args.load,args.campaign)
    print(q['case'],q['element_corners'],'corner records')
