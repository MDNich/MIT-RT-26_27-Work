"""Read native PSD sets and stored equivalent-stress RMS at solid integration-result nodes."""
import argparse,json
from pathlib import Path
import numpy as np
from native_rst import read_rst

def recover(path):
    rst=read_rst(str(path))
    ls=rst._resultheader['ls_table']
    assert np.count_nonzero((ls[:,0]==3)&(ls[:,1]==1))==1
    assert np.count_nonzero((ls[:,0]==5)&(ls[:,1]==1))==1
    g=rst.grid
    cellmat=g.cell_data['ansys_material_type']
    solid=np.isin(g.cell_data['ansys_elem_type_num'],[185,186,187])
    scopes={'assembly':solid,'pcb':solid&(cellmat==208),'cells':solid&np.isin(cellmat,[176,187,191]),
            'nickel':solid&np.isin(cellmat,[174,179,180,186,189,193]),'pla':solid&(cellmat==850)}
    scopes={k:m for k,m in scopes.items() if m.any()}
    en=g.cell_data['ansys_elem_num']
    scope_mat={k:set(map(int,en[m])) for k,m in scopes.items()}
    node_ids,disp=rst.nodal_solution([3,1])
    ai,acc=rst.nodal_solution([5,1]);assert np.array_equal(ai,node_ids)
    ssort=np.argsort(node_ids)
    def result_rows(selected):
        idx=np.searchsorted(node_ids[ssort],selected)
        ix=ssort[idx]
        assert np.array_equal(node_ids[ix],selected)
        return ix
    results={}
    for scope,mask in scopes.items():
        pts=g.extract_cells(mask).point_data['ansys_node_num']
        idx=result_rows(pts)
        u=np.abs(disp[idx,:3]);a=np.abs(acc[idx,:3]);assert np.all(np.isfinite(u)) and np.all(np.isfinite(a))
        results[scope]={'directional_rms_u_mm':list(1000*np.max(u,axis=0)),
                        'absolute_acceleration_rms_g':list(np.max(a,axis=0)/9.806),
                        'nodes':len(pts),'equivalent_stress_rms_Pa':0.0}
    enum,raw,nodes=rst.element_solution_data([3,1],'ENS')
    read=0
    for n,values,ids in zip(enum,raw,nodes):
        if int(n) not in scope_mat['assembly']:continue
        if values is None or len(ids)==0:continue
        # The last of eleven stored ENS quantities is the solver's combined equivalent RMS.
        if len(values)!=11*len(ids):raise ValueError(f'Unexpected ENS record length on solid {n}')
        vm=values.reshape(-1,11)[:,10];assert np.all(np.isfinite(vm))
        i=int(np.argmax(vm));val=float(vm[i]);read+=1
        for scope,elems in scope_mat.items():
            if n in elems and val>results[scope]['equivalent_stress_rms_Pa']:
                results[scope].update(equivalent_stress_rms_Pa=val,stress_element=int(n),stress_node=int(ids[i]))
    assert read==len(scope_mat['assembly'])
    return dict(sets=len(ls),displacement_load_step=3,acceleration_load_step=5,solid_elements_read=read,scopes=results)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('rst',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();a.output.parent.mkdir(exist_ok=True,parents=True)
    a.output.write_text(json.dumps(recover(a.rst),indent=2)+'\n')
