"""Read converged tab installation states on a historical unpreloaded default-contact mesh."""
import re
import sys

import numpy as np

from audit_local import ROOT, read, table
from film_identity import verified, write_json
from global_contact import history
from native_rst import read_rst


def audit(case,campaign):
    rt=ROOT/'.runtime'
    folder=rt/'archive'/campaign/case
    receipts=rt/'receipts'/campaign/case
    assert (receipts/'released.txt').is_file()
    archive=read(receipts/'archived.json');status=read(receipts/'status.json')
    spec=read(ROOT/'validation/default_contact_jobs.json')[case]
    assert spec['kind']=='static' and spec['parent'] is None
    assert archive['case']==status['case']==spec['case']==case and archive['campaign']==campaign
    assert status['phase']=='solver_complete' and not status.get('parent')
    files={v['name']:v['sha256'] for v in archive['files']}
    for name in ('model.inp','surface_job.json','board_surface_post.inp','board_surface_post.out',
                 'file.rst','solve.out','seat_contacts.csv','seat_material.csv','board_drives.csv'):
        verified(folder/name,files[name])
    assert files['model.inp']==spec['model_sha256']==status['input_sha256'].lower()
    assert files['board_surface_post.inp']==spec['post_sha256'] and files['surface_job.json']==spec['spec_sha256']
    post=(folder/'board_surface_post.out').read_text(errors='replace')
    assert 'BOARD_FACE_POST_FINISHED' in post and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',post)
    listing=(folder/'solve.out').read_text(errors='replace')
    completed=[(int(i),int(j)) for i,j in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',listing)]
    rst=read_rst(folder/'file.rst');ls=rst._resultheader['ls_table'][:,:2]
    indices=np.flatnonzero(ls[:,1]!=999999);sets=indices+1;times=rst.time_values[indices]
    assert len(sets)>0 and np.array_equal(ls[indices],completed) and np.all(np.diff(times)>0)
    assert completed[0]==(1,1) and all(i in (1,2) for i,j in completed)
    d=table(folder/'board_drives.csv');c=table(folder/'seat_contacts.csv');m=table(folder/'seat_material.csv')
    for rows,count in ((d,4),(c,5),(m,1)):
        assert np.array_equal(rows['set'],np.repeat(sets,count))
        assert np.allclose(rows['time_s'],np.repeat(times,count),atol=1e-8,rtol=0)
    assert np.array_equal(d['foot'],np.tile(np.arange(4),len(sets)))
    assert np.allclose(d['travel_m'],.003*np.clip(d['time_s']-1.,0.,1.),rtol=0,atol=1e-8)
    assert np.allclose(d['head_z_m']-d['board_z_m'],d['travel_m'],rtol=0,atol=1e-8)
    assert np.all(m['pla_elements']==np.count_nonzero(rst.grid.cell_data['ansys_etype']==850))
    complete=bool(status['native_clean'] and abs(times[-1]-2.)<1e-8)
    contacts={};flags=[]
    for pair in (853,880,881,882,883):
        h=history(rst,853 if pair==853 else 858,pair,indices)
        rows=c[c['pair']==pair]
        for p,v in zip(rows,h,strict=True):
            assert p['set']==v['set'] and p['faces']==v['n_contact'] and (p['p_max_Pa']>0)==(v['p_max']>0)
            bins=[int(p[k]) for k in ('far','near','sliding','sticking')]
            assert bins in (v['fully_uniform_face_bins'],[v[k] for k in ('far','near','sliding','sticking')])
        assert not (h[0]['sliding'] or h[0]['sticking'])
        pen=1000*max(x['loaded_corner_pen_max'] for x in h)
        if pen>(.015 if pair==853 else .05):flags.append(f'Loaded penetration on pair {pair}')
        if complete and not (h[-1]['sliding'] or h[-1]['sticking']):flags.append(f'Open final pair {pair}')
        contacts[str(pair)]=dict(final=h[-1],peak_penetration_mm=pen)
    issue=re.findall(r'(?im)^.*(?:small equation solver pivot|unconstrained rigid body|near.zero pivot|singular matrix).*$',
                     listing)
    if issue:flags.append('Review solver pivot or rigid body warnings')
    rec=dict(case=case,campaign=campaign,default_mesh=spec['mesh'],rst_sha256=files['file.rst'],
             converged_states=len(sets),complete_drawdown=complete,final_time=float(times[-1]),
             four_tab_travels_mm=(1000*d['travel_m'][-4:]).tolist(),four_drive_N=d['drive_N'][-4:].tolist(),
             contact=contacts,principal_PLA_strain_range=[float(m['e3min'].min()),float(m['e1max'].max())],
             numerical_flags=flags,solver_warning_examples=list(dict.fromkeys(i.strip() for i in issue))[:4],
             scope='Unpreloaded October default-contact assembly plus four driven case tabs. Eligible saved states only. Check local drift of the historically disconnected bodies, material response and all four seats before releasing modal films.')
    write_json(ROOT/'validation/review_global'/f'{case}.json',rec)
    print(case,len(sets),'converged states; reached full seat:',complete)


if __name__=='__main__':audit(*sys.argv[1:])
