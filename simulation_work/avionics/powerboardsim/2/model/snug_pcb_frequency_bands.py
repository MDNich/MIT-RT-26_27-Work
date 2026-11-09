"""Resolve native PCB stress maxima by excitation frequency using the signed modal stress tensors."""
import argparse

import numpy as np

from audit_local import ROOT,read
from film_identity import digest,write_json
from independent_psd import moments,spectrum_input
from pcb_stress_cutoff import signed_basis
from seeded_motion import participation
from snug_pcb_footprint import BRANCHES
from stage_snug_fit import AUDIT
from study_cases import native_case


BANDS=(20,200,350,500,800,1200,2000)


def equivalent_mean_square(stress,cov):
    # Covariance of the six tensor components at one exact element corner, in square MPa.
    c=stress.T@cov@stress
    normal=np.trace(c[:3,:3])-c[0,1]-c[1,2]-c[2,0]
    return float(normal+3*np.trace(c[3:,3:]))


def run(branch,campaign,axes):
    shape,elem,counts,nodes,freq,listing,manifest=signed_basis(branch,campaign)
    element_per_corner=np.repeat(elem,counts)
    for axis in axes:
        key=native_case(branch,'psd_'+axis)
        native=read(ROOT/'validation/global'/(key+'.json'))
        cutoff=read(ROOT/'validation/pcb_stress_cutoff'/(key+'.json'))
        assert native['campaign']==cutoff['campaign']==campaign and cutoff['case']==key
        assert cutoff['rst_sha256']==native['rst_sha256'] and cutoff['signed_modes_sha256']==digest(manifest)
        scopes=native['native_psd_fields']['scopes']['pcb']
        location=(element_per_corner==scopes['stress_element'])&(nodes==scopes['stress_node'])
        idx,=np.flatnonzero(location)
        stress=np.array(shape[:,idx,:],dtype=float)*1e-6
        path,fk,sk,zeta=spectrum_input(axis)
        assert cutoff['spectrum_sha256']==digest(path)
        gamma=participation(listing,axis)
        cov,power=moments(freq,gamma,fk,sk,zeta,.125)
        reference=equivalent_mean_square(stress,cov)
        native_peak=scopes['equivalent_stress_rms_Pa']*1.e-6
        assert abs(np.sqrt(reference)/native_peak-1)<.001
        band_results=[]
        for lo,hi in zip(BANDS[:-1],BANDS[1:],strict=True):
            knots=np.r_[lo,fk[(fk>lo)&(fk<hi)],hi]
            density=np.exp(np.interp(np.log(knots),np.log(fk),np.log(sk)))
            cov1,base_power=moments(freq,gamma,knots,density,zeta,.125)
            cov2,_=moments(freq,gamma,knots,density,zeta,.0625)
            value=equivalent_mean_square(stress,cov1)
            refined=equivalent_mean_square(stress,cov2)
            assert 0<value and abs(value/refined-1)<5e-4
            band_results.append(dict(low_Hz=lo,high_Hz=hi,base_acceleration_variance_fraction=base_power/power,
                                     equivalent_stress_mean_square_MPa2=value,stress_variance_fraction=value/reference,
                                     quadrature_halving_relative_change=abs(value/refined-1)))
        assert np.isclose(sum(r['stress_variance_fraction'] for r in band_results),1.,rtol=1e-9,atol=0)
        assert np.isclose(sum(r['base_acceleration_variance_fraction'] for r in band_results),1.,rtol=1e-9,atol=0)
        write_json(AUDIT/(branch+'_pcb_bands_'+axis+'.json'),dict(case=key,campaign=campaign,
            base_axis=axis,native_peak_MPa=native_peak,element=int(element_per_corner[idx]),node=int(nodes[idx]),
            integrated_peak_MPa=float(np.sqrt(reference)),native_spectrum_rst_sha256=native['rst_sha256'],
            signed_basis_manifest_sha256=digest(manifest),spectrum_input_sha256=digest(path),bands=band_results,
            scope='Shares of the mean square of the equivalent stress at this assembly’s peak PCB corner. '
                  'Each band retains all native modes and their cross-correlations. The input bands are disjoint.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('branch',choices=BRANCHES)
    parser.add_argument('--axes',default='XYZ')
    parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args()
    assert args.axes and all(k in 'XYZ' for k in args.axes)
    run(args.branch,args.campaign,args.axes)
