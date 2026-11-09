"""Audit converged installation states separately from the subsequent pull (local N–mm model)."""
import json
import re
import sys

import numpy as np
from ansys.mapdl import reader
from audit_local import ROOT, read, table
from local_equilibrium import movement_table, recover, write_csv
from stage_local_jobs import digest


def contact_history(raw, records, tab, topology, clamp_steps=2):
    """Independently decode binary corner statuses/penetration and the native force on each oriented pair."""
    faces=raw.grid.cell_data
    groups={}
    for pid,count in topology.items():
        ids=faces['ansys_elem_num'][(faces['ansys_real_constant']==pid)&(faces['ansys_etype']==(858 if pid>=880 else (862 if pid<=862 else 864)))]
        assert len(ids)==count,(pid,len(ids),count)
        groups[pid]=ids
    output=[];first={};worst={i:0. for i in groups}
    case_error=neighbor_error=seat_error=0.
    for ii,rec in enumerate(records):
        k=rec['native_set']
        enum,vals,_=raw.element_solution_data(k-1,'EMN')
        loads={};contacts={}
        for pid,ids in groups.items():
            loc=np.searchsorted(enum,ids)
            assert np.array_equal(enum[loc],ids)
            available=[vals[j] for j in loc if vals[j] is not None and len(vals[j])]
            a=np.stack(available) if available else np.empty((0,45))
            assert a.shape[1]>=45
            closed=(a[:,40]==2)|(a[:,40]==3)
            loaded=((a[:,:4]==2)|(a[:,:4]==3))&closed[:,None]
            p=float(a[:,8:12][loaded].max(initial=0.))
            contact=tab[(tab['set']==k)&(tab['pair']==pid)]
            assert len(contact)==1 and int(contact['elements'][0])==len(ids) and int(contact['closed'][0])==closed.sum()
            assert abs(contact['time'][0]-rec['time'])<1e-7
            f=a[:,42:45].sum(axis=0,dtype=float)
            assert np.allclose(f,[contact[f'{x}_N'][0] for x in ('fx','fy','fz')],rtol=3e-6,atol=2e-5)
            loads[pid]=f;contacts[pid]=int(closed.sum())
            if contacts[pid] and pid not in first:
                first[pid]=dict(native_set=k,stage=rec['loadstep'],top_travel_bracket_mm=[
                    records[max(0,ii-1)]['screw1_u_mm_z'],rec['screw1_u_mm_z']])
            if rec['loadstep']<=clamp_steps and (closed.any() or np.linalg.norm(f)>.005):
                raise ValueError(f'Case already engaged during washer clamping at set {k}, pair {pid}')
            worst[pid]=max(worst[pid],p)
            output.append(dict(native_set=k,stage=rec['loadstep'],pair=pid,closed=int(closed.sum()),
                loaded_corners=int(loaded.sum()),max_closed_penetration_mm=p,fx_N=f[0],fy_N=f[1],fz_N=f[2]))
        # 861/862 contact elements sit on the case, 863/864 on the two nickel strips.
        screw=np.array([rec['screw_support_N_'+a] for a in 'xyz'])
        neighbor=np.array([rec['neighbor_support_N_'+a] for a in 'xyz'])
        seat_contact=np.zeros(3)
        for j,pid in enumerate(range(880,884),1):
            if pid in loads:
                support=np.array([rec[f'seat{j}_support_N_'+a] for a in 'xyz'])
                imbalance=np.linalg.norm(support+loads[pid]);seat_error=max(seat_error,float(imbalance))
                assert imbalance<.03+.002*np.linalg.norm(support),(pid,k,imbalance)
                seat_contact+=loads[pid]
        err=float(np.linalg.norm(screw-loads[861]-loads[862]+loads.get(863,0.)+loads.get(864,0.)-seat_contact))
        nerr=float(np.linalg.norm(neighbor+loads[862]))
        if err>.03+.002*sum(np.linalg.norm(x) for x in loads.values()) or nerr>.03+.002*np.linalg.norm(neighbor):
            raise ValueError(f'Case or neighboring target contact does not balance its supports, set {k}: {err}, {nerr} N')
        case_error=max(case_error,err);neighbor_error=max(neighbor_error,nerr)
    assert len(tab)==len(output)
    return output,dict(contact_onset=first,peak_closed_corner_penetration_mm=worst,
                worst_case_support_contact_residual_N=case_error,worst_neighbor_contact_residual_N=neighbor_error,
                **({'worst_fixed_seat_contact_residual_N':seat_error} if any(pid>=880 for pid in groups) else {}))


