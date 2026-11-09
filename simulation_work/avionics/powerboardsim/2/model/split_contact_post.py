"""Repeat the POST1 contact readback with every native real-constant child of a split pair."""
import argparse
import ctypes
import os
import re

import numpy as np

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from native_rst import read_rst

PAIRS={853:853,880:858,881:858,882:858,883:858}


def location(case,campaign):
    assert case in ('flush_nylon_surf1_static','flush_aluminium_surf1_static')
    assert campaign=='nov08_01'
    return ROOT/'.runtime'/('contact_readback_'+case+'_'+campaign)


def selection(pair,children):
    return [f'ESEL,S,REAL,,{pair}',*[f'ESEL,A,REAL,,{real}' for real in children],f'ESEL,R,TYPE,,{PAIRS[pair]}']


def stage(case,campaign):
    out=location(case,campaign);out.mkdir(parents=True,exist_ok=True)
    vault=ROOT/'.runtime/archive'/campaign/case
    receipt=ROOT/'.runtime/receipts'/campaign/case
    assert (receipt/'released.txt').is_file()
    ledger=read(receipt/'archived.json')
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    for name in ('solve.out','file.rst','file.rdb','seat_contacts.csv'):verified(vault/name,hashes[name])
    raw=(vault/'solve.out').read_text(errors='replace')
    matches=re.findall(r'CONTACT PAIR ASSOCIATED WITH REAL CONSTANT\s+(\d+) SPLIT INTO\s+(\d+) NEW PAIRS\s+ASSOCIATED WITH REAL CONSTANTS\s+(\d+)\s*-\s*(\d+)',raw)
    children={k:[] for k in PAIRS}
    for base,count,a,b in matches:
        parent=int(base)
        if parent not in children:continue
        fresh=list(range(int(a),int(b)+1))
        assert len(fresh)+1==int(count) and not children[parent] and not set(fresh).intersection(PAIRS)
        children[parent]=fresh
    assert any(children.values())
    clone=ctypes.CDLL(None,use_errno=True).clonefile
    for name in ('file.rst','file.rdb'):
        dest=out/name
        if not dest.exists():
            if clone(os.fsencode(vault/name),os.fsencode(dest),0):raise OSError(ctypes.get_errno(),'readback clone failed')
        assert dest.stat().st_ino!=(vault/name).stat().st_ino
        verified(dest,hashes[name])
    initial=read(ROOT/'validation/board_surface_initial.json')
    counts={853:8038,**{p:initial['pairs'][str(p)]['PLA_facets'] for p in PAIRS if p!=853}}
    lines=['/batch','resume,file,rdb','/post1','file,file,rst','rsys,0','allsel,all','set,last','*get,ns,active,0,set,nset',
           '*cfopen,selection,csv','*vwrite',"('pair,element,real')"]
    for pair in PAIRS:
        lines+=selection(pair,children[pair])+['*get,nc,elem,0,count',f'*if,nc,ne,{counts[pair]},then',
               '*msg,fatal','Combined contact face selection disagrees with the sealed mesh.','*endif',
               'ee=0','*do,j,1,nc','ee=elnext(ee)','*get,rr,elem,ee,attr,real',
               f'*vwrite,{pair},ee,rr',"(F5.0,',',F12.0,',',F6.0)",'*enddo']
    lines+=['*cfclos','allsel,all','*cfopen,contacts,csv','*vwrite',
        "('set,time_s,pair,faces,far,near,sliding,sticking,p_max_Pa,pen_max_m')",
        '*do,ii,1,ns','allsel,all','set,,,,,,,ii','*get,sb,active,0,set,sbst',
        '*if,sb,eq,999999,then','*cycle','*endif','*get,tk,active,0,set,time']
    for pair in PAIRS:
        sel=selection(pair,children[pair])
        lines+=sel+['*get,nc,elem,0,count','etable,eras','etable,cs,cont,stat,max','etable,cpres,cont,pres,max',
               'etable,cpen,cont,pene,max','esort,etab,cpres,0,0','*get,pmax,sort,0,max','esort,etab,cpen,0,0',
               '*get,penmax,sort,0,max','*do,jk,0,3',*sel,'esel,r,etab,cs,jk,jk','*get,nj,elem,0,count','ct%jk%=nj',
               '*enddo',f'*vwrite,ii,tk,{pair},nc,ct0,ct1,ct2,ct3,pmax,penmax',
               "(F6.0,',',E16.9,6(',',F8.0),2(',',E16.8))"]
    lines+=['*enddo','*cfclos','allsel,all','/com,SPLIT_CONTACT_READBACK_FINISHED','finish','/exit,nosave']
    deck=('\r\n'.join(lines)+'\r\n').encode()
    inp=out/'control.inp'
    if inp.exists():assert inp.read_bytes()==deck
    else:inp.write_bytes(deck)
    request=dict(case=case,campaign=campaign,source_rst_sha256=hashes['file.rst'],source_rdb_sha256=hashes['file.rdb'],
        solver_listing_sha256=hashes['solve.out'],original_table_sha256=hashes['seat_contacts.csv'],
        post_input_sha256=digest(inp),split_real_constants={str(k):v for k,v in children.items()})
    if (out/'request.json').exists():assert read(out/'request.json')==request
    else:write_json(out/'request.json',request)
    print(out,flush=True)


