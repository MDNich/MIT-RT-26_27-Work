"""Compare fine-mesh PCB stress spectra with the nominal native PSDs on identical board columns."""
import argparse
import numpy as np

from audit_local import ROOT,read
from case_stress import source
from film_identity import digest,write_json
from independent_psd import moments,spectrum_input
from pcb_dynamic_stress import cache_modes
from pcb_stress_cutoff import signed_basis,combine
from seeded_motion import participation
from snug_pcb_footprint import area_quantile,board_columns
from stage_snug_fit import AUDIT


def run(material,campaign):
    base='snug125_'+material
    branch=base+'_mesh15'
    convergence=read(AUDIT/(material+'_modal_mesh_comparison.json'))
    model=convergence['models'][-1];assert model['case']==branch+'_basis'
    proof,folder,r=source(model['case'],campaign)
    assert proof['rst_sha256']==model['basis_rst_sha256']
    cache=ROOT/'.runtime/post'/campaign/(branch+'_films')/'pcb_stress'
    assert cache_modes(folder/'file.rst',cache)['rst_sha256']==proof['rst_sha256']
    tensor,es,counts,nodes,freq,listing,manifest=signed_basis(branch,campaign)
    geom,columns,_,pose=board_columns(campaign)
    layers=np.array([[r[0],r[1]] for r in columns]);area=np.array([r[2] for r in columns])
    ix=np.searchsorted(es,layers);assert np.array_equal(es[ix],layers)
    element_per_corner=np.repeat(es,counts)
    starts=np.r_[0,np.cumsum(counts)[:-1]]
    comparisons={}
    for axis in 'XYZ':
        name=base+'_psd_'+axis+'_private1'
        nominal,_,rst=source(name,campaign)
        known=read(AUDIT/('pcb_footprint_'+axis+'.json'))
        assert known['models'][base]['rst_sha256']==nominal['rst_sha256'] and known['area_reference']==geom
        enum,raw,idx=rst.element_solution_data([3,1],'ENS')
        positions=np.searchsorted(enum,es);assert np.array_equal(enum[positions],es)
        assert np.array_equal(np.concatenate([idx[j] for j in positions]),nodes)
        coarse=np.concatenate([raw[j].reshape(-1,11)[:,10] for j in positions]).astype('float64')*1e-6
        c_field=np.maximum.reduceat(coarse,starts)[ix].max(1)
        c95=area_quantile(c_field,area,.95)
        assert np.isclose(c95,known['models'][base]['area_95th_percentile_MPa'],rtol=1e-10)
        path,knots,psd,zeta=spectrum_input(axis);gamma=participation(listing,axis)
        c,_=moments(freq,gamma,knots,psd,zeta,.125)
        finer,_=moments(freq,gamma,knots,psd,zeta,.0625)
        quad_delta=np.linalg.norm(finer-c)/np.linalg.norm(finer)
        assert quad_delta<1e-5
        data={}
        for limit in (3500,4000):
            n=int(np.count_nonzero(freq<=limit));assert n>0
            stress,_=combine(tensor,c[:n,:n],False);stress*=1e-6
            peak=int(stress.argmax())
            assert (n==len(freq))==(limit==4000)
            col=np.maximum.reduceat(stress,starts)[ix].max(1)
            node=int(nodes[peak]);pos=np.searchsorted(pose[0],node);assert node==pose[0][pos]
            data[limit]=dict(modes=n,peak_MPa=float(stress[peak]),element=int(element_per_corner[peak]),node=node,
                original_xyz_mm=(pose[1][pos]*1000).tolist(),area_95th_percentile_MPa=area_quantile(col,area,.95))
        fine=data[4000]
        signed_nominal=read(ROOT/'validation/pcb_stress_cutoff'/(name+'.json'))
        assert signed_nominal['rst_sha256']==nominal['rst_sha256']
        comparisons[axis]=dict(nominal_case=name,nominal_native_rst_sha256=nominal['rst_sha256'],
            nominal_peak_MPa=float(coarse.max()),nominal_area_95th_percentile_MPa=c95,
            fine_cutoffs_Hz=data,peak_change_percent=float(100*(fine['peak_MPa']/coarse.max()-1)),
            area_95th_percentile_change_percent=float(100*(fine['area_95th_percentile_MPa']/c95-1)),
            fine_covariance_quadrature_relative_change=float(quad_delta),spectrum_input_sha256=digest(path))
    write_json(AUDIT/(material+'_mesh_pcb_spectra.json'),dict(branch=branch,campaign=campaign,
        fine_basis_rst_sha256=proof['rst_sha256'],modal_tensor_manifest_sha256=digest(manifest),
        original_geometry=geom,matched_corners=len(nodes),matched_board_columns=len(area),axes=comparisons,
        scope='Nominal PCB stresses are read from native MAPDL spectra. Fine stresses are independent combinations '
              'of all signed native eigenvector tensors using each base spectrum and two percent damping. '
              'Each mesh uses its own installed tangent. The 95th percentile weights columns by their original PCB area.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--material',choices=('nylon','aluminium'),default='nylon')
    p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args()
    run(args.material,args.campaign)
