"""Integrate the absolute acceleration over each battery cell to obtain its net dynamic force."""
import argparse
import re

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.signal import lfilter

from audit_local import ROOT,read
from basis_comparison import field_files
from film_identity import verified,digest,write_json
from independent_psd import spectrum_input
from motion_surface import displacement_basis
from native_rst import read_rst
from seeded_motion import FS,excitation,participation
from study_cases import native_case


def tetra_mass_weights(xyz,order):
    """Integrate ten-node tetrahedral interpolation functions on each material element."""
    grid,w=leggauss(order);grid=(grid+1)*.5;w*=.5
    grad=np.vstack([-np.ones(3),np.eye(3)])
    edges=[(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)]
    coeff=np.zeros(xyz.shape[:2])
    for i,a in enumerate(grid):
        for j,b in enumerate(grid):
            for k,c in enumerate(grid):
                l=np.array([(1-a)*(1-b)*(1-c),a,(1-a)*b,(1-a)*(1-b)*c])
                shape=np.r_[l*(2*l-1),[4*l[n]*l[m] for n,m in edges]]
                deriv=np.vstack([(4*l[:,None]-1)*grad,[4*(l[n]*grad[m]+l[m]*grad[n]) for n,m in edges]])
                jac=np.einsum('eni,nj->eij',xyz-xyz[:,:1],deriv)
                det=np.linalg.det(jac)
                assert np.all(det>0) and np.isclose(shape.sum(),1) and np.allclose(deriv.sum(0),0)
                coeff+=det[:,None]*shape*(w[i]*w[j]*w[k]*(1-a)**2*(1-b))
    return coeff


def acceleration_covariance(freq,gamma,knots,psd,damping,spacing):
    omega=2*np.pi*freq
    matrix=np.zeros((len(freq)+1,len(freq)+1))
    for lo,hi,sl,sh in zip(knots[:-1],knots[1:],psd[:-1],psd[1:],strict=True):
        axis=np.linspace(lo,hi,int(np.ceil((hi-lo)/spacing))+1)
        w=2*np.pi*axis[:,None]
        weights=(axis[1]-axis[0])*sl*(axis/lo)**(np.log(sh/sl)/np.log(hi/lo))
        weights[[0,-1]]*=.5
        acc=gamma*w**2/(omega**2-w**2+2j*damping*omega*w)
        transfer=np.column_stack((acc,np.ones(len(w))))*np.sqrt(weights[:,None])
        matrix+=(transfer.conj().T@transfer).real
    return .5*(matrix+matrix.T)


def rms(vectors,cov,axis):
    # The same base acceleration drives every mode. Add its direct contribution
    # before combining the modal cross terms and evaluating each physical component.
    direct=np.broadcast_to(np.eye(3)['XYZ'.index(axis)],vectors.shape[:-1])
    augmented=np.concatenate([vectors,direct[...,None]],axis=-1)
    return np.sqrt(np.maximum(0,np.einsum('...i,ij,...j->...',augmented,cov,augmented,optimize=True)))


def seed_check(freq,gamma,mean,axis,damping):
    _,base,_=excitation(axis)
    out=base[:,None,None]*np.tile(np.eye(3)['XYZ'.index(axis)],(len(mean),1))[None,:,:]
    scale=2*FS
    for j,(f,g) in enumerate(zip(freq,gamma,strict=True)):
        omega=2*np.pi*f
        qdd=lfilter(-g*scale**2*np.array([1.,-2.,1.]),
                    [scale**2+2*damping*omega*scale+omega**2,2*(omega**2-scale**2),
                     scale**2-2*damping*omega*scale+omega**2],base)
        out+=qdd[:,None,None]*mean[None,:,:,j]
    steady=out[FS:-1]
    seed=np.sqrt(np.mean(steady**2,axis=0))
    # Check the discrete time integration by Parseval on the exact periodic input.
    n=len(steady)
    bins=np.fft.rfftfreq(n,1/FS)
    band=(bins>=20)&(bins<=2000)
    f=bins[band]
    weights=2*np.abs(np.fft.rfft(base[FS:-1])[band]/n)**2
    omega=2*np.pi*freq
    def evaluate(physical):
        w=physical[:,None]
        transfer=gamma*w**2/(omega**2-w**2+2j*damping*omega*w)
        response=(transfer@mean.reshape(-1,len(freq)).T).reshape(len(w),len(mean),3)+np.eye(3)['XYZ'.index(axis)]
        return np.sqrt(np.einsum('f,fij->ij',weights,np.abs(response)**2))
    analog=evaluate(2*np.pi*f)
    numerical=[evaluate(2*rate*np.tan(np.pi*f/rate)) for rate in (FS,2*FS,4*FS)]
    return seed,analog,numerical


