"""Read the stored corner contact field (ECT) independently of POST1; global decks request CONT, not MISC."""
import json
import numpy as np
from ansys.mapdl import reader


def history(raw,etype,real):
    g=raw.grid.cell_data
    ids=g['ansys_elem_num'][(g['ansys_etype']==etype)&(g['ansys_real_constant']==real)]
    if len(ids)==0:raise ValueError('No contact elements in expected pair')
    out=[]
    for k,t in enumerate(raw.time_values):
        enum,data,nodes=raw.element_solution_data(k,'ECT');loc=np.searchsorted(enum,ids)
        assert np.array_equal(enum[loc],ids)
        groups=[];missing=0
        for i in loc:
            vals=data[i]
            if vals is None or not len(vals):missing+=1;continue
            count=len(nodes[i]);assert count in (3,4)
            if len(vals)==10*count+1:
                assert vals[-1] in (10.,32.), 'Unsupported ECT trailer'
                vals=vals[:-1]
            assert len(vals)==10*count
            groups.append(np.array(vals).reshape(count,10))
        st=[int(a[:,0].max()) for a in groups]
        assert all(np.isin(a[:,0],[0,1,2,3]).all() for a in groups)
        mixed=sum(np.min(a[:,0])!=np.max(a[:,0]) for a in groups)
        full=[int(a[0,0]) for a in groups if np.min(a[:,0])==np.max(a[:,0])]
        far=missing+st.count(0);near=st.count(1);sliding=st.count(2);sticking=st.count(3)
        assert far+near+sliding+sticking==len(ids)
        a=np.vstack(groups) if groups else np.empty((0,10))
        loaded=a[:,0]>=2
        gap=-a[a[:,0]==1,6]
        out.append(dict(set=k+1,time_s=float(t),n_contact=len(ids),far=far,near=near,sliding=sliding,sticking=sticking,
                        p_max=float(a[:,2].max(initial=0)),loaded_corner_pen_max=float(a[loaded,1].max(initial=0)),
                        missing_far_records=missing,mixed_corner_faces=int(mixed),fully_uniform_face_bins=[missing+full.count(0),full.count(1),full.count(2),full.count(3)],smallest_positive_open_gap=float(gap[gap>0].min()) if np.any(gap>0) else None))
    return out


def verify_local():
    from audit_local import ROOT,table,read
    case='stand3_nylon_lateral_friction_locked_pin1';proof=read(ROOT/'validation/local'/f'{case}.json')
    d=ROOT/'.runtime/archive'/proof['campaign']/case
    raw=reader.read_binary(str(d/'pull.rst'));tab=table(d/'case_pairs.csv')
    corner=np.genfromtxt(ROOT/'validation/pulls'/f'{case}_contact.csv',delimiter=',',names=True,usecols=('native_set','pair','max_closed_corner_penetration_mm'))
    checks={}
    for real in (861,862):
        rows=history(raw,862,real)
        t=tab[tab['pair']==real];c=corner[corner['pair']==real]
        assert np.allclose([r['time_s'] for r in rows],t['time'])
        assert np.array_equal([r['sliding']+r['sticking'] for r in rows],t['closed'])
        err=float(np.max(abs(np.array([r['loaded_corner_pen_max'] for r in rows])-c['max_closed_corner_penetration_mm'])))
        assert err<1e-6,err
        checks[real]=dict(number_of_sets=len(rows),maximum_difference_from_closed_NMISC_corner_penetration_mm=err,
                          maximum_nodal_contact_pressure_MPa=max(r['p_max'] for r in rows))
    (ROOT/'validation/stored_contact_reader.json').write_text(json.dumps(dict(control=case,rst_sha256=proof['rst_sha256'],
        scope='Stored corner statuses and loaded penetration agree with native NMISC control. Corner-extrapolated pressure and centroid pressure are different measures.',
        pairs=checks),indent=2)+'\n')


if __name__=='__main__':verify_local()
