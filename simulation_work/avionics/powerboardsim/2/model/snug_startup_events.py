"""Put the sampled outer-cell crossings, nickel screen and printed-material references on one native timeline."""
import argparse

from audit_local import ROOT,read
from film_identity import digest,write_json
from stage_snug_fit import AUDIT


def compare(axis):
    branches={}
    for material in ('nylon','aluminium'):
        branch='snug125_'+material
        motion_file=ROOT/'validation/motion'/f'{branch}_motion_{axis}.json'
        motion=read(motion_file)
        scan_file=AUDIT/f'{branch}_outer_onset_{axis}_native.json'
        witness_file=scan_file.with_name(scan_file.stem+'_witness.json')
        scan,witness=read(scan_file),read(witness_file)
        assert witness['source_sha256']==digest(scan_file) and scan['method']==witness['method']=='native'
        assert scan['variant']==witness['variant']==branch and scan['base_axis']==motion['axis']==axis
        assert scan['basis_rst_sha256']==motion['basis_rst_sha256'] and scan['input_sha256']==motion['input_sha256']
        assert scan['checks']['native_mcf_sha256']==motion['mcf_sha256']
        assert scan['checks']['native_history_audit_sha256']==digest(motion_file)
        pla=AUDIT/f'{branch}_{axis}_PLA_native.json'
        screen_file=pla.with_name(pla.stem+'_onset.json')
        levels=read(screen_file)
        assert levels['maximum_record_sha256']==digest(pla) and read(pla)['coordinate_source_sha256']==motion['mcf_sha256']
        cells={}
        for side,c in scan['cells'].items():
            lo=c['last_contiguous_clear_sample'];rate=scan['sample_rate_Hz']
            if c['first_intersecting_sample'] is None:
                assert side not in witness['cells']
                cells[side]=dict(last_proven_clear_ms=1000*lo/rate,unresolved_samples=c['unresolved_samples'])
                continue
            row=witness['cells'][side];lower,upper=row['first_intersection_interval_ms']
            assert lower==1000*lo/rate and upper==1000*row['sample']/rate and lower<upper
            assert row['residual_mm']<1e-9 and row['normal_cross_magnitude']>1e-5
            cells[side]=dict(interval_ms=[lower,upper],point_mm=row['quadratic_point_xyz_mm'])
        bounds=[(v['interval_ms'],k) for k,v in cells.items() if 'interval_ms' in v]
        order=None
        if len(bounds)==2:
            bounds.sort()
            if bounds[0][0][1]<bounds[1][0][0]:
                order=[k for _,k in bounds]
        nickel=motion.get('nickel_trial_crossing')
        nickel_ms=[1000*t for t in nickel['time_bracket_s']] if nickel else None
        first_delta=None
        if order and nickel_ms:
            lo,hi=cells[order[0]]['interval_ms']
            first_delta=[nickel_ms[0]-hi,nickel_ms[1]-lo]
        item=dict(motion_sha256=digest(motion_file),scan_sha256=digest(scan_file),witness_sha256=digest(witness_file),
                  PLA_screen_sha256=digest(screen_file),sample_rate_Hz=rate,cells=cells,order=order,
                  nickel_trial_crossing_ms=nickel_ms,nickel_minus_first_outer_interval_ms=first_delta,
                  PLA_first_coupon_crossings_ms={k:None if not v else [1000*r['time_s'] for r in v]
                                                 for k,v in levels['brackets'].items()})
        reserve=AUDIT/(material+'_pocket_preload_native.json')
        if reserve.exists():
            ref=read(reserve);record=ref['axes'][axis]
            assert ref['native_basis_sha256']==scan['basis_rst_sha256'] and record['native_mcf_sha256']==motion['mcf_sha256']
            item.update(middle_pressure_change_upper_bound_ms=record['upper_bound_ms'],reserve_sha256=digest(reserve))
        branches[material]=item
    write_json(AUDIT/f'outer_startup_events_{axis}.json',dict(base_axis=axis,models=branches,
               scope='Time ordering on the native trajectory linearized at bolt lock. Nickel uses the 185 MPa '
                     'exploratory trial yield threshold anywhere in the nickel strips. An outer-cell crossing is '
                     'an interpolated geometric intersection. These events do not directly give an impact or tearing load.'))
    print(axis,[(k,r['order'],r['nickel_minus_first_outer_interval_ms']) for k,r in branches.items()])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('axis',choices=('X','Y','Z'))
    compare(p.parse_args().axis)