def audit(case,campaign):
    out=location(case,campaign)
    m=read(out/'request.json')
    assert m['case']==case and m['campaign']==campaign
    for f,h in [('file.rst','source_rst_sha256'),('file.rdb','source_rdb_sha256'),('control.inp','post_input_sha256')]:
        verified(out/f,m[h])
    assert (out/'exit.txt').read_text(encoding='utf-8-sig').strip()=='0'
    log=(out/'control.out').read_text(errors='replace')
    assert 'SPLIT_CONTACT_READBACK_FINISHED' in log and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    r=read_rst(out/'file.rst');g=r.grid.cell_data
    selected=table(out/'selection.csv');rows=table(out/'contacts.csv')
    indices=np.flatnonzero(r._resultheader['ls_table'][:,1]!=999999)
    counts={};sets={}
    pressure_error=penetration_error=0.
    for pair,etype in PAIRS.items():
        selected_pair=selected[selected['pair']==pair]
        true=g['ansys_elem_num'][(g['ansys_etype']==etype)&(g['ansys_real_constant']==pair)]
        assert np.array_equal(np.sort(selected_pair['element']),np.sort(true))
        groups,qty=np.unique(selected_pair['real'],return_counts=True)
        assert set(groups)=={pair,*m['split_real_constants'][str(pair)]}
        counts[pair]=dict(zip(map(int,groups),map(int,qty),strict=True))
        sets[pair]=np.sort(true)
    assert len(rows)==len(indices)*len(PAIRS)
    for k in indices:
        enum,data,nodes=r.element_solution_data(int(k),'ECT')
        for pair,ids in sets.items():
            (a,)=rows[(rows['pair']==pair)&(rows['set']==k+1)]
            pos=np.searchsorted(enum,ids);assert np.array_equal(enum[pos],ids)
            # ETABLE averages over distinct face corners. Three-node triangular
            # faces repeat their last corner in the fourth native storage slot.
            vals=np.zeros((len(ids),3))
            for j,i in enumerate(pos):
                v=data[i]
                if v is None or not len(v):continue
                nn=nodes[i];unique=np.unique(nn,return_index=True)[1]
                corners=v[:10*len(nn)].reshape(len(nn),10)
                vals[j]=corners[unique,:3].mean(axis=0,dtype=np.float64)
            assert abs(a['time_s']-r.time_values[k])<1e-8 and a['faces']==len(ids)
            for status,col in enumerate(('far','near','sliding','sticking')):
                assert a[col]==np.count_nonzero(abs(vals[:,0]-status)<1.e-6),(k,pair,col)
            for column,index in [('pen_max_m',1),('p_max_Pa',2)]:
                observed=vals[:,index].max(initial=0);expected=a[column]
                assert np.isclose(observed,expected,rtol=2e-6,atol=1e-12),(k,pair,column,observed,expected)
                diff=abs(observed-expected)
                if index==1:penetration_error=max(penetration_error,diff)
                else:pressure_error=max(pressure_error,diff)
    verdict=dict(**m,sets=len(indices),selected_faces_by_real=counts,selection_sha256=digest(out/'selection.csv'),
                 readback_sha256=digest(out/'control.out'),corrected_table_sha256=digest(out/'contacts.csv'),
                 largest_centroid_pressure_error_Pa=float(pressure_error),largest_centroid_penetration_error_m=float(penetration_error))
    write_json(ROOT/'validation/split_contact_readback'/(case+'.json'),verdict)
    return rows


def corrected_rows(case,campaign,original):
    path=ROOT/'validation/split_contact_readback'/(case+'.json')
    if not path.is_file():
        rows=table(original)
        initial=read(ROOT/'validation/board_surface_initial.json')
        counts={853:8038,**{p:initial['pairs'][str(p)]['PLA_facets'] for p in PAIRS if p!=853}}
        if any(not np.all(rows['faces'][rows['pair']==p]==n) or not np.any(rows['pair']==p) for p,n in counts.items()):
            stage(case,campaign)
            raise ValueError('Incomplete contact-face POST1 selection. Full split-pair readback is staged.')
        return rows
    v=read(path);out=location(case,campaign)
    assert v['case']==case and v['campaign']==campaign
    verified(original,v['original_table_sha256'])
    verified(original.parent/'file.rst',v['source_rst_sha256'])
    verified(out/'contacts.csv',v['corrected_table_sha256'])
    return table(out/'contacts.csv')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['stage','audit']);p.add_argument('case');p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();(stage if a.operation=='stage' else audit)(a.case,a.campaign)
