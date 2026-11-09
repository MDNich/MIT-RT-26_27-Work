"""Recover only verified converged states when the nonlinear whole-board installation stops early."""
import re,sys
import numpy as np
from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from native_rst import read_rst
from prepare_board_install import support_post
from stage_local_jobs import seal

def stage():
    rt=ROOT/'.runtime'
    native=read(ROOT/'validation/board_surface_jobs.json')
    parent=read(ROOT/'validation/global/bare_static.json')
    backup=rt/'archive'/parent['campaign']/parent['case']
    bolts=table(backup/'bolt_preload_audit.csv')[:6]
    assert np.array_equal(bolts['bolt'],np.arange(1,7)) and len(set(bolts['pilot']))==6
    output={}
    for case,spec in native.items():
        if spec['kind']!='static':continue
        folder=rt/'inputs'/case
        post=(folder/'board_surface_post.inp').read_text()
        assert digest(folder/'board_surface_post.inp')==spec['post_sha256']
        row=' set,,,,,,,ii\n'
        assert post.count(row)==2
        post=post.replace(row,row+' *get,lsb,active,0,set,sbst\n *if,lsb,eq,999999,then\n *cycle\n *endif\n')
        prefix,final=post.split('/com,BOARD_FACE_POST_FINISHED',1)
        lines=['*cfopen,partial_bolts,csv','*vwrite',"('set,step,time_s,bolt,pilot,adjustment_m,reaction_N')",
               '*do,ii,1,nsav','set,,,,,,,ii','*get,sb,active,0,set,sbst','*if,sb,eq,999999,then','*cycle','*endif',
               '*get,ls,active,0,set,lstp','*get,t,active,0,set,time']
        for b in bolts:
            n=int(b['pilot']);j=int(b['bolt'])
            lines += [f'*get,u,node,{n},u,x',f'*get,f,node,{n},rf,fx',
                      f'*vwrite,ii,ls,t,{j},{n},u,f',"(F6.0,',',F3.0,',',E16.9,',',F3.0,',',F10.0,2(',',E16.9))"]
        post=prefix+'\n'+'\n'.join(lines+['*enddo','*cfclos','allsel,all'])+'\n'
        post+=support_post().decode().replace('\r\n','\n')+'/com,PARTIAL_FACE_POST_FINISHED'+final
        dest=rt/'surface_partial_readbacks'/case;dest.mkdir(exist_ok=True,parents=True)
        output[case]=dict(input_sha256=seal(dest/'partial_post.inp',post.encode()),
                          original_model_sha256=spec['model_sha256'],original_post_sha256=spec['post_sha256'])
    write_json(ROOT/'validation/partial_board_readbacks.json',output)

def audit(case,campaign):
    rt=ROOT/'.runtime';d=rt/'archive'/campaign/case;receipt=rt/'receipts'/campaign/case
    status=read(receipt/'status.json');meta=read(receipt/'archived.json')
    spec=read(ROOT/'validation/partial_board_readbacks.json')[case]
    assert status['phase']=='solver_complete' and status['native_clean'] is False and meta['case']==case and meta['campaign']==campaign
    sha={row['name']:row['sha256'] for row in meta['files']}
    assert sha['model.inp']==spec['original_model_sha256'] and sha['partial_post.inp']==spec['input_sha256']
    for name in ('model.inp','partial_post.inp','file.rst','solve.out','partial_post.out','board_drives.csv',
                 'partial_bolts.csv','seat_contacts.csv','seat_material.csv'):
        verified(d/name,sha[name])
    out=(d/'partial_post.out').read_text(errors='replace')
    assert 'PARTIAL_FACE_POST_FINISHED' in out and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',out)
    raw=read_rst(d/'file.rst');ls=raw._resultheader['ls_table'][:,:2]
    indices=np.flatnonzero(ls[:,1]!=999999);sets=indices+1;t=raw.time_values[indices]
    log=(d/'solve.out').read_text(errors='replace')
    done=[(int(s),int(k)) for s,k in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',log)]
    assert len(sets) and np.array_equal(ls[indices],done) and np.all(np.diff(t)>0)
    drives=table(d/'board_drives.csv');bolts=table(d/'partial_bolts.csv');contacts=table(d/'seat_contacts.csv');material=table(d/'seat_material.csv')
    for rows,nrows in [(drives,4),(bolts,6),(contacts,5),(material,1)]:
        assert np.array_equal(rows['set'],np.repeat(sets,nrows)) and np.allclose(rows['time_s'],np.repeat(t,nrows),atol=1e-8,rtol=0)
    assert np.allclose(drives['head_z_m']-drives['board_z_m'],drives['travel_m'],atol=1e-8,rtol=0)
    assert np.allclose(drives['travel_m'],.003*np.clip(drives['time_s']-2.,0.,1.),atol=1e-8,rtol=0)
    from global_contact import histories
    last={}
    pairs={853:853,880:858,881:858,882:858,883:858}
    for pair,h in histories(raw,pairs,indices).items():
        p=contacts[contacts['pair']==pair]
        for a,b in zip(p,h,strict=True):
            assert a['set']==b['set'] and a['faces']==b['n_contact']
            assert bool(a['p_max_Pa']>0)==bool(b['p_max']>0)
        last[str(pair)]=h[-1]
    rec=dict(case=case,campaign=campaign,classification='Partial installation',rst_sha256=sha['file.rst'],
        equilibria=len(sets),last_converged_time=float(t[-1]),last_completed_step=int(ls[indices[-1],0]),
        screw_travel_mm=(1000*drives['travel_m'][-4:]).tolist(),drive_reactions_N=drives['drive_N'][-4:].tolist(),
        contact_at_last_equilibrium=last,bolt_reactions_N=bolts['reaction_N'][-6:].tolist(),
        maximum_principal_PLA_tension_MPa=float(material['s1max_Pa'].max()*1e-6),
        scope='Verified saved equilibria before numerical termination. A full installed state and modal restart remain pending.')
    write_json(ROOT/'validation/review_global'/f'{case}.json',rec)
    print(case,len(sets),'converged partial equilibria')
if __name__=='__main__':
    if len(sys.argv)==1:stage()
    else:audit(*sys.argv[1:])
