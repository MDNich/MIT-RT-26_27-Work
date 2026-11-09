"""Locate the six pretension sections and compare retained bolt force to the load after locking."""
import argparse

import numpy as np
from scipy.spatial.distance import cdist

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from native_rst import read_rst


def run(case,campaign):
    receipt=ROOT/'.runtime/receipts'/campaign/case
    assert (receipt/'released.txt').is_file()
    vault=ROOT/'.runtime/archive'/campaign/case
    hashes={v['name']:v['sha256'] for v in read(receipt/'archived.json')['files']}
    for name in ('file.rst','partial_bolts.csv','board_drives.csv'):
        verified(vault/name,hashes[name])
    csv=table(vault/'partial_bolts.csv');drives=table(vault/'board_drives.csv')
    rst=read_rst(vault/'file.rst')
    g=rst.grid.cell_data
    elements=g['ansys_elem_num'][g['ansys_elem_type_num']==179]
    order=np.argsort(rst.mesh.enum);raw=rst.mesh.elem
    ix=order[np.searchsorted(rst.mesh.enum[order],elements)]
    assert np.array_equal(rst.mesh.enum[ix],elements)
    connect=np.stack([raw[j][10:] for j in ix])
    assert connect.shape==(len(elements),3)
    def xyz(ids):
        idx=np.searchsorted(rst.mesh.nnum,ids);assert np.array_equal(rst.mesh.nnum[idx],ids)
        return rst.mesh.nodes[idx]*1000
    cad_path=ROOT/'validation/rigid_case_drawdown.json'
    hardware=read(cad_path)
    records=[r for r in hardware['records'] if r['native_material'] in (173,178,181,182,183,192)]
    centers=np.array([r['STEP_centre_mm'][:2] for r in records])
    pilots=[]
    description={}
    for j in range(1,7):
        pi=np.unique(csv[csv['bolt']==j]['pilot'].astype(int))
        assert len(pi)==1
        pilot=pi.item();pilots.append(pilot)
        nodes=connect[connect[:,2]==pilot,:2]
        assert len(nodes)>10 and np.allclose(xyz(nodes[:,0]),xyz(nodes[:,1]),atol=1e-4)
        section=xyz(nodes[:,0])
        ctr=(section[:,:2].max(0)+section[:,:2].min(0))*.5
        distance=cdist(ctr[None],centers)[0];i=distance.argmin()
        radius=np.linalg.norm(section[:,:2]-ctr,axis=1).max()
        assert distance[i]<radius and np.partition(distance,1)[1]>2*radius
        washer=records[i]
        description[j]=dict(pilot=pilot,pretension_section_center_xy_mm=ctr.tolist(),
            section_z_extent_mm=[float(section[:,2].min()),float(section[:,2].max())],cut_node_pairs=len(nodes),
            washer_STEP_body=washer['STEP_body'],washer_native_material=washer['native_material'],
            axis_to_washer_center_xy_mm=float(distance[i]))
    assert len(set(v['washer_native_material'] for v in description.values()))==6
    states=rst._resultheader['ls_table']
    sets=np.flatnonzero(states[:,1]!=999999)+1
    lock=int(sets[states[sets-1,0]==2][-1])
    locked=csv[csv['set']==lock]
    assert np.array_equal(locked['bolt'],range(1,7)) and np.max(abs(locked['reaction_N']-750))<1
    check=ROOT/'validation/partition_checks'/case/'step3_substep20_history.json'
    independent=read(check)['history']
    entries=[];largest_error=0.
    for k in sets:
        z=csv[csv['set']==k];u=drives[drives['set']==k]
        assert np.array_equal(z['pilot'],pilots) and np.array_equal(u['foot'],range(4))
        f,n,d=rst.nodal_reaction_forces(int(k-1))
        values=np.array([f[(n==pi)&(d==1)].sum() for pi in pilots])
        err=float(np.max(abs(values-z['reaction_N'])))
        assert err<1e-5 and np.allclose(values,independent[k-1]['bolt_N'],atol=1e-8,rtol=0)
        largest_error=max(largest_error,err)
        if k>=lock:
            assert np.max(abs(z['adjustment_m']-locked['adjustment_m']))<1e-9
            entries.append(dict(native_set=int(k),travel_mm=float(u['travel_m'].mean()*1000),force_N=values.tolist(),
                      change_from_locked_N=(values-locked['reaction_N']).tolist()))
    o=ROOT/'validation/installed_bolt_loads'/(case+'.json')
    write_json(o,dict(case=case,campaign=campaign,combined_rst_sha256=hashes['file.rst'],
              POST1_bolt_table_sha256=hashes['partial_bolts.csv'],partition_history_sha256=digest(check),
              STEP_mapping_sha256=digest(cad_path),max_force_POST1_difference_N=largest_error,locations=description,
              locked_set=lock,states=entries,scope='Axial reactions on the original locked battery bolts. These '
              'reactions track clamp preload; they are separate from the four case-screw drive reactions.'))
    for j,v in description.items():
        print(j,v['washer_native_material'],v['pretension_section_center_xy_mm'],
              entries[-1]['change_from_locked_N'][j-1])
    return o


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case');p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();run(a.case,a.campaign)
