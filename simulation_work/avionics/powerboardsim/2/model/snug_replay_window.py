"""Choose a short base-Z history from rest and check actual curved pockets at matched startup samples."""
import argparse
import numpy as np

from audit_local import ROOT,read
from early_cell_clearance import outer_faces
from film_identity import digest,verified,write_json
from seeded_motion import FRAMES,FS,integrate,participation
from snug_seeded_contact import geometry
from snug_locked_contact import sampled_gaps
from curved_cell_contact import set_coordinates
from stage_snug_fit import AUDIT


def run(variant,campaign):
    proof,rst,_,parts,targets,ids,xyz,_,shapes=geometry(variant,campaign)
    limit=round(.10*FS)
    log=ROOT/'.runtime/archive'/campaign/(variant+'_basis')/'solve.out'
    source=read(ROOT/'validation/independent_motion'/(variant+'_motion_Z.json'))
    assert source['basis_rst_sha256']==proof['rst_sha256']
    verified(log,source['modal_listing_sha256'])
    gamma=participation(log.read_text(errors='replace'),'Z')
    samples=np.arange(limit+1);times,q,_=integrate(rst.time_values,gamma,'Z',samples)
    locator=AUDIT/'snug125_nylon_seeded_contact.json'
    selected=read(locator)['axes']['Z']['samples'][0]
    point=next(r for r in selected['gaps'] if r['body']==4 and r['subdivision']==3)
    assert point['intersects'] and selected['frame_one_based']==353
    if variant=='snug125_nylon':
        hot=np.array(point['target_vertex_xyz_mm'])*.001
        _,previous,_=integrate(rst.time_values,gamma,'Z',np.array([FRAMES[352]]))
        deformed=xyz+(previous[0]@shapes).reshape(-1,3)
        nodes=[]
        for material in (176,850):
            surf_ids=np.unique(outer_faces(rst,[material]))
            # Only the exposed surface nodes used by the registered contact geometry are eligible.
            candidates=np.intersect1d(ids,surf_ids)
            ix=np.searchsorted(ids,candidates)
            d=np.linalg.norm(deformed[ix]-hot,axis=1)
            i=ix[d.argmin()]
            nodes.append(dict(node=int(ids[i]),material=material,offset_from_selected_point_mm=float(d.min()*1000)))
        centre=read(ROOT/'validation/cell_force'/(variant+'.json'))['geometry']['176']['centroid_mm']
        normal=1000*hot-np.asarray(centre);normal[1]=0;normal/=np.linalg.norm(normal)
        i,j=np.searchsorted(ids,[n['node'] for n in nodes])
        assert max(n['offset_from_selected_point_mm'] for n in nodes)<2.5
        projector=(shapes.reshape(rst.nsets,-1,3)[:,i]-shapes.reshape(rst.nsets,-1,3)[:,j])@normal
        relative=q@projector
        candidates=sorted({int(relative.argmin()),int(relative.argmax())})
        assert len(candidates)==2 and 0<candidates[0]<candidates[1]
        choice=dict(nodes=nodes,outward_radial_axis=normal.tolist(),samples=candidates,
                    relative_displacement_mm=[float(1000*relative[i]) for i in candidates])
    else:
        nylon=read(AUDIT/'snug125_nylon_replay_window.json')
        choice=nylon['choice'];candidates=choice['samples']
        assert nylon['source_film_audit_sha256']==digest(locator) and nylon['campaign']==campaign
    states=[]
    for sample in candidates:
        set_coordinates(parts,ids,xyz+(q[sample]@shapes).reshape(-1,3))
        rows=sampled_gaps(parts,targets,include_locations=True)
        states.append(dict(sample=sample,time_s=float(times[sample]),gaps=rows))
    horizon=4*int(np.ceil((max(candidates)+2*FS/rst.time_values[0])/4))
    if variant!='snug125_nylon':horizon=max(horizon,nylon['replay_last_sample'])
    write_json(AUDIT/(variant+'_replay_window.json'),dict(variant=variant,campaign=campaign,
        basis_sha256=proof['rst_sha256'],source_film_audit_sha256=digest(locator),choice=choice,
        states=states,replay_last_sample=horizon,sample_rate_Hz=FS,
        scope='The nylon outer-pocket relative nodal motion selects two instants in the first 0.10 s. '
              'All cell and washer surfaces are then evaluated independently at both instants. '
              'The tracked nodes index the waveform and do not define an exact geometric gap or first-impact time.'))
    print(variant,[(s['time_s'],[r['body'] for r in s['gaps'] if r['subdivision']==3 and r['intersects']]) for s in states],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=('snug125_nylon','snug125_aluminium'))
    p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();run(a.variant,a.campaign)
