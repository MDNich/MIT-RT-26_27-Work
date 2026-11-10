"""Compare the two nominally identical nylon preloads at matched equilibria and CAD bearing locations."""
import numpy as np

from audit_local import ROOT,read
from film_identity import digest,write_json
from stage_snug_fit import AUDIT,input_record


def statistics(case):
    model=input_record(case)
    verdict=read(AUDIT/f'{case}_installed.json')
    detail=read(AUDIT/f'{case}_contacts.json')
    fitted=read(ROOT/'validation/static'/f'{case}.json')
    material=read(ROOT/'validation/installation_material'/f'{case}.json')
    assert detail['rst_sha256']==material['rst_sha256']==verdict['rst_sha256']==fitted['models'][case]['source_rst_sha256']
    assert detail['case_mesh_sha256']==model['mesh_sha256'] and model['step_sha256']==detail['step_sha256']
    assert material['input_sha256']==model['input_sha256']
    times=[r['time_s'] for r in verdict['contact_history']]
    assert times==[r['load_time'] for r in detail['contact_history']]==[r['time_s'] for r in material['history']]
    active=[r for r in verdict['contact_history'] if r['sliding']+r['sticking']>0]
    stats=fitted['models'][case]['scopes']
    rows=detail['locked_geometry']['rows']
    final_contacts={str(level):[row['body'] for row in rows if row['subdivision']==level and row['intersects']] for level in (2,3)}
    return dict(case=case,step_sha256=model['step_sha256'],mesh_size_mm=model['size_mm'],
        bare_sha256=fitted['models']['bare_static']['source_rst_sha256'],input_sha256=model['input_sha256'],
        rst_sha256=verdict['rst_sha256'],locked_surface_check_sha256=digest(AUDIT/f'{case}_contacts.json'),
        supports=model['supports'],number_of_PLA_tets=material['case_tets'],times=times,
        peak_final_U_um={name:1000*v['peak_total_U_mm'] for name,v in stats.items()},
        peak_PCB_node=int(stats['pcb']['node']),matched_PCB_nodes=fitted['same_node_comparison']['pcb']['matched_nodes'],
        max_locked_bolt_error_N=max(abs(f-750) for f in verdict['locked_bolt_forces_N']),
        peak_in_plane_PLA_tension_MPa=max(r['all_in_plane_tension_MPa'] for r in material['history']),
        peak_layer_PLA_tension_MPa=max(r['all_layer_tension_MPa'] for r in material['history']),
        highest_pressure_MPa=max(r['p_max'] for r in verdict['contact_history'])*1e-6,
        locked_pressure_MPa=verdict['contact_history'][-1]['p_max']*1e-6,
        first_closed_load_time=active[0]['time_s'] if active else None,
        locked_closed_faces=sum(len(q['element_ids']) for q in detail['contact_history'][-1]['loaded_case_faces']),
        locked_intersections_by_surface_level=final_contacts,pressure_path_MPa=[r['p_max']*1e-6 for r in verdict['contact_history']],
        loaded_CAD_faces=sorted(int(k) for k in detail['loaded_STEP_face_geometry']))


def compare():
    runs=[statistics(case) for case in ('snug125_nylon_mesh3_static','snug125_nylon_static')]
    a,b=runs
    assert a['step_sha256']==b['step_sha256'] and a['bare_sha256']==b['bare_sha256']
    assert np.allclose(a['times'],b['times'],atol=1e-10,rtol=0) and a['matched_PCB_nodes']==b['matched_PCB_nodes']
    for x,y in zip(a['supports'],b['supports'],strict=True):
        for name in ('board_center_mm','screw_axis_mm','case_center_mm','grip_mm'):
            assert np.allclose(x[name],y[name],rtol=0,atol=1.e-7)
        assert x['bearing_nodes'][0]==y['bearing_nodes'][0]
    diff={key:100*(b[key]-a[key])/a[key] if a[key] else None for key in
          ('highest_pressure_MPa','locked_pressure_MPa','peak_in_plane_PLA_tension_MPa','peak_layer_PLA_tension_MPa')}
    diff['locked_PCB_peak_displacement']=100*(b['peak_final_U_um']['pcb']/a['peak_final_U_um']['pcb']-1)
    write_json(AUDIT/'nylon_mesh_comparison.json',dict(runs=runs,fine_vs_coarse_change_percent=diff,
        scope='Same board, CAD registration, fasteners and load histories. Changing PLA volume and contact meshes also changes the case-side bearing nodes inside each fixed physical footprint. Two meshes measure sensitivity at these resolutions.'))


