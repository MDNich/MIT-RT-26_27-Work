"""Recover signed shank stresses for the four snug-case screws during the matched nine-second excitation."""
import argparse
import numpy as np
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS

from audit_local import ROOT, read
from case_stress import source
from audit_motion import native_series
from film_identity import digest, verified, write_json
from independent_psd import moments, spectrum_input
from seeded_motion import excitation, FS, integrate, participation
from stage_snug_fit import input_record


def screw_elements(result):
    mesh=result.grid.cell_data
    elements=np.sort(mesh['ansys_elem_num'][mesh['ansys_etype']==851])
    assert len(elements)==4
    order=np.argsort(result._eeqv)
    positions=order[np.searchsorted(result._eeqv[order],elements)]
    assert np.array_equal(result._eeqv[positions],elements)
    assert np.array_equal(result.mesh.enum[positions],elements)
    ends=[result.mesh.elem[i][10:12] for i in positions]
    assert np.array_equal(ends,np.arange(950001,950009).reshape(4,2))
    return elements,positions


def section(result,k,positions,field):
    pointers,_,offset=result._element_solution_header(k)
    raw=result._cfile.read_element_data(pointers[positions],ELEMENT_INDEX_TABLE_KEYS.index(field),offset)
    assert all(row is not None and len(row)==150 for row in raw)
    values=np.asarray(raw,dtype=float).reshape(4,2,25,3)
    assert np.isfinite(values).all()
    return values[:,:,:,0]


def scan(coordinates,mean,shapes):
    """Every screw, end and section node at every integration station, in bounded memory."""
    peaks=np.full(4,-np.inf)
    records=[None]*4
    direct_peaks=np.full(4,-np.inf)
    for start in range(0,len(coordinates),4096):
        q=coordinates[start:start+4096]
        stress=(q@shapes.reshape(len(shapes),-1)).reshape(-1,4,2,25)+mean
        # Node zero is the section centre. This identity is verified before superposition.
        direct_peaks=np.maximum(direct_peaks,stress[:,:,:,0].max(axis=(0,2)))
        for i in range(4):
            field=stress[:,i];it,end,point=np.unravel_index(np.argmax(field),field.shape)
            peak=float(field[it,end,point])
            if peak>peaks[i]:
                centre=float(field[it,end,0])
                peaks[i]=peak
                records[i]=dict(screw=i+1,end='IJ'[end],section_index=int(point),sample=start+int(it),
                    time_s=(start+int(it))/FS,tensile_MPa=peak,direct_MPa_at_peak=centre,
                    bending_MPa_at_peak=peak-centre,static_MPa_at_peak=float(mean[i,end,point]))
    for row,maximum in zip(records,direct_peaks,strict=True):row['maximum_direct_tension_MPa']=float(maximum)
    return records


