"""Compare the native locked contact geometry with six matched states in the seeded film interval."""
import argparse

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from curved_cell_contact import set_coordinates
from film_identity import digest, verified, write_json
from modal_correspondence import reference_geometry
from motion_surface import displacement_basis
from seeded_motion import FRAMES, FS, excitation
from snug_locked_contact import contact_parts, sampled_gaps
from stage_snug_fit import AUDIT


def run(variant, campaign):
    key = variant+'_basis'
    proof, _, rst = source(key,campaign)
    _, _, pose = reference_geometry(rst,include_case=True)
    locked = read(AUDIT/(pose['parent']+'_contacts.json'))
    assert locked['rst_sha256']==pose['parent_RST_sha256'] and locked['campaign']==campaign
    _, _, preload = source(pose['parent'],campaign)
    parts, targets = contact_parts(preload)
    ids = np.unique(np.concatenate([p.point_data['ansys_node_num'] for p in parts]))
    pos = np.searchsorted(rst.mesh.nnum,ids)
    assert np.array_equal(rst.mesh.nnum[pos],ids)
    xyz = rst.mesh.nodes[pos]
    set_coordinates(parts,ids,xyz)
    initial = sampled_gaps(parts,targets)
    previous = locked['locked_geometry']['rows']
    assert len(initial)==len(previous)
    for row, ref in zip(initial,previous,strict=True):
        assert all(row[k]==ref[k] for k in ('body','material','subdivision','intersects'))
        assert abs(row['minimum_signed_target_vertex_gap_mm']-ref['minimum_signed_target_vertex_gap_mm'])<1e-6

    fields = field_files(key,campaign,proof['rst_sha256'],rst.nsets)
    shapes = displacement_basis(rst,ids,fields).reshape(rst.nsets,-1)
    results = {}
    for axis in 'XYZ':
        name = variant+'_motion_'+axis
        record = read(ROOT/'validation/independent_motion'/(name+'.json'))
        assert record['coordinate_method']=='independent' and record['basis_rst_sha256']==proof['rst_sha256']
        assert record['campaign']==campaign
        clip = ROOT/'.runtime/post'/campaign/name/'independent/coordinates.npz'
        verified(clip,record['clip_sha256'])
        _, acceleration, _ = excitation(axis)
        load = ROOT/'.runtime/motion_loads'/(axis+'.txt')
        verified(load,record['input_sha256'])
        sealed = np.loadtxt(load,skiprows=1,max_rows=int(FRAMES[-1])+1)[FRAMES]
        assert np.allclose(sealed[:,0],FRAMES/FS,rtol=0,atol=5.1e-13)
        acceleration = acceleration[FRAMES]
        assert np.allclose(sealed[:,1],acceleration,rtol=1e-10,atol=1e-9)
        records = []
        with np.load(clip) as data:
            assert np.array_equal(data['time_s'],FRAMES/FS)
            assert np.array_equal(data['frequencies_Hz'],rst.time_values)
            for index in [int(acceleration.argmin()),int(acceleration.argmax())]:
                displacement = (data['coordinates'][index]@shapes).reshape(-1,3)
                set_coordinates(parts,ids,xyz+displacement)
                rows = sampled_gaps(parts,targets,include_locations=True)
                records.append(dict(frame_one_based=index+1,time_s=float(FRAMES[index]/FS),
                    acceleration_m_s2=float(acceleration[index]),gaps=rows))
        results[axis] = dict(clip_sha256=record['clip_sha256'],load_sha256=record['input_sha256'],samples=records)
        print(variant,axis,[(s['frame_one_based'],[r['body'] for r in s['gaps'] if r['subdivision']==3 and r['intersects']]) for s in records],flush=True)
    write_json(AUDIT/(variant+'_seeded_contact.json'),dict(variant=variant,campaign=campaign,
        native_basis_sha256=proof['rst_sha256'],static_contact_sha256=digest(AUDIT/(pose['parent']+'_contacts.json')),
        pose_check=pose,locked_geometry=initial,axes=results,
        scope='Independent linear modal histories use the native bolt-locked contact tangent. '
              'Both mounts use the frames of minimum and maximum input acceleration in each 480-frame film. '
              'At each instant the deformed quadratic case, three cells and six washers are checked at two '
              'spatial subdivisions. Changes relative to equilibrium flag contact states for nonlinear verification. '
              'The sampled states give neither extrema over the history nor contact forces.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=('snug125_nylon','snug125_aluminium'))
    parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args()
    run(args.variant,args.campaign)
