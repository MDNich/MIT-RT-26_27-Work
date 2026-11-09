"""Check the time sampling of the prescribed base-Z inputs across all intact-shell drive nodes."""
import argparse

import numpy as np

from audit_local import ROOT, read
from audit_motion import selected_native_coordinates
from basis_comparison import field_files
from case_stress import source
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FS, excitation, integrate, participation
from snug_shell_equilibrium import solid_parts
from stage_snug_fit import AUDIT


def interpolation_error(values, stride):
    """Piecewise-linear table error at the original, uniformly spaced solver stations."""
    samples = np.arange(len(values))
    assert samples[-1]%stride==0
    left = samples//stride*stride
    right = np.minimum(left+stride,samples[-1])
    weight = ((samples-left)/stride)[:,None]
    result = (values[left]-values)+(values[right]-values[left])*weight
    assert not np.any(result[::stride])
    return result


def scan(nodes, shapes, samples, delta, total_samples):
    best = -1.
    sum_squared = 0.
    for start in range(0,len(nodes),192):
        modes = np.ascontiguousarray(shapes[:,start:start+192]).reshape(len(shapes),-1)
        error = (delta@modes).reshape(len(delta),-1,3)
        sq = np.einsum('tnc,tnc->tn',error,error)
        sum_squared += sq.sum(dtype=np.float64)
        i,j = np.unravel_index(sq.argmax(),sq.shape)
        if sq[i,j]>best:
            best=sq[i,j]
            peak=dict(node=int(nodes[start+j]),sample=int(samples[i]),time_s=float(samples[i]/FS),
                      error_xyz_um=(1e6*error[i,j]).tolist())
    return dict(nodes=len(nodes),peak_vector_error_um=float(1e6*np.sqrt(best)),**peak,
                rms_vector_error_um=float(1e6*np.sqrt(sum_squared/(total_samples*len(nodes)))))


def native_startup(motion,campaign,frequencies,samples):
    path=ROOT/'validation/motion'/(motion['case']+'.json')
    audit=read(path)
    assert audit['campaign']==campaign==motion['campaign'] and audit['case']==motion['case']
    assert audit['basis_rst_sha256']==motion['basis_rst_sha256'] and audit['input_sha256']==motion['input_sha256']
    archive=ROOT/'.runtime/archive'/campaign/audit['case']/'file.mcf'
    verified(archive,audit['mcf_sha256'])
    coordinates=selected_native_coordinates(archive,frequencies,samples)
    assert np.linalg.norm(coordinates[0])<1e-13 and samples[0]==0
    return coordinates,dict(native_mcf_sha256=audit['mcf_sha256'],native_history_audit_sha256=digest(path))


