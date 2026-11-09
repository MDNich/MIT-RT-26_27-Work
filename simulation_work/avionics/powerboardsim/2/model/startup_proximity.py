"""Locate modeled cell-to-case encounters during the common 100 ms acceleration ramp."""
import argparse
import numpy as np

from audit_local import ROOT,read
from audit_motion import selected_native_coordinates
from case_stress import source
from film_cell_timestep import resolve_cells, refined_coordinates
from film_identity import digest,verified,write_json
from seeded_motion import FS, participation


def coordinate_window(variant,axis,campaign,modal,samples):
    motion_path=ROOT/'validation/motion'/f'{variant}_motion_{axis}.json'
    motion=read(motion_path)
    assert motion['axis']==axis and motion['branch']==variant and motion['campaign']==campaign
    assert motion['basis_rst_sha256']==modal['rst_sha256'] and motion['sampling_Hz']==FS
    mcf=ROOT/'.runtime/archive'/campaign/motion['case']/'file.mcf'
    verified(mcf,motion['mcf_sha256'])
    q=selected_native_coordinates(mcf,modal['frequencies_Hz'],samples)
    assert samples[0]==0 and np.all(q[0]==0)
    return q,motion_path,motion


def run(variant,campaign,method):
    modal,folder,rst=source(variant+'_basis',campaign)
    samples=np.arange(int(np.ceil(.1*FS))+1)
    surface_path=ROOT/'validation/film_cell_contact'/f'{variant}.json'
    controls=read(surface_path)
    assert controls['campaign']==campaign and controls['basis_sha256']==modal['rst_sha256']
    axes='XYZ' if method=='native' else 'X'
    for axis in axes:
        q,motion_path,motion=coordinate_window(variant,axis,campaign,modal,samples)
        keep=None
        checked={}
        if method=='independent_exact':
            inputs=ROOT/'.runtime/motion_loads'/(axis+'.txt')
            verified(inputs,motion['input_sha256'])
            forcing=np.loadtxt(inputs,skiprows=1,max_rows=len(samples))
            assert np.allclose(forcing[:,0],samples/FS,rtol=0,atol=5.1e-13)
            log=folder/'solve.out'
            spec=read(ROOT/'validation/independent_motion'/(motion['case']+'.json'))
            verified(log,spec['modal_listing_sha256'])
            gamma=participation(log.read_text(errors='replace'),axis)
            q,checked=refined_coordinates('linear_input_exact',forcing[:,1],samples,rst.time_values,gamma)
            checked['input_sha256']=motion['input_sha256']
        if method=='native_3500_Hz':
            keep=rst.time_values<=3500.
            q=q[:,keep]
            checked.update(modes=int(keep.sum()),highest_mode_Hz=float(rst.time_values[keep][-1]))
        cells,combined=resolve_cells(variant,campaign,rst,modal,q,samples,controls['quadratic_faces'],keep)

        assert combined[0]=='separated'
        result=dict(variant=variant,campaign=campaign,base_axis=axis,samples=len(samples),sampling_Hz=FS,
                    through_s=float(samples[-1]/FS),basis_rst_sha256=modal['rst_sha256'],
                    native_motion_sha256=digest(motion_path),mcf_sha256=motion['mcf_sha256'],
                    surface_control_sha256=digest(surface_path),cells=cells,
                    scope='Curved cell and casing surfaces in the tightened linear model. All native integration '
                          'stations from rest to the first sample at or after full input amplitude are included. '
                          'Intersections estimate closure of the open gap; subsequent contact forces require a contact solve.')
        if variant=='stand3_nylon' and axis=='X' and method=='native':
            replay_path=ROOT/'validation/contact_replay_parent.json'
            replay=read(replay_path)
            assert replay['native_mcf_sha256']==motion['mcf_sha256'] and 0<replay['samples']<len(q)
            for key,c in cells.items():
                for field in ('crossing_intervals_samples','unresolved_intervals_samples'):
                    truncated=[[s,min(e,replay['samples']-1)] for s,e in c[field] if s<replay['samples']]
                    assert truncated==replay['full_cells'][key][field]
            result['verified_prior_window_sha256']=digest(replay_path)
        if method!='native':
            result.update(coordinate_method=method,method_checks=checked)
        suffix='' if method=='native' else '_'+method
        write_json(ROOT/'validation/startup_ramp'/f'{variant}_{axis}_gap{suffix}.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=['stand3_nylon','stand3_aluminium'])
    parser.add_argument('--campaign',default='nov08_01')
    parser.add_argument('--method',choices=['native','independent_exact','native_3500_Hz'],default='native')
    args=parser.parse_args()
    run(args.variant,args.campaign,args.method)
