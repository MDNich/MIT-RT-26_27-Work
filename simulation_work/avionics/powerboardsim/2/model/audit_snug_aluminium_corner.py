"""Audit completed local refinements and supersede the paired pull's material scope."""
import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from stage_snug_fit import AUDIT

SOURCE=AUDIT/'aluminium_forward_corner_submodel.json'
OUTPUT=AUDIT/'forward_material_scope_reassessment.json'


def audit():
    data=read(SOURCE)
    verified(SOURCE,read(ROOT/'.runtime/qa/snug125/aluminium-corner-submodel/complete.json')['output_sha256'])
    verified(ROOT/'model/snug_tab_submodel.py',data['shared_patch_solver_sha256'])
    checkpoint=AUDIT/f"{data['case']}_{data['checkpoint']}_checkpoint.json"
    cp=read(checkpoint)
    assert cp['case']==data['case'] and cp['converged_sets']==24
    checks={};seen=set();first=[]
    for name,region in data['regions'].items():
        verified(checkpoint,region['checkpoint_sha256'])
        assert cp['rst_sha256']==region['DPF_source_sha256'] and cp['input_sha256']==region['input_sha256']
        verified(ROOT/'.runtime/inputs'/data['case']/'model.inp',region['input_sha256'])
        fields=ROOT/'.runtime/post/nov08_01'/data['case']/'pull_work'/cp['rst_sha256'][:16]/'sets_9_24/U'
        for row in region['field_hashes']:
            for ext,key in (('.ids','ids_sha256'),('.u','U_sha256')):
                path=fields/f"set_{row['native_set']:04d}{ext}"
                if path not in seen:verified(path,row[key]);seen.add(path)
        native=region['native'];records=region['independent']
        sets=[r['native_set'] for r in native]
        assert sets==list(range(9,25)) and len(records)==16
        for r in native:
            assert abs(cp['states'][r['native_set']-1]['travel_mm']-r['travel_mm'])<1e-12
        def key(r):return r['radius_mm'],r['subdivisions'],r['alternate_diagonal'],r['stiffness_quadrature_points']
        index={key(r):r for r in records}
        expected={(radius,n,False,4) for radius,ns in ((1.8,(1,2,4,8)),(2.75,(1,2,4,8)),(3.75,(1,2,4))) for n in ns}
        expected|={(1.8,n,True,4) for n in (2,4,8)}|{(1.8,n,False,27) for n in (1,4)}
        assert len(index)==16 and index.keys()==expected
        baseline_error=0.;volume_error=0.;quadrature_error=0.
        for r in records:
            values=np.asarray(r['high_Y_root_max_layer_tension_MPa'])
            assert values.shape==(16,) and np.isfinite(values).all()
            cross=np.flatnonzero(values>=40.5)
            above=sets[cross[0]] if len(cross) else None
            assert above==r['first_sample_above_coupon_native_set']
            reference=index[(1.8,r['subdivisions'],False,4)]
            assert above==reference['first_sample_above_coupon_native_set']
            assert r['max_free_dof_residual_N']<1e-6
            volume_error=max(volume_error,abs(r['star_volume_mm3']-native[0]['volume_mm3']))
            if r['subdivisions']==1:
                error=float(np.max(abs(values-[v['max_MPa'] for v in native])))
                baseline_error=max(baseline_error,error)
                assert error<.30 and max(r['max_node_error_relative_to_native_um'])<.1
            if r['stiffness_quadrature_points']==27:
                error=float(np.max(abs(values-reference['high_Y_root_max_layer_tension_MPa'])))
                quadrature_error=max(quadrature_error,error)
                assert error<1e-6
            if above is not None:first.append(above)
        assert volume_error<2e-6
        main=[index[(1.8,n,False,4)] for n in (1,2,4,8)]
        checks[name]=dict(root_node=region['root_node'],root_xyz_mm=region['root_xyz_mm'],
            native_baseline_error_MPa=baseline_error,volume_error_mm3=volume_error,
            quadrature_peak_error_MPa=quadrature_error,
            largest_free_dof_residual_N=max(r['max_free_dof_residual_N'] for r in records),
            final_travel_mm=native[-1]['travel_mm'],
            native_final_peak_MPa=native[-1]['max_MPa'],
            refined_final_peaks_MPa=[r['high_Y_root_max_layer_tension_MPa'][-1] for r in main],
            fixed_volume_mm3=native[0]['volume_mm3'],
            refined_final_volume_means_MPa=[r['star_mean_layer_tension_MPa'][-1] for r in main],
            first_crossing_sets=[r['first_sample_above_coupon_native_set'] for r in main])
    high=min(first);assert high==18
    bracket=cp['states'][high-2:high]
    assert [r['native_set'] for r in bracket]==[high-1,high]
    comparisons={}
    for name in ('forward_screw_checkpoint_comparison','forward_mount_checkpoint_comparison',
                 'forward_middle_engagement_comparison','forward_screw_energy_comparison','forward_screw_nickel_initiation'):
        path=AUDIT/(name+'.json');comparisons[name]=digest(path)
    common=read(AUDIT/'forward_middle_engagement_comparison.json')['common_native_travel']
    before=[r for r in common if r['aluminium']['native_set']<high]
    after=[r['aluminium']['native_set'] for r in common if r['aluminium']['native_set']>=high]
    assert before[-1]['aluminium']['native_set']==17 and after==list(range(18,23))
    output=dict(case=data['case'],input_sha256=cp['input_sha256'],checkpoint_sha256=digest(checkpoint),
        checkpoint_path=str(checkpoint.relative_to(ROOT)),submodel_sha256=digest(SOURCE),
        shared_patch_solver_sha256=data['shared_patch_solver_sha256'],checks=checks,
        native_set=high,travel_bracket_mm=[r['travel_mm'] for r in bracket],
        last_common_station_below_all_tested_corner_references=before[-1],
        numerical_only_paired_sets=after,historical_comparison_sha256=comparisons,
        scope='Supersedes the earlier nylon-only material screen for the exact paired forward decks. '
              'No tested corner exceeds its reference through saved set 17; this is not a proven safe load. '
              'The aluminium sharp-corner stress and its coupon crossing do not converge with refinement. '
              'Sets 18 onward, including the earlier 0.207 and 0.219 mm comparisons, are numerical continuation only. '
              'Native equilibrium, work and nickel audit values remain unchanged. The 8.54 N brackets precede this crossing. '
              'Local cut-displacement elasticity does not redistribute assembly loads or simulate fracture.')
    write_json(OUTPUT,output)
    print('Material scope:',output['travel_bracket_mm'],'last common set',high-1)
    print(checks)


if __name__=='__main__':audit()