def indexed(tab,sets):
    assert np.array_equal(tab['set'],sets), 'Missing or diagnostic set in native POST1 readback'
    return tab


def audit(case,campaign):
    dest=ROOT/'.runtime/post'/campaign/case;dest.mkdir(exist_ok=True,parents=True)
    folder=ROOT/'.runtime/archive'/campaign/case;receipt=ROOT/'.runtime/receipts'/campaign/case
    status=read(receipt/'status.json');ledger=read(receipt/'archived.json');spec=read(folder/'local_job.json')
    face_seats=case.endswith('_seatfaces1')
    grip=spec.get('load_protocol')=='grip_install'
    registry='perfect_grip_cases.json' if grip else ('local_seat_jobs.json' if face_seats else 'local_install_jobs.json')
    if spec.get('sensitivity_reference'):registry='damage_variant_inputs.json'
    if spec.get('bearing_pilots'):registry='rocking_bearing_input.json'
    catalog=read(ROOT/'validation'/registry)
    if face_seats and case not in catalog:catalog=read(ROOT/'validation/flush_pull_variants.json')
    ref=catalog[case]
    assert status['phase']=='solver_complete' and case==spec['case']==status['case']==ledger['case']
    assert spec['load_protocol'] in ('four_stage_install','grip_install') and digest((folder/'local_job.json').read_bytes())==ref['spec_sha256']
    assert status['input_sha256'].lower()==ref['input_sha256']==spec['files']['model.inp']
    for name,sha in spec['files'].items():assert digest((folder/name).read_bytes())==sha
    assert all((folder/r['name']).stat().st_size==r['bytes'] for r in ledger['files'])
    source=ROOT/'.runtime/local_inputs'/spec['source']
    listing=(folder/'solve.out').read_text(errors='replace')
    damage=spec['job']=='tear'
    rst=folder/(spec['job']+'.rst')
    movements=movement_table(folder/'moving_supports.csv')
    rows=recover(rst,source,movements,True,moving_screw_tops=True,seat_pilots=spec.get('seat_pilots',()))
    done=[tuple(map(int,x)) for x in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',listing)]
    assert done==[(r['loadstep'],r['substep']) for r in rows] and done[0]==(1,1)
    for (sa,ia),(sb,ib) in zip(done,done[1:]):
        assert (sb==sa and ib==ia+1) or (sb==sa+1 and ib==1)
    sets=[r['native_set'] for r in rows]
    if damage:
        inv=indexed(table(folder/'set_inventory.csv'),sets)
        kin=indexed(table(folder/'damage_kinematics.csv'),sets)
        assert np.array_equal(inv['loadstep'],[r['loadstep'] for r in rows]) and np.array_equal(inv['substep'],[r['substep'] for r in rows])
        h={key:kin[key] for key in kin.dtype.names}
        h.update(ux_mm=inv['ux_mm'],fx_N=inv['fx_N'],max_eppl=inv['peeq'])
        clamp={'time':inv['time']}
        for j in (1,2):
            clamp[f'washer{j}_RFz']=inv[f'clamp{j}_N']
            clamp[f'washer{j}_uz']=np.array([r[f'washer{j}_u_mm_z'] for r in rows])
    else:
        h=indexed(table(folder/'history.csv'),sets)
        if not grip:clamp=indexed(table(folder/'contact_history.csv'),sets)
    solid=indexed(table(folder/'case_solid.csv'),sets)
    assert np.all(solid['solids']==16108) and np.all(solid['seqv_MPa']>=0)
    times=np.array([r['time'] for r in rows])
    assert np.allclose(times,h['time'],atol=5e-9,rtol=0)
    if not grip:assert np.allclose(times,clamp['time'],atol=5e-9,rtol=0)
    assert np.allclose([r['cell_fx_N'] for r in rows],h['fx_N'],atol=1e-5,rtol=1e-6)
    lock=spec['installation_start_time'] if grip else spec['washer_lock_time']
    seat,end=spec['installed_time'],spec['end_time']
    expected=(0.,1.,2.) if grip else (2.,3.,11. if damage else 4.)
    assert (lock,seat,end)==expected and times[-1]<=end+1e-8
    # Check the complete displacement path, not just whether the last actuator happened to reach 3 mm.
    uz=spec['top_travel_mm']*np.clip((times-lock)/(seat-lock),0,1)
    ux=spec['cell_pull_mm']*np.clip((times-seat)/(end-seat),0,1)
    assert np.allclose(h['ux_mm'],ux,rtol=0,atol=2e-6)
    assert all(np.max(abs(h[k][times<=lock]),initial=0)<1e-7 for k in ('uy_mm','uz_mm','rotx','roty','rotz'))
    for i in range(1,5):
        for axis in 'xyz':
            assert np.allclose([r[f'screw{i}_u_mm_{axis}'] for r in rows],uz if axis=='z' else 0.,atol=2e-6,rtol=0)
    for t in ((seat,end) if grip else (1.,lock,seat,end)):
        if times[-1]>=t-1e-9:assert np.count_nonzero(np.isclose(times,t,rtol=0,atol=1e-9))==1
    if not grip and times[-1]>=lock-1e-9:
        for i in (1,2):
            at=np.flatnonzero(np.isclose(times,lock,rtol=0,atol=1e-9))[0]
            assert abs(clamp[f'washer{i}_RFz'][at]-750)<.2
            assert np.ptp(clamp[f'washer{i}_uz'][at:])<1e-7
    # Reactions use current physical support locations, including the advancing screw heads.
    ff=np.array([[r[f'force_N_{a}'] for a in 'xyz'] for r in rows])
    mm=np.array([[r[f'moment_cell_Nmm_{a}'] for a in 'xyz'] for r in rows])
    drive=np.array([abs(r['cell_fx_N'])+sum(abs(r[f'screw{i}_force_N_z']) for i in range(1,5)) for r in rows])
    if np.any(np.linalg.norm(ff,axis=1)>.2+.001*drive) or np.any(np.linalg.norm(mm,axis=1)>1.+.002*42.5*drive):
        raise ValueError('Whole-fixture force or moment imbalance')
    write_csv(rows,dest/'whole_fixture_balance.csv')
    if damage and np.any(inv['loadstep']>=4):
        from nickel_pull_balance import native_check
        native_check(folder,dest/'whole_fixture_balance.csv',campaign,seat)
    topology={int(float(p['pair'])):int(float(p['contact'])) for p in read(ROOT/'validation/flush_approach_preflight.json')['pairs']}
    if face_seats:
        topology.update({p['real']:p['tab_faces'] for p in read(ROOT/'validation/local_seat_preflight.json')['pairs']})
    if 'nickel_faces_per_side' in spec:
        topology.update({pid:spec['nickel_faces_per_side'] for pid in (863,864)})
    raw=reader.read_binary(str(rst))
    pairs,checks=contact_history(raw,rows,table(folder/'case_pairs.csv'),topology,clamp_steps=0 if grip else 2)
    from tab_seating import trace
    tab_history=trace(raw,sets)
    (dest/'tab_plane_history.json').write_text(json.dumps(tab_history,indent=2)+'\n')
    write_csv(pairs,dest/'closed_contacts.csv')
    # Mechanical work of the four driven tops, prescribed cell UX and the two washer loads.
    # Rotation at each screw is held at zero and released cell DOFs carry no imposed moment.
    work={};groups={'drawdown':[(f'screw{i}_u_mm_z',f'screw{i}_force_N_z') for i in range(1,5)],
        'side_pull':[('ux_mm','cell_fx_N')]}
    if not grip:groups['washer_preload']=[(f'washer{i}_u_mm_z',f'washer{i}_force_N_z') for i in (1,2)]
    for name,signals in groups.items():
        w=0.
        for u,f in signals:
            travel=np.r_[0.,[r[u] for r in rows]];force=np.r_[0.,[r[f] for r in rows]]
            w+=float(np.sum(.5*(force[1:]+force[:-1])*np.diff(travel)))
        work[name]=w
    def state(i):
        r=rows[i]
        return dict(time=r['time'],cell_xyz_mm=[r['cell_u_mm_'+a] for a in 'xyz'],cell_fx_N=r['cell_fx_N'],
                    top_travel_mm=r['screw1_u_mm_z'],individual_top_Fz_N=[r[f'screw{j}_force_N_z'] for j in range(1,5)],
                    max_nickel_plastic_strain=float(h['max_eppl'][i]),max_PLA_centroid_von_Mises_MPa=float(solid['seqv_MPa'][i]),
                    PLA_extreme_centroid_principal_elastic_strains=[float(solid['e3_min'][i]),float(solid['e1_max'][i])])
    seated=np.flatnonzero(np.isclose(times,seat,rtol=0,atol=1e-9))
    # Distinguish complete loading from acceptable contact resolution. A coarse shell-contact
    # penetration (>10% of thickness) or PLA/rigid penetration >0.05 mm requires a refined retry.
    limits={861:.05,862:.05,863:.015,864:.015}
    if face_seats:limits.update({pid:.05 for pid in range(880,884)})
    unresolved=[pid for pid,val in checks['peak_closed_corner_penetration_mm'].items() if val>limits[pid]]
    if len(seated) and not any(r['closed'] for r in pairs if r['native_set']==sets[seated[0]] and r['pair'] in (861,862,863,864)):
        raise ValueError('Reached nominal flush position without contacting any cell, strip or washer')
    reached=bool(len(seated) and abs(times[-1]-end)<1e-9 and status['native_clean'])
    # A 3 mm prescribed screw-head travel need not produce flush PLA tabs. With no explicit
    # contact to the PCB face in this local model, reject substantial crossing or all-open feet.
    seat_screen_mm=.05
    tab_review=[]
    for row in tab_history:
        for i,p in enumerate(row['tabs'],1):
            if p['min_mm'] < -seat_screen_mm:tab_review.append('datum crossing: tab '+str(i))
            if row['time']>=seat-1e-9 and p['min_mm']>seat_screen_mm:tab_review.append('no near-bearing point: tab '+str(i))
    if face_seats and len(seated):
        stopped_at=sets[seated[0]]
        for p in pairs:
            if p['native_set']==stopped_at and p['pair']>=880 and not p['closed']:
                tab_review.append(f"open bearing pair {p['pair']} at final drawdown")
    out=dict(case=case,campaign=campaign,states=len(rows),full_requested_path=reached,
        installed_tab_gaps_mm=tab_history[seated[0]]['tabs'] if len(seated) else None,
        tab_plane_review=sorted(set(tab_review)),tab_plane_review_screen_mm=seat_screen_mm,
        tab_plane_scope='Deformed near-hole PLA sample clearance versus a rigid board datum; not a PCB contact pressure or screw preload.',
        installed_state=state(seated[0]) if len(seated) else None,last_converged_state=state(-1),
        force_residual_peak_N=float(np.linalg.norm(ff,axis=1).max()),moment_residual_peak_Nmm=float(np.linalg.norm(mm,axis=1).max()),
        integrated_external_work_Nmm=work,contact_resolution_limits_mm=limits,contact_resolution_flagged_pairs=unresolved,
        peak_abs_total_drawdown_force_N=max(abs(r['screw_support_N_z']) for r in rows),**checks,
        rst_sha256=next(r['sha256'] for r in ledger['files'] if r['name']==rst.name),
        scope='Local fixture only; linear printed PLA and surrogate screw beams, fixed neighbors. A forced seat is not a demonstrated assembly.')
    category='local' if reached and not unresolved and not tab_review else ('review_local' if reached else 'partial_local')
    if damage:
        from nickel_damage import summarize
        out.update(summarize(inv,rows))
        if np.any(inv['loadstep'] >= (2 if grip else 4)):
            from damage_footprint import run as damage_maps
            from film_identity import digest as file_sha
            out['damage_footprint_sha256']=file_sha(damage_maps(case,campaign))
        if out['nickel_material_scope_exceeded'] and category=='local':
            category='review_local'
    if spec.get('bearing_pilots'):
        from rocking_bearing import audit_joint
        from film_identity import digest as file_digest
        out['joint_check_sha256']=file_digest(audit_joint(case,campaign))
    out['classification']=category
    pub=ROOT/'validation'/category;pub.mkdir(exist_ok=True)
    from film_identity import write_json
    if spec.get('bearing_pilots') or damage:
        from installation_material import run as audit_material
        draft=dest/'fixture_verdict.json'
        write_json(draft,out)
        audit_material(case,campaign,verdict_path=draft)
        if damage and np.any(inv['loadstep']>=4):
            audit_material(case,campaign,pull=True,verdict_path=draft)
    write_json(pub/(case+'.json'),out)
    print(category,case,len(rows),'native equilibria')


if __name__=='__main__':audit(*sys.argv[1:])