def force_pair(control):
    spec = input_record(control)
    if 'absolute_force_criterion_N' in spec:
        reference = spec['reference_case']
        stem = control.removeprefix('snug125_').removesuffix('_tol001_static')
        return reference, AUDIT / f'{stem}_force_tolerance_comparison.json'
    material = spec['material']
    return f'snug125_{material}_out2_static', AUDIT / f'{material}_force_mesh_comparison.json'


def compare_forces(control='snug125_nylon_mesh15_static'):
    reference_case,output=force_pair(control)
    cases=(reference_case,control)
    same_mesh='absolute_force_criterion_N' in input_record(control)
    if same_mesh:
        reference, tight = map(input_record,cases)
        assert tight['reference_input_sha256']==reference['input_sha256'] and tight['mesh_sha256']==reference['mesh_sha256']
        assert tight['post_sha256']==reference['post_sha256'] and tight['supports']==reference['supports']
    runs=[statistics(case) for case in cases]
    coarse,fine=runs
    assert coarse['step_sha256']==fine['step_sha256'] and coarse['bare_sha256']==fine['bare_sha256']
    assert coarse['matched_PCB_nodes']==fine['matched_PCB_nodes']
    for first,last in zip(coarse['supports'],fine['supports'],strict=True):
        for field in ('case_center_mm','board_center_mm','screw_axis_mm','grip_mm'):
            assert np.allclose(first[field],last[field],atol=1.e-7,rtol=0)
        assert first['bearing_nodes'][0]==last['bearing_nodes'][0]
    curves=[]
    for case,run in zip(cases,runs,strict=True):
        result=read(AUDIT/(case+'_contacts.json'))
        force=result['resultant_force_check']
        assert len(force)==len(run['times']) and [r['native_set'] for r in force]==list(range(1,len(force)+1))
        run['force_history']=force
        run['locked_resultant_N']=force[-1]['resultant_N']
        curves.append(np.array([r['force_xyz_N'] for r in force]))
    shared=[]
    for i,t in enumerate(coarse['times']):
        matching=np.flatnonzero(np.isclose(t,fine['times'],atol=1.e-9,rtol=0))
        if not len(matching):continue
        j,=matching
        x,y=curves[0][i],curves[1][j]
        shared.append(dict(load_time=t,coarse_set=i+1,fine_set=int(j)+1,
                           coarse_force_xyz_N=x.tolist(),fine_force_xyz_N=y.tolist(),
                           delta_vector_norm_N=float(np.linalg.norm(y-x)),
                           fine_minus_coarse_magnitude_N=float(np.linalg.norm(y)-np.linalg.norm(x))))
    assert shared and np.isclose(shared[-1]['load_time'],2.) and any(np.isclose(r['load_time'],1.) for r in shared)
    a=coarse['locked_resultant_N'];b=fine['locked_resultant_N']
    write_json(output,dict(runs=runs,matched_native_stations=shared,
        locked_resultant_change_percent=100*(b/a-1) if a>0 else None,
        scope='Matched boundaries, solver loads and material. Only shared native equilibria are paired; '
              'all saved states are retained separately. The native contact vector in each run was independently summed.'))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force-pair',action='store_true')
    if parser.parse_args().force_pair:compare_forces()
    else:compare()