def volume_control():
    vertex=np.array([[0.,0.,0.],[2.,0.,0.],[0.,3.,0.],[0.,0.,4.]])
    mids=[.5*(vertex[a]+vertex[b]) for a,b in [(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)]]
    nodes=np.vstack([vertex,mids])
    weights=tetra_mass_weights(nodes[None],4)[0]
    assert abs(weights.sum()-4.)<1e-12 and np.allclose(weights@nodes/4.,vertex.mean(0),atol=1e-13)
    for component in range(3):
        u=1+nodes@np.eye(3)[component]
        assert abs(weights@u/4.-(1+vertex.mean(0)[component]))<1e-12


def run(branch,campaign):
    volume_control()
    basis=branch+'_basis'
    p=read(ROOT/'validation/global'/(basis+'.json'))
    static=native_case(branch,'static')
    q=read(ROOT/'validation/global'/(static+'.json'))
    assert p['campaign']==q['campaign']==campaign
    archive=ROOT/'.runtime/archive'/campaign
    verified(archive/basis/'file.rst',p['rst_sha256'])
    verified(archive/static/'file.rst',q['rst_sha256'])
    ledger=read(ROOT/'.runtime/receipts'/campaign/basis/'archived.json')
    log=archive/basis/'solve.out'
    listing_sha=verified(log,next(x['sha256'] for x in ledger['files'] if x['name']=='solve.out'))
    deck=archive/static/'model.inp'
    src=read(ROOT/'.runtime/receipts'/campaign/static/'archived.json')
    input_sha=verified(deck,next(x['sha256'] for x in src['files'] if x['name']=='model.inp'))
    text=deck.read_text()
    rst=read_rst(archive/basis/'file.rst'); virgin=read_rst(archive/static/'file.rst')
    g=rst.grid.cell_data
    geom=virgin.mesh.elem; modal=rst.mesh.elem
    order=np.argsort(virgin.mesh.enum);morder=np.argsort(rst.mesh.enum)
    groups=[]; info={}
    for material in [176,187,191]:
        elements=np.sort(g['ansys_elem_num'][(g['ansys_elem_type_num']==187)&(g['ansys_material_type']==material)])
        ix=order[np.searchsorted(virgin.mesh.enum[order],elements)]
        im=morder[np.searchsorted(rst.mesh.enum[morder],elements)]
        assert np.array_equal(virgin.mesh.enum[ix],elements) and np.array_equal(rst.mesh.enum[im],elements)
        nodes=np.stack([geom[i][10:] for i in ix])
        assert nodes.shape==(len(elements),10) and np.array_equal(nodes,np.stack([modal[i][10:] for i in im]))
        ids,inv=np.unique(nodes,return_inverse=True)
        idx=np.searchsorted(virgin.mesh.nnum,ids);assert np.array_equal(virgin.mesh.nnum[idx],ids)
        coords=virgin.mesh.nodes[idx]
        nodal=[]
        for degree in (4,5):
            weights=tetra_mass_weights(coords[inv.reshape(nodes.shape)],degree)
            nodal.append(np.bincount(inv.ravel(),weights=weights.ravel(),minlength=len(ids)))
        err=float(np.linalg.norm(nodal[0]-nodal[1])/np.linalg.norm(nodal[1]))
        assert err<1e-9
        volume=nodal[1].sum()
        weights=nodal[1]/volume
        density=float(re.search(r'(?im)^mp,dens,'+str(material)+r',([^,\r\n]+)',text)[1])
        assert density==2200
        info[material]=dict(mass_kg=float(density*volume),volume_m3=float(volume),density_kg_m3=density,
              centroid_mm=(1000*(weights@coords)).tolist(),quadrature_relative_difference=err,elements=len(elements))
        groups.append((ids,weights))
    ids=np.unique(np.concatenate([v[0] for v in groups]))
    stems=None if branch=='bare' else field_files(basis,campaign,p['rst_sha256'],rst.nsets)
    phi=np.moveaxis(displacement_basis(rst,ids,stems),0,-1)
    means=np.stack([np.einsum('n,nij->ij',w,phi[np.searchsorted(ids,n)]) for n,w in groups])
    cache=ROOT/'.runtime/post'/campaign/basis/'cell_mass_mean.npz'
    cache.parent.mkdir(parents=True,exist_ok=True)
    if not cache.exists():
        temp=cache.with_suffix('.new.npz')
        np.savez_compressed(temp,mean=means,frequencies_Hz=rst.time_values,materials=list(info));temp.replace(cache)
    with np.load(cache) as previous:
        assert np.array_equal(previous['materials'],list(info)) and np.array_equal(previous['frequencies_Hz'],rst.time_values)
        assert np.allclose(previous['mean'],means,rtol=1e-12,atol=1e-13)
    weights_file=cache.with_name('cell_mass_weights.npz')
    weights=np.zeros((len(groups),len(ids)))
    for j,(numbers,v) in enumerate(groups):weights[j,np.searchsorted(ids,numbers)]=v
    if not weights_file.exists():
        temp=weights_file.with_suffix('.new.npz')
        np.savez_compressed(temp,nodes=ids,weights=weights,materials=list(info));temp.replace(weights_file)
    with np.load(weights_file) as saved:
        assert np.array_equal(saved['nodes'],ids) and np.array_equal(saved['weights'],weights)
    outcomes={}
    for axis in 'XYZ':
        spectrum,knots,psd,damping=spectrum_input(axis)
        gam=participation(log.read_text(errors='replace'),axis)
        cov=acceleration_covariance(rst.time_values,gam,knots,psd,damping,.125)
        coarse=acceleration_covariance(rst.time_values,gam,knots,psd,damping,.25)
        calc=rms(means,cov,axis)
        grid_err=float(np.max(abs(rms(means,coarse,axis)/calc-1)))
        check,analog,numerical=seed_check(rst.time_values,gam,means,axis,damping)
        digital=numerical[0]
        refinement=[float(np.max(abs(v/analog-1))) for v in numerical]
        assert refinement[2]<.1*refinement[0] and refinement[2]<refinement[1]<refinement[0],refinement
        discrepancy=float(np.max(abs(check/calc-1)))
        parseval=float(np.max(abs(check/digital-1)))
        bin_error=float(np.max(abs(analog/calc-1)))
        print('frequency checks',branch,axis,grid_err,parseval,bin_error,discrepancy,flush=True)
        assert grid_err<1e-5 and parseval<1e-5,(grid_err,parseval)
        assert bin_error<.015,(bin_error,analog,calc)
        axis_num='XYZ'.index(axis)
        cutoff={}
        for bound in (2000,3000,3500,4000):
            count=int(np.searchsorted(rst.time_values,bound,side='right'))
            keep=np.r_[np.arange(count),len(rst.time_values)]
            small=rms(means[:,:,:count],cov[np.ix_(keep,keep)],axis)
            cutoff[bound]=dict(modes=count,driven_axis_change_percent=(100*(small[:,axis_num]/calc[:,axis_num]-1)).tolist())
        cases={}
        for i,m in enumerate(info):
            cases[m]=dict(mean_acceleration_XYZ_rms_g=(calc[i]/9.806).tolist(),
                          net_dynamic_force_XYZ_rms_N=(calc[i]*info[m]['mass_kg']).tolist(),
                          seed_mean_acceleration_XYZ_rms_g=(check[i]/9.806).tolist())
        native_case_id=native_case(branch,'psd_'+axis)
        auth=ROOT/'validation/global'/(native_case_id+'.json')
        native_check=None
        if auth.is_file():
            nat=read(auth);path=archive/native_case_id/'file.rst';verified(path,nat['rst_sha256'])
            result=read_rst(path);nodes,values=result.nodal_solution([5,1]);order=np.argsort(nodes)
            pos=order[np.searchsorted(nodes[order],ids)];assert np.array_equal(nodes[pos],ids)
            actual=np.abs(values[pos,:3]);reconstruction=rms(phi,cov,axis)
            rel=np.linalg.norm(reconstruction-actual,axis=0)/np.linalg.norm(actual,axis=0)
            native_check=dict(native_case=native_case_id,native_rst_sha256=nat['rst_sha256'],matched_nodes=len(ids),
                              relative_L2_XYZ=rel.tolist())
            assert np.max(rel)<.02,rel
            print('native check',branch,axis,rel,flush=True)
        outcomes[axis]=dict(cell_order=list(info),modal_cutoff_Hz=cutoff,
                        nominal_half_quarter_step_max_relative_error_vs_analog_bins=refinement,
                        largest_driven_axis_seed_vs_continuous_PSD_difference=float(np.max(abs(check[:,axis_num]/calc[:,axis_num]-1))),
                        spectrum_sha256=digest(spectrum),quadrature_max_relative_change=grid_err,
                        largest_seeded_relative_difference=discrepancy,seeded_vs_discrete_Parseval_relative_error=parseval,
                        analog_Fourier_bins_vs_continuous_PSD_relative_difference=bin_error,cells=cases,native_nodal_check=native_check)
    print(branch,{a:[round(v['net_dynamic_force_XYZ_rms_N']['XYZ'.index(a)],2) for v in d['cells'].values()] for a,d in outcomes.items()},flush=True)
    dest=ROOT/'validation/cell_force'/(branch+'.json')
    write_json(dest,dict(branch=branch,campaign=campaign,basis_rst_sha256=p['rst_sha256'],static_rst_sha256=q['rst_sha256'],
        mean_shapes_sha256=digest(cache),mass_weights_sha256=digest(weights_file),modal_listing_sha256=listing_sha,static_deck_sha256=input_sha,geometry=info,base_cases=outcomes,
        scope='Independent cross-spectral integration of absolute accelerations on the tightened native modes. '
              'Quadratic material-volume integration gives each cell’s centre-of-mass acceleration and net dynamic '
              'force. The summed force on a cell includes all its attachments; no allocation to an individual weld is inferred.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('branch');p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();run(a.branch,a.campaign)
