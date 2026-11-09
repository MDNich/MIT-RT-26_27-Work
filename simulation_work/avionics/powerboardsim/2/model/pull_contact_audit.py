"""Separate penetrations on closed corners from near-field values on unloaded facets."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from ansys.mapdl import reader
from audit_local import read,table,ROOT


def verify(case):
    proof=read(ROOT/f'validation/local/{case}.json');camp=proof['campaign']
    archive=ROOT/f'.runtime/archive/{camp}/{case}'
    assert proof['full_requested_path']
    raw=reader.read_binary(str(archive/'pull.rst'));grid=raw.grid
    pairs=table(archive/'case_pairs.csv')
    balance=table(ROOT/f'.runtime/post/{camp}/{case}/whole_fixture_balance.csv')
    rows=[]
    for kk,br in enumerate(balance):
        k=int(br['native_set'])
        enum,nmisc,_=raw.element_solution_data(k-1,'EMN')
        for rid in (861,862):
            mask=(grid.cell_data['ansys_etype']==862)&(grid.cell_data['ansys_real_constant']==rid)
            elements=grid.cell_data['ansys_elem_num'][mask]
            idx=np.searchsorted(enum,elements)
            assert np.array_equal(enum[idx],elements)
            # Far-field elements with no saved record have no compressive contact force.
            items=[nmisc[i] for i in idx if nmisc[i] is not None and len(nmisc[i])]
            if not items:raise ValueError('Missing all contact records for a pair')
            a=np.stack(items);assert a.shape[1]>=45
            closed=a[:,40]>=2
            loaded=(a[:,:4]>=2)&closed[:,None]
            row=pairs[(pairs['set']==k)&(pairs['pair']==rid)]
            assert len(row)==1 and int(closed.sum())==row['closed'][0]
            force=a[:,42:45].sum(axis=0,dtype=float)
            assert np.allclose(force,[row['fx_N'][0],row['fy_N'][0],row['fz_N'][0]],rtol=2e-6,atol=1e-5)
            residual=None
            if rid==861:
                supports=np.array([br['screw_support_N_'+k]+br['neighbor_support_N_'+k] for k in 'xyz'])
                residual=float(np.linalg.norm(force-supports))
                if residual>max(.01,.002*np.linalg.norm(force)):raise ValueError(('Contact vs case supports',k,residual))
            rows.append(dict(native_set=k,ux_mm=float(br['ux_mm']),pair=rid,closed_faces=int(closed.sum()),closed_corner_records=int(loaded.sum()),
                     max_closed_corner_penetration_mm=float(max(0,a[:,8:12][loaded].max(initial=0))),
                     max_all_corner_value_mm=float(max(0,a[:,8:12].max())),
                     active_pair_vs_case_support_residual_N=residual))
    out=ROOT/'validation/pulls';out.mkdir(exist_ok=True)
    active=[r for r in rows if r['pair']==861]
    final=dict(case=case,rst_sha256=proof['rst_sha256'],converged_states=len(active),
            max_closed_corner_penetration_mm=max(r['max_closed_corner_penetration_mm'] for r in rows),
            end_active_closed_corner_penetration_mm=active[-1]['max_closed_corner_penetration_mm'],
            max_unfiltered_corner_value_mm=max(r['max_all_corner_value_mm'] for r in rows),
            max_active_contact_vs_support_force_residual_N=max(r['active_pair_vs_case_support_residual_N'] for r in active))
    (out/(case+'_contact.json')).write_text(json.dumps(final,indent=2)+'\n')
    with (out/(case+'_contact.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    print(final)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case');verify(parser.parse_args().case)
