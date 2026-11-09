"""Review the complete three-stage fitted assembly. Numerical completion alone never releases a modal restart."""
import re,sys
import numpy as np
from audit_local import ROOT,table,read
from film_identity import verified,write_json,digest
from native_rst import read_rst
from global_contact import histories

def audit(case,campaign):
    assert re.fullmatch(r'flush_(nylon|aluminium)_surf1_static',case)
    rt=ROOT/'.runtime';d=rt/'archive'/campaign/case;r=rt/'receipts'/campaign/case
    assert (r/'released.txt').exists()
    if read(r/'status.json').get('native_clean') is False:
        from partial_board import audit as audit_partial
        audit_partial(case,campaign)
    else:
        audit_complete(case,campaign,d,r)
    from installed_tab_gap import run as audit_gaps
    from board_reactions import run as audit_supports
    audit_gaps(case,campaign,[])
    audit_supports(case,campaign)
    from installation_material import run as audit_material
    audit_material(case,campaign)
    from reconcile_installation import reconcile
    reconcile(case,campaign)

def audit_complete(case,campaign,d,r):
    ledger=read(r/'archived.json');status=read(r/'status.json');job=read(d/'surface_job.json')
    pub=read(ROOT/'validation/board_surface_jobs.json')[case]
    assert case==ledger['case']==job['case']==status['case'] and ledger['campaign']==campaign and status['phase']=='solver_complete' and status['exit']==0
    files={e['name']:e['sha256'] for e in ledger['files']}
    names='model.inp surface_job.json board_surface_post.inp file.rst board_surface_post.out bolt_preload_audit.csv seat_contacts.csv seat_material.csv board_drives.csv solve.out'.split()
    for n in names:verified(d/n,files[n])
    assert files['surface_job.json']==pub['spec_sha256'] and files['model.inp']==pub['model_sha256']==status['input_sha256'].lower()
    assert files['board_surface_post.inp']==pub['post_sha256']
    post=(d/'board_surface_post.out').read_text(errors='replace')
    log=(d/'solve.out').read_text(errors='replace')
    assert 'BOARD_FACE_POST_FINISHED' in post and all(re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',s) for s in (post,log))
    rst=read_rst(d/'file.rst');times=rst.time_values
    ls=rst._resultheader['ls_table'][:,:2]
    done=[(int(a),int(b)) for a,b in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',log)]
    assert np.array_equal(ls,done) and np.array_equal(np.unique(ls[:,0]),[1,2,3]) and np.all(np.diff(times)>0) and abs(times[-1]-3)<1e-8
    g=rst.grid.cell_data; pla=int(np.count_nonzero(g['ansys_etype']==850));assert pla>1000
    a=table(d/'board_drives.csv');b=table(d/'bolt_preload_audit.csv');c=table(d/'seat_contacts.csv');m=table(d/'seat_material.csv')
    assert len(a)==4*len(times) and len(c)==5*len(times) and len(b)==18
    assert np.array_equal(m['set'],np.arange(1,len(times)+1)) and np.allclose(m['time_s'],times,atol=1e-8,rtol=0) and np.all(m['pla_elements']==pla)
    assert max(m['s1max_Pa'])>0 and min(m['s3min_Pa'])<0 and max(m['e1max'])>0 and min(m['e3min'])<0
    bolts=[]
    for j in range(1,7):
        y=b[b['bolt']==j];assert np.array_equal(y['step'],[1,2,3]) and abs(y[1]['reaction_N']-750)<1.
        assert abs(y[1]['adjustment_m']-y[2]['adjustment_m'])<1e-8
        bolts.append(float(y[2]['reaction_N']))
    drives=[];flag=[]
    for i in range(4):
        z=a[a['foot']==i]
        assert np.array_equal(z['set'],np.arange(1,len(times)+1)) and np.allclose(z['time_s'],times,atol=1e-8,rtol=0)
        cmd=.003*np.clip(times-2,0,1)
        assert np.max(abs(z['travel_m']-cmd))<1e-8 and np.max(abs(z['head_z_m']-z['board_z_m']-cmd))<1e-8
        drives.append(dict(foot=i+1,final_drive_N=float(z['drive_N'][-1]),peak_abs_drive_N=max(abs(z['drive_N'])),
                           signed_actuator_work_J=float(np.trapezoid(z['drive_N'],z['travel_m']))))
    evidence={}
    pairs={853:853,880:858,881:858,882:858,883:858}
    for k,hist in histories(rst,pairs).items():
        p=c[c['pair']==k]
        assert len(hist)==len(p)==len(times)
        for z,h in zip(p,hist,strict=True):
            assert int(z['set'])==h['set'] and abs(z['time_s']-h['time_s'])<1e-8 and int(z['faces'])==h['n_contact']
            bins=[int(z[x]) for x in ('far','near','sliding','sticking')]
            assert bins in ([h[x] for x in ('far','near','sliding','sticking')],h['fully_uniform_face_bins'])
            assert bool(z['p_max_Pa']>0)==bool(h['p_max']>0)
        closed=[h for h in hist if h['sliding']+h['sticking']>0]
        if hist[-1]['sliding']+hist[-1]['sticking']==0:flag.append(f'pair {k}: no compressed face at final travel')
        if not closed:flag.append(f'pair {k}: never closed')
        pen=max(h['loaded_corner_pen_max'] for h in hist)*1000
        lim=.015 if k==853 else .05
        if pen>lim:flag.append(f'pair {k}: loaded penetration above {lim:g} mm screen')
        evidence[str(k)]=dict(first_closed_time=None if not closed else closed[0]['time_s'],peak_loaded_penetration_mm=pen,
                              final=hist[-1],history=hist)
    rec=dict(case=case,campaign=campaign,states=len(times),rst_sha256=files['file.rst'],controls=job['controls'],
             actuators=drives,clamp_forces_after_seating_N=bolts,contact=evidence,numerical_flags=flag,
             PLA_principal_stress_extrema_MPa=[min(m['s3min_Pa'])/1e6,max(m['s1max_Pa'])/1e6],
             PLA_principal_elastic_strain_extrema=[min(m['e3min']),max(m['e1max'])],
             classification='Completed numerical installation, engineering review required. Check contact location, PLA material scope, fastener force and restart before releasing vibration.')
    write_json(ROOT/'validation/review_global'/f'{case}.json',rec)
    print(case,len(times),'equilibria,',len(flag),'screen flags; no automatic modal release')
if __name__=='__main__':audit(*sys.argv[1:])
