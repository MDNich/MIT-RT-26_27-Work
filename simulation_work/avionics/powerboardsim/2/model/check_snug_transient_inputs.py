"""Read the serialized startup tables independently of the intact-shell input generator."""
import argparse

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FS
from snug_shell_drive_sampling import native_startup
from stage_snug_fit import AUDIT, INPUTS, STEP_HASH


def check(registry):
    specs = read(registry)
    assert len(specs)==2
    first, second = specs.values()
    assert not first['contact'] and second['contact'] and first['variant']==second['variant']
    wave_inputs = {name:sha for name,sha in first['files'].items() if name!='model.inp'}
    assert wave_inputs == {name:sha for name,sha in second['files'].items() if name!='model.inp'}
    for spec in specs.values():
        folder = INPUTS/spec['case']
        for name,sha in spec['files'].items():
            verified(folder/name,sha)
        static = INPUTS/spec['static_fixture']/'model.inp'
        verified(static,spec['static_fixture_sha256'])
        text = (folder/'model.inp').read_text()
        assert text.split('*dim,pbt,array,')[0] == static.read_text().split('*dim,pbt,array,')[0]
        assert text.count('\nsolve\n')==len(spec['preload_times'])+2
        assert text.count('timint,on')==1 and 'acel,0,0,%baseacc%' in text
        assert 'timint,off' in text and 'outres,rsol,%pbrf%' in text and 'outres,nsol,%pbfull%' in text
        assert ('nlhist,pair,pbfz,cont,CFNZ,853' in text)==spec['contact']
        assert 'copy,pbat(1)' in text and 'copy,pbt(1)' in text
    s=first
    folder=INPUTS/s['case']
    variant,campaign=s['variant'],s['campaign']
    parent=read(AUDIT/(variant+'_shell_inputs_v2.json'))[s['static_fixture']]
    assert s['static_fixture_sha256']==parent['files']['model.inp'] and s['step_sha256']==parent['step_sha256']==STEP_HASH
    proof,_,rst=source(parent['basis_case'],campaign)
    assert proof['rst_sha256']==s['basis_rst_sha256'] and parent['drive_field_sha256']==s['drive_field_sha256']
    cache=ROOT/'.runtime/shell_fixture'/campaign/variant/'parent_fields.npz'
    verified(cache,s['drive_field_sha256'])
    def array(name):
        return np.loadtxt(folder/(name+'.dat'))
    with np.load(cache) as saved:
        ports=array('pbn').astype(int)
        assert np.array_equal(ports,saved['driven'])
        ix=np.searchsorted(saved['nodes'],ports)
        saved_times=np.array(s['preload_times'])
        assert np.array_equal(saved_times,saved['t'][1:len(saved_times)+1])
        pre=saved['u'][1:len(saved_times)+1,ix]
    start=s['startup_time'];last=s['final_sample'];stride=s['stride']
    stations=np.arange(0,last+1,stride);source_clock=np.arange(last+1)/FS
    times=array('pbt')
    assert np.array_equal(times,np.r_[0.,saved_times,start+stations/FS])
    a_path=ROOT/'.runtime/motion_loads/Z.txt'
    verified(a_path,s['acceleration_sha256'])
    acc=np.loadtxt(a_path,skiprows=1,max_rows=last+1)
    assert np.array_equal(array('pba'),np.r_[0.,acc[:,1]])
    assert np.array_equal(array('pbat'),np.r_[0.,start+source_clock])
    assert np.array_equal(array('pbfull'),start+np.asarray(s['full_output_samples'])/FS)
    assert np.array_equal(array('pbrf'),start+np.arange(4,last+1,4)/FS)
    motion=read(ROOT/'validation/independent_motion'/(variant+'_motion_Z.json'))
    q,proof=native_startup(motion,campaign,rst.time_values,stations)
    assert proof['native_mcf_sha256']==s['native_mcf_sha256']
    forces=array('pbq').reshape(len(times),-1,order='F')
    nlock=len(saved_times)
    assert np.array_equal(forces[:nlock+1,:nlock],np.vstack([np.zeros(nlock),np.eye(nlock)]))
    assert not np.any(forces[:nlock+1,nlock:]) and np.array_equal(forces[nlock+1:,nlock:],q)
    assert np.all(forces[nlock+1:,nlock-1]==1) and not np.any(forces[nlock+1:,:nlock-1])
    fields=field_files(parent['basis_case'],campaign,s['basis_rst_sha256'],rst.nsets)
    shapes=displacement_basis(rst,ports,fields)
    worst=0.
    for j,axis in enumerate('xyz'):
        disk=array('shape'+axis).reshape(forces.shape[1],len(ports),order='F')
        assert np.array_equal(disk[:nlock],pre[:,:,j]) and np.array_equal(disk[nlock:],shapes[:,:,j])
        for offset in range(0,len(ports),512):
            group=slice(offset,offset+512)
            physical=pre[-1,group,j]+q@shapes[:,group,j]
            actual=forces[nlock+1:]@disk[:,group]
            worst=max(worst,float(abs(physical-actual).max()))
    assert worst<1e-12
    evidence=dict(registry_sha256=digest(registry),checked_cases=list(specs),native_mcf_sha256=s['native_mcf_sha256'],
                  nodes=len(ports),directions=3,static_load_states=nlock,table_times=len(times),
                  transient_displacement_knots=len(stations),transient_acceleration_knots=len(source_clock),
                  maximum_boundary_reconstruction_error_m=worst,
                  scope='Input readback only. Both decks preserve their matching static geometry prefix. Full native '
                        'input and result checks are required for a physical interpretation of the transient response.')
    write_json(registry.with_name(registry.stem+'_preflight.json'),evidence)
    print(variant,len(ports),len(stations),worst)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry',type=lambda name:AUDIT/name)
    check(parser.parse_args().registry)
