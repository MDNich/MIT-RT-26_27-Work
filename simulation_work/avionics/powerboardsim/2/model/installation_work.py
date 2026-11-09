"""Recover the four actuator work histories and incremental element energies during flush seating."""
import argparse

import numpy as np
from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from native_rst import read_rst


def run(case,campaign):
    assert case in ('flush_nylon_surf1_static','flush_aluminium_surf1_static')
    folder=ROOT/'.runtime/archive'/campaign/case
    receipt=ROOT/'.runtime/receipts'/campaign/case
    assert (receipt/'released.txt').is_file()
    proof=read(ROOT/'validation/review_global'/(case+'.json'))
    ledger=read(receipt/'archived.json')
    hashes={v['name']:v['sha256'] for v in ledger['files']}
    assert ledger['case']==proof['case']==case and ledger['campaign']==proof['campaign']==campaign
    assert hashes['file.rst']==proof['rst_sha256']
    for name in ['file.rst','board_drives.csv','model.inp']:verified(folder/name,hashes[name])
    r=read_rst(folder/'file.rst')
    g=r.grid.cell_data;et=g['ansys_elem_type_num'];mat=g['ansys_material_type'];type_id=g['ansys_etype']
    cat={'PLA':type_id==850,'case_screws':type_id==851,'PCB':mat==208,'contacts':np.isin(et,[170,174]),
         'other_original_solids':(type_id<850)&np.isin(et,[185,186,187])&(mat!=208)}
    kept=np.sum(list(cat.values()),axis=0);assert np.max(kept)==1
    cat['remaining_elements']=kept==0
    assert set(et[cat['remaining_elements']]) <= {21,179}
    assert set(et[cat['PCB']]) <= {185,186,187}
    ls=r._resultheader['ls_table'];valid=np.flatnonzero(ls[:,1]!=999999)
    if not np.any(ls[valid,0]==3):
        print(case,'ended before any seated-drive increment')
        return
    last_lock=valid[ls[valid,0]==2][-1]
    selected=valid[valid>=last_lock]
    native=table(folder/'board_drives.csv')
    blocks=[native[native['foot']==i] for i in range(4)]
    for z in blocks:assert np.array_equal(z['set'],valid+1)
    rows=np.searchsorted(valid,selected)
    x=np.stack([z['travel_m'][rows] for z in blocks],axis=1)
    f=np.stack([z['drive_N'][rows] for z in blocks],axis=1)
    relative=np.stack([(z['head_z_m']-z['board_z_m'])[rows] for z in blocks],axis=1)
    assert np.allclose(x,relative,rtol=0,atol=1e-9) and np.all(np.diff(x,axis=0)>0)
    def work(x,f):
        return 1000*np.vstack([np.zeros(4),np.cumsum(np.diff(x,axis=0)*.5*(f[:-1]+f[1:]),axis=0)])
    applied=work(x,f);records=[]
    comp=ROOT/'validation/partition_checks'/case
    interim_check=[]
    for h in sorted(comp.glob('*_history.json')):
        data=read(h)
        assert data['case']==case and data['campaign']==campaign
        matched=[v for v in data['history'] if v['native_set']>=last_lock+1]
        if len(matched)<2:continue
        jj=np.array([v['native_set'] for v in matched])-1
        q=np.searchsorted(selected,jj);assert np.array_equal(selected[q],jj)
        assert np.array_equal(q,np.arange(len(q)))
        independent=work(x[q],np.array([v['drive_N'] for v in matched]))
        err=float(abs(independent-applied[q]).max());assert err<1e-4
        interim_check.append(dict(checkpoint_sha256=digest(h),states=len(q),max_difference_mJ=err))
    ref=None
    for i,k in enumerate(selected):
        nums,fields,_=r.element_solution_data(int(k),'ENG')
        per_element=np.array([row[1] if row is not None and len(row) else 0. for row in fields])
        assert np.isfinite(per_element).all()
        part={}
        for key,mask in cat.items():
            ids=g['ansys_elem_num'][mask];idx=np.searchsorted(nums,ids)
            assert np.array_equal(nums[idx],ids)
            if key in ('PLA','case_screws','PCB','other_original_solids'):
                assert all(fields[j] is not None and len(fields[j])==11 for j in idx)
            part[key]=1000*float(per_element[idx].sum())
        assert np.isclose(sum(part.values()),1000*per_element.sum(),rtol=1e-11)
        if ref is None:ref=part
        delta={name:value-ref[name] for name,value in part.items()}
        kept=np.unique(np.r_[np.arange(0,i+1,2),i])
        coarse=float(work(x[kept],f[kept])[-1].sum())
        records.append(dict(native_set=int(k+1),travel_mm=float(1000*x[i].mean()),
               drive_work_mJ=float(applied[i].sum()),per_drive_work_mJ=applied[i].tolist(),
               alternate_saved_state_work_mJ=coarse,energy_change_mJ=delta,
               work_less_summed_stiffness_energy_mJ=float(applied[i].sum()-sum(delta.values()))))
    reference=ROOT/'validation/installation_material'/(case+'.json')
    limits=read(reference);assert limits['rst_sha256']==hashes['file.rst']
    output=dict(case=case,campaign=campaign,rst_sha256=hashes['file.rst'],drive_table_sha256=hashes['board_drives.csv'],
        material_check_sha256=digest(reference),first_layer_tension_crossing=limits['first_reference_crossings'].get('all_layer_tension_MPa'),
        reference_lock_set=int(last_lock+1),excluded_diagnostic_sets=int(len(ls)-len(valid)),history=records,
        partition_checks=interim_check,scope='Four-actuator work and native element stiffness-energy changes from six-bolt lock. '
        'The work difference can include contact effects and integration error. Contact stiffness energy is a numerical term.')
    write_json(ROOT/'validation/installation_work'/(case+'.json'),output)
    print(case,len(records),records[-1],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case');p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();run(a.case,a.campaign)