def check(variant, campaign, *, native=False):
    registry = AUDIT/(variant+'_shell_inputs_v2.json')
    spec = read(registry)['shell_'+variant+'_contact_v2']
    preflight=read(AUDIT/(variant+'_shell_preflight_v2.json'))
    assert spec['campaign']==campaign and preflight['registry_sha256']==digest(registry)
    locator=AUDIT/(variant+'_replay_window.json')
    verified(locator,spec['replay_window_sha256'])
    last=read(locator)['replay_last_sample']
    proof,folder,rst=source(spec['basis_case'],campaign)
    assert proof['rst_sha256']==spec['basis_rst_sha256']
    cache=ROOT/'.runtime/shell_fixture'/campaign/variant/'parent_fields.npz'
    verified(cache,spec['drive_field_sha256'])
    with np.load(cache) as saved:
        nodes,bearings=saved['driven'],saved['bearing']
        positions=np.searchsorted(saved['nodes'],nodes)
        assert np.array_equal(saved['nodes'][positions],nodes)
        saved_u=saved['u']
        original=(saved_u[-4:-2,positions,:]-saved_u[-1,positions,:])
    motion=ROOT/'validation/independent_motion'/(variant+'_motion_Z.json')
    m=read(motion)
    assert m['basis_rst_sha256']==proof['rst_sha256']
    listing=folder/'solve.out';verified(listing,m['modal_listing_sha256'])
    samples=np.arange(last+1)
    times,q,_=integrate(rst.time_values,participation(listing.read_text(errors='replace'),'Z'),'Z',samples)
    t,a,_=excitation('Z')
    assert np.array_equal(times,t[:last+1]) and not np.any(q[0])
    fields=field_files(spec['basis_case'],campaign,proof['rst_sha256'],rst.nsets)
    shapes=displacement_basis(rst,nodes,fields)
    projected=(q[spec['base_Z_samples'][:2]]@shapes.reshape(rst.nsets,-1)).reshape(original.shape)
    seal_error=float(abs(projected-original).max())
    assert seal_error<1e-13
    parts=solid_parts(rst)
    group_nodes={str(spec['body_ids'][str(m)]):part[3] for m,part in parts.items() if m!=850}
    group_nodes['PLA bearing nodes']=bearings
    assert np.array_equal(np.sort(np.concatenate(list(group_nodes.values()))),nodes)
    records=[]
    reference=q
    extra={}
    if native:
        reference,extra=native_startup(m,campaign,rst.time_values,samples)
    for stride in ((4,2,1) if native else (4,2)):
        coords=interpolation_error(q,stride)
        if native:
            coords+=q-reference
        kept=samples if native else samples[samples%stride!=0]
        errors={}
        for name,ids in group_nodes.items():
            j=np.searchsorted(nodes,ids)
            errors[name]=scan(ids,shapes[:,j],kept,coords[kept],len(samples))
        base=interpolation_error(a[:last+1,None],stride)[:,0]
        peak=int(np.argmax(abs(base)))
        worst=max(errors,key=lambda k:errors[k]['peak_vector_error_um'])
        # Check the reported extreme using an independent scalar interpolation of the physical field.
        record=errors[worst]; node=record['node']; sample=record['sample']
        field=shapes[:,np.searchsorted(nodes,node),:]
        exact=q@field
        at_sample=reference[sample]@field
        knot=samples[::stride]
        residual=[np.interp(sample,knot,column[knot])-value for column,value in zip(exact.T,at_sample,strict=True)]
        assert np.allclose(record['error_xyz_um'],1e6*np.array(residual),atol=1e-8,rtol=1e-8)
        records.append(dict(source_stride=stride,table_interval_us=1e6*stride/FS,knots=len(knot),
                            max_acceleration_error_g=float(abs(base[peak])/9.806),acceleration_peak_sample=peak,
                            rms_acceleration_error_g=float(np.sqrt(np.mean(base**2))/9.806),
                            maximum_group=worst,groups=errors))
    suffix='_shell_drive_native.json' if native else '_shell_drive_sampling.json'
    if native:
        extra['reference']='Archived MAPDL base-Z MCF evaluated at all original stations, including table knots.'
    write_json(AUDIT/(variant+suffix),dict(variant=variant,campaign=campaign,**extra,
        registry_sha256=digest(registry),basis_rst_sha256=proof['rst_sha256'],drive_field_sha256=spec['drive_field_sha256'],
        signed_motion_audit_sha256=digest(motion),modal_listing_sha256=m['modal_listing_sha256'],
        nodes=len(nodes),modes=rst.nsets,sample_rate_Hz=FS,samples=len(samples),end_time_s=last/FS,
        maximum_snapshot_reconstruction_error_m=seal_error,controls=records,
        scope='Linear interpolation of the independently integrated relative boundary motion and base acceleration. '
              'Signed components are compared at every original sample for all prescribed nodes. '
              'The resulting errors concern the drive tables. Nonlinear time integration and contact require separate checks.'))
    print(variant,[(r['source_stride'],r['groups'][r['maximum_group']]['peak_vector_error_um'],r['max_acceleration_error_g']) for r in records],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=['snug125_nylon','snug125_aluminium'])
    parser.add_argument('--campaign',default='nov08_01')
    parser.add_argument('--native',action='store_true',help='Compare the independently generated table to the accepted native base-Z motion')
    args=parser.parse_args()
    check(args.variant,args.campaign,native=args.native)