def run(variant,campaign,axes,*,check_psd=False,check_history=False):
    basis,folder,modal=source(variant+'_basis',campaign)
    preload,_,static=source(variant+'_static',campaign)
    install=read(ROOT/'validation/installation_material'/(preload['case']+'.json'))
    assert install['rst_sha256']==preload['rst_sha256'] and install['section_nodes_per_beam_end']==25
    elements,positions=screw_elements(modal)
    initial,static_positions=screw_elements(static)
    assert np.array_equal(initial,elements)
    mean=section(static,static.nsets-1,static_positions,'ENS')*1e-6
    assert np.allclose(mean.max(axis=(1,2)),install['history'][-1]['four_screws']['peak_fiber_tension_MPa'])
    installed = input_record(preload['case'])
    assert installed['input_sha256'] == install['input_sha256']
    E = {'nylon': 3000., 'aluminium': 69000.}[installed['material']]
    shapes=np.empty((modal.nsets,4,2,25))
    constitutive=0.
    for k in range(modal.nsets):
        shapes[k]=section(modal,k,positions,'ENS')*1e-6
        strain=section(modal,k,positions,'EEL')
        error=np.max(abs(shapes[k]-E*strain))/max(abs(shapes[k]).max(),1e-12)
        constitutive=max(constitutive,float(error))
    assert constitutive<.001 and np.allclose(mean.mean(axis=2),mean[:,:,0],atol=1e-3)
    asymmetry=np.max(abs(shapes.mean(axis=3)-shapes[:,:,:,0]))/np.max(abs(shapes))
    assert asymmetry<1e-5
    ledger=read(ROOT/'.runtime/receipts'/campaign/basis['case']/'archived.json')
    listing=folder/'solve.out'
    log_sha=verified(listing,next(r['sha256'] for r in ledger['files'] if r['name']=='solve.out'))
    frequencies=modal.time_values
    for axis in axes:
        load=ROOT/'.runtime/motion_loads'/(axis+'.txt')
        input_sha=read(ROOT/'validation/motion_inputs.json')['inputs'][axis]['sha256']
        verified(load,input_sha)
        spectrum,fk,sk,damping=spectrum_input(axis)
        gamma=participation(listing.read_text(errors='replace'),axis)
        cov,_=moments(frequencies,gamma,fk,sk,damping,.125)
        flat=shapes.reshape(modal.nsets,-1)
        rms=np.sqrt(np.einsum('ip,ip->p',flat,cov@flat)).reshape(4,2,25)
        assert np.isfinite(rms).all()
        key=variant+'_'+axis
        if check_psd:
            response,_,rst=source(variant+'_psd_'+axis+'_private1',campaign)
            ids,index=screw_elements(rst);assert np.array_equal(elements,ids)
            native=section(rst,rst.parse_step_substep([3,1]),index,'ENS')*1e-6
            assert native.min()>=0
            err=np.linalg.norm(native-rms)/np.linalg.norm(rms)
            assert err<.01,(axis,err)
            write_json(ROOT/'validation/screw_vibration'/(key+'_native_psd.json'),
                dict(case=response['case'],campaign=campaign,rst_sha256=response['rst_sha256'],
                     basis_sha256=basis['rst_sha256'],maximum_native_RMS_MPa=native.max(axis=(1,2)).tolist(),
                     maximum_independent_RMS_MPa=rms.max(axis=(1,2)).tolist(),section_field_relative_L2=float(err)))
            continue
        if check_history:
            native=read(ROOT/'validation/motion'/f'{variant}_motion_{axis}.json')
            assert native['basis_rst_sha256']==basis['rst_sha256'] and native['campaign']==campaign
            mcf=ROOT/'.runtime/archive'/campaign/native['case']/'file.mcf'
            verified(mcf,native['mcf_sha256'])
            q=native_series(mcf,frequencies)
            records=scan(q,mean,shapes)
            reference=read(ROOT/'validation/screw_vibration'/(key+'.json'))
            assert reference['native_basis_sha256']==basis['rst_sha256']
            shifts=[abs(r['tensile_MPa']/s['tensile_MPa']-1) for r,s in zip(records,reference['screws'],strict=True)]
            assert max(shifts)<.005,shifts
            write_json(ROOT/'validation/screw_vibration'/(key+'_native_history.json'),
                       dict(variant=variant,axis=axis,campaign=campaign,basis_sha256=basis['rst_sha256'],
                            mcf_sha256=native['mcf_sha256'],screws=records,
                            max_relative_difference_from_independent_peak=max(shifts)))
            continue
        times,acc,_=excitation(axis)
        sealed=np.loadtxt(load,skiprows=1)
        assert np.allclose(sealed[:,0],times,rtol=0,atol=5.1e-13) and np.allclose(sealed[:,1],acc,rtol=1e-10,atol=1e-9)
        t,q,_=integrate(frequencies,gamma,axis,slice(None))
        assert np.array_equal(t,times)
        records=scan(q,mean,shapes)
        high=max(records,key=lambda row:row['tensile_MPa'])
        i=high['screw']-1;end='IJ'.index(high['end']);point=high['section_index']
        stat=float(np.std(q[FS:-1]@shapes[:,i,end,point]))
        assert abs(stat/rms[i,end,point]-1)<.03
        write_json(ROOT/'validation/screw_vibration'/(key+'.json'),dict(case=variant,campaign=campaign,axis=axis,
            native_basis_sha256=basis['rst_sha256'],native_static_sha256=preload['rst_sha256'],listing_sha256=log_sha,
            input_sha256=input_sha,spectrum_input_sha256=digest(spectrum),sample_rate_Hz=FS,samples=len(t),duration_s=float(t[-1]),
            section_elements=elements.tolist(),section_nodes_per_end=25,Young_modulus_MPa=E,
            largest_modal_constitutive_relative_error=constitutive,relative_centre_to_mean_discrepancy=float(asymmetry),
            screws=records,maximum_spectrum_RMS_MPa=rms.max(axis=(1,2)).tolist(),
            governing_point_spectrum_RMS_MPa=float(rms[i,end,point]),governing_point_stationary_time_RMS_MPa=stat,
            scope='Signed independent modal integration about bolt lock with locked preload included. '
                  'Direct and bending components at the peak are simultaneous; tensile stress is longitudinal '
                  'at a modelled beam-section node. The circular beam represents an effective M4 shank. '
                  'The seeds and the fixed-contact tangent define these conditional stress histories.'))
        print(variant,axis,'peak screw',high,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=('snug125_nylon','snug125_aluminium','snug125_nylon_mesh15','snug125_aluminium_mesh15'))
    p.add_argument('--axes',default='XYZ',choices=('X','Y','Z','XYZ'))
    p.add_argument('--campaign',default='nov08_01')
    checks=p.add_mutually_exclusive_group()
    checks.add_argument('--check-psd',action='store_true');checks.add_argument('--check-history',action='store_true')
    a=p.parse_args()
    run(a.variant,a.campaign,a.axes,check_psd=a.check_psd,check_history=a.check_history)
