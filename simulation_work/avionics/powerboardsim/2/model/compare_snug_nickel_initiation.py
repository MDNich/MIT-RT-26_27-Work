"""Compare nickel initiation demand on audited bare, nylon and aluminium bilinear histories."""
import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from compare_snug_middle_engagement import OUTPUT as MATCHED
from film_identity import digest, verified, write_json
from snug_nickel_initiation import bilinear, integrate, tables
from stage_snug_fit import AUDIT, INPUTS

OUTPUT = AUDIT/'forward_screw_nickel_initiation.json'
REPLAY = AUDIT/'nickel_initiation_replay.json'


def compare():
    previous=read(REPLAY)
    verified(AUDIT/'damage_family_inputs.json',previous['family_inputs_sha256'])
    assert all(r['field_replay_verified'] for r in previous['native_material_controls'].values())
    curves=tables()
    baseline=bilinear(curves)
    assert baseline==previous['matched_bilinear'], 'Previous bare/nylon replay changed'
    matched=read(MATCHED)
    source=matched['sources']['aluminium']['checkpoint']
    checkpoint=ROOT/source['path'];verified(checkpoint,source['sha256'])
    cp=read(checkpoint)
    end=matched['last_common_native_set']
    assert end==baseline['last_before_refined_PLA_crossing']==22
    folder=ROOT/'.runtime/qa/snug125/directional-readback'/cp['case']/cp['checkpoint']
    rst=folder/'pull.rst';verified(rst,cp['rst_sha256'])
    verified(INPUTS/cp['case']/'model.inp',cp['input_sha256'])
    states=cp['states'][:end]
    assert all(r['within_screens'] for r in states)
    raw=reader.read_binary(str(rst))
    meshfile=ROOT/'.runtime/local_inputs/lateral_friction_locked/mesh.json'
    verified(meshfile,read(ROOT/'validation/local_inputs.json')['lateral_friction_locked']['files']['mesh.json'])
    mesh=read(meshfile)
    native={int(e[8]):e for e in raw.mesh.elem if e[8]<=2304}
    for j,nodes in enumerate(mesh['elements'],1):
        np.testing.assert_array_equal(native[j][10:14],nodes)
    rows,checks=integrate(raw,2304,np.arange(1,end+1),curves,
                          [r['travel_mm'] for r in states],
                          [r['cell_force_N'] for r in states])
    assert checks['maximum_nominal_peak_change_using_stress_tensor']<1e-8
    nylon=baseline['snug'];bare=baseline['bare']
    assert len(rows)==len(nylon)==end
    for old,new in zip(nylon[:12],rows[:12],strict=True):
        # Same preload and the three pull stations preceding pocket contact.
        assert old['curves']==new['curves']
    common=[]
    for pair in matched['common_native_travel']:
        k=pair['nylon']['native_set'];assert k==pair['aluminium']['native_set']
        a,b=nylon[k-1],rows[k-1]
        for material,row in [('nylon',a),('aluminium',b)]:
            assert abs(row['travel_mm']-pair[material]['travel_mm'])<1e-10
            assert abs(row['force_N']-pair[material]['cell_force_N'])<1e-8
        x=pair['travel_mm']
        upper=next(i for i,r in enumerate(bare) if r['travel_mm']>=x)
        bracket=bare[max(0,upper-1):upper+1]
        assert bracket[0]['travel_mm']<=x<=bracket[-1]['travel_mm']
        peaks={}
        for material,row in [('nylon',a),('aluminium',b)]:
            peak=row['curves']['0.3'];e=peak['nickel_element']
            peaks[material]=dict(element=e,section=peak['section'],corner=peak['corner'],
                region=mesh['region'][e-1],
                undeformed_element_centroid_mm=np.mean([mesh['nodes'][str(n)] for n in mesh['elements'][e-1]],axis=0).tolist())
        common.append(dict(native_set=k,travel_mm=x,nylon=a,aluminium=b,nominal_peak_locations=peaks,
                           bare_bracket=bracket,
                           bare_nominal_interpolated=float(np.interp(x,[r['travel_mm'] for r in bracket],
                               [r['curves']['0.3']['maximum'] for r in bracket]))))
    force=baseline['common_load_N']
    equal_load={}
    for material,history in [('nylon',nylon),('aluminium',rows)]:
        candidates=[r for r in history if r['travel_mm']>0]
        upper=next(i for i,r in enumerate(candidates) if r['force_N']>=force)
        assert upper>0
        bracket=candidates[upper-1:upper+1]
        equal_load[material]=dict(native_bracket=bracket,
             nominal_criterion_bracket=[r['curves']['0.3']['maximum'] for r in bracket])
    assert [r['native_set'] for r in equal_load['nylon']['native_bracket']]==baseline['snug_common_load_bracket']
    assert [r['native_set'] for r in equal_load['aluminium']['native_bracket']]==cp['equal_bare_endpoint_load']['cased']['native_sets']
    result=dict(previous_replay_sha256=digest(REPLAY),matched_scope_sha256=digest(MATCHED),
         aluminium_checkpoint_sha256=digest(checkpoint),aluminium_rst_sha256=cp['rst_sha256'],
         aluminium_input_sha256=cp['input_sha256'],integration_source_sha256=digest(ROOT/'model/snug_nickel_initiation.py'),
         unchanged_bare_and_nylon_replay=True,stored_sites_per_set=2304*12,
         aluminium_checks={k:checks[k] for k in ('negative_plastic_increment','maximum_nominal_peak_change_using_stress_tensor')},
         nickel_mesh_sha256=digest(meshfile),aluminium_history=rows,common_native_travel=common,
         common_load_N=force,bare_at_common_load=bare[-1],equal_load=equal_load,
         scope='Independent ductile-initiation integral on the saved bilinear nickel histories. '
               'Unity denotes initiation for the assumed curve; it is not percent of allowable stress. '
               'The damage law has no feedback on these bilinear solutions. Comparisons end before the refined nylon PLA crossing. '
               'Local clamps, fixed neighbour cells, rigid welds and unresolved contact increments remain model assumptions.')
    write_json(OUTPUT,result)
    print('Equal-load nominal criterion:',{m:r['nominal_criterion_bracket'] for m,r in equal_load.items()},flush=True)
    for r in common[-2:]:
        print(r['travel_mm'],{m:r[m]['curves']['0.3'] for m in ('nylon','aluminium')},flush=True)


if __name__=='__main__':
    compare()
