"""Check completed global structural, modal or PSD output before dispatching its dependants."""
from pathlib import Path
import csv,hashlib,json,re,sys
import numpy as np
from native_rst import read_rst
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def audit(case,campaign):
    receipt=ROOT/'.runtime/receipts'/campaign/case
    d=ROOT/'.runtime/archive'/campaign/case
    meta=load(receipt/'archived.json')
    assert load(receipt/'status.json')['phase']=='solver_complete' and meta['case']==case
    assert all((d/f['name']).stat().st_size==f['bytes'] for f in meta['files'])
    lst=(d/'solve.out').read_text(errors='replace')
    assert 'RUN COMPLETED' in lst and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',lst)
    rst=read_rst(d/'file.rst')
    t=np.asarray(rst.time_values);g=rst.grid
    assert len(t)>0 and np.all(np.isfinite(t))
    # For PSD, the last result can be acceleration; only the labeled relative-displacement set is in metres.
    nid,disp=rst.nodal_solution([3,1]) if '_psd_' in case else rst.nodal_displacement(len(t)-1)
    valid=np.all(np.isfinite(disp[:,:3]),axis=1)
    assert valid.sum()>1000
    result=dict(case=case,campaign=campaign,sets=len(t),rst_sha256=next(f['sha256'] for f in meta['files'] if f['name']=='file.rst'),last_time_or_hz=float(t[-1]),finite_displacement_nodes=int(valid.sum()),max_vector_u=float(np.max(np.linalg.norm(disp[valid,:3],axis=1))),warnings=int(re.search(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',lst)[1]))
    if case.endswith('_static'):
        data=np.loadtxt(d/'bolt_preload_audit.csv',skiprows=1,delimiter=',');assert data.shape==(12,5)
        assert abs(t[-1]-2)<1e-8 and np.max(np.abs(data[6:,4]-750))<1
        result['locked_bolt_reactions_N']=data[6:,4].tolist()
        if not case.startswith('bare'):
            with (d/'case_contact.csv').open() as f:
                rows=list(csv.DictReader(f))
            last={key:float(value) for key,value in rows[-1].items()}
            assert abs(last['time_s']-2)<1e-8 and last['n_contact']>0
            from global_contact import history
            if case.startswith('snug125_'):
                from global_contact import pair_summary
                grid=rst.grid.cell_data
                ids=np.sort(grid['ansys_elem_num'][grid['ansys_etype']==853])
                # The native readback selects TYPE 853, including DMP real-constant children.
                stored=[pair_summary(k,t[k],ids,*rst.element_solution_data(k,'ECT')) for k in range(rst.nsets)]
            else:
                stored=history(rst,853,853)
            assert len(rows)==len(stored)
            for item,raw in zip(rows,stored,strict=True):
                item={k:float(v) for k,v in item.items()}
                assert np.isfinite(list(item.values())).all() and item['set']==raw['set'] and abs(item['time_s']-raw['time_s'])<1e-7
                assert item['n_contact']==raw['n_contact']
                # POST1 classifies entire faces with exactly integer ETABLE status. A face
                # with both far and near corners can have a fractional ETABLE value.
                bins=[int(item[x]) for x in ('far','near','sliding','sticking')]
                highest=[raw[x] for x in ('far','near','sliding','sticking')]
                uniform=raw['fully_uniform_face_bins']
                assert bins==highest or bins==uniform,(bins,highest,uniform)
                if raw['p_max']==0:assert item['p_max_Pa']==0
            result['post1_integer_status_summary']=last
            result['installed_contact_summary']=stored[-1]
            result['contact_history_native_RST']=stored
            result['contact_scope']='Engineering interpretation requires penetration, seating loads and PLA stress review.'
    elif '_psd_' in case:
        # Workbench writes the statistical result sets after the modal basis; select PSD labels in the field audit.
        assert re.search(r'(?im)^\s*SPECTRUM TYPE[ .]+PSD\s*$',lst)
        assert re.search(r'(?im)^\s*MODE COMBINATION TYPE[ .]+PSD\s*$',lst)
        result.pop('max_vector_u')  # Orthogonal component RMS values are not a peak displacement magnitude.
        from psd_fields import recover
        result['native_psd_fields']=recover(d/'file.rst')
        branch,axis=case.removesuffix('_private1').rsplit('_psd_',1)
        if branch=='bare':
            from psd_comparison import check_october
            result['october_native_comparison']=check_october(case,axis,result['native_psd_fields'])
        from independent_psd import run as independent_response
        check=ROOT/'validation/independent_psd'/f'{branch}_basis.json'
        if not check.exists():independent_response(branch,campaign)
        expected=load(check);parent=load(ROOT/'validation/global'/f'{branch}_basis.json')
        assert expected['campaign']==parent['campaign']==campaign and expected['rst_sha256']==parent['rst_sha256'] and expected['baseline_5pct_screen_passed']
        errs={}
        for scope,vals in expected['base_cases'][axis]['scopes'].items():
            actual=result['native_psd_fields']['scopes']['pla' if scope=='case' else scope]['directional_rms_u_mm']
            err=np.abs(np.asarray(actual)/np.array(vals['peak_directional_RMS_mm'])-1)
            assert np.max(err)<.05,(case,scope,actual,vals,err)
            errs[scope]=err.tolist()
        result['independent_displacement_relative_errors']=errs
        if (d/'private_psd.json').exists():
            from private_psd import verify
            result['private_modal_directory']=verify(case,campaign)
        if (d/'remote_psd.json').exists():
            from stage_remote_psd import verify
            result['remote_modal_directory']=verify(case,campaign)
    else:
        assert np.all(np.diff(t)>0)
        if case.endswith('_basis'):assert len(t)>=20 and t[-1]<=4000.0001
        else:assert len(t)==20
        result['frequencies_Hz']=t.tolist()
        if case.startswith('flush_') and ('_surf1_' in case or '_default_' in case):
            from actuator_control import modal_residual
            parent=load(receipt/'status.json')['parent']
            assert parent==case.rsplit('_',1)[0]+'_static'
            checks=[]
            for k in range(rst.nsets):
                ids,u=rst.nodal_displacement(k)
                checks.append(modal_residual(ids,u,range(960101,960105),range(950002,950010,2),range(960111,960115)))
            result['installed_head_motion_check']=dict(static_parent=parent,checked_modes=rst.nsets,
                maximum_relative_error={key:max(q[key] for q in checks) for key in checks[0]})
        if case.startswith('bare_') and (case.endswith(('_original','_refined','_sturm'))):
            mesh_name=case.removeprefix('bare_').removesuffix('_sturm')
            ref=ROOT.parent/f'1/output/latex/modal_reproduction/native/default_{mesh_name}/frequencies.csv'
            expected=np.loadtxt(ref,delimiter=',',skiprows=1)[:,1]
            assert expected.shape==t.shape
            error=float(np.max(np.abs(t/expected-1)))
            assert error<1e-4, f'Mode sequence differs from the reference by {error:.3%}'
            result['maximum_relative_frequency_difference_from_october']=error
    if not case.startswith('bare'):
        for mat in (850,851):assert np.count_nonzero(g.cell_data['ansys_material_type']==mat)>0
    out=ROOT/'validation/global';out.mkdir(exist_ok=True);dest=out/(case+'.json')
    temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(dest)
    if case.startswith('snug125_') and '_psd_' in case:
        from psd_comparison import summary
        summary(branch,axis)
    if case.startswith('snug125_') and case.endswith('_static'):
        from snug_installed import review
        review(case,campaign)
        if case in ('snug125_nylon_mesh15_static','snug125_nylon_tol001_static','snug125_aluminium_mesh15_static','snug125_aluminium_out2_static','snug125_aluminium_project3_static','snug125_aluminium_cylinder_static'):
            from snug_locked_contact import run as check_faces
            from compare_static import compare as check_board
            from snug_mesh_comparison import compare_forces
            check_faces(case,campaign)
            check_board(case,campaign)
            from snug_equilibrium_residual import audit as check_residuals
            check_residuals(case,campaign)
            if case=='snug125_aluminium_out2_static':
                from snug_pocket_preload import repeat
                from film_identity import write_json
                proofs,errors=repeat('snug125_aluminium','snug125_aluminium_out2',campaign)
                write_json(ROOT/'validation/snug125/aluminium_force_repeat.json',
                           dict(original_static_rst_sha256=proofs[0]['rst_sha256'],
                                repeat_static_rst_sha256=proofs[1]['rst_sha256'],
                                maximum_nodal_displacement_difference_m_by_set=errors,
                                identical_locked_bolt_forces_and_contact_histories=True))
                from snug_pocket_unloading import compare_native_repeat
                compare_native_repeat('snug125_aluminium',case,errors)
            if case in ('snug125_aluminium_project3_static','snug125_aluminium_cylinder_static'):
                from snug_unilateral_geometry import audit_projection
                audit_projection(campaign,case)
            elif case.startswith('snug125_aluminium_'):
                pair=('snug125_aluminium_out2_static','snug125_aluminium_mesh15_static')
                if ((ROOT/'validation/snug125/aluminium_force_repeat.json').is_file()
                        and all((ROOT/'validation/snug125'/(name+'_residuals.json')).is_file() for name in pair)):
                    compare_forces(pair[1])
            else:compare_forces(case)
    if case=='snug125_nylon_mesh3_basis':
        from snug_coarse_modes import audit as check_coarse_basis
        check_coarse_basis(campaign)
    print(case,'verified',flush=True)
if __name__=='__main__':audit(*sys.argv[1:])
