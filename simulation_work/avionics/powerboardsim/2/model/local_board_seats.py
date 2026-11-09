"""Use fixed PCB landing faces and an initially clear tab contact in the local flush fixture."""
import re,sys
import numpy as np
from audit_local import ROOT,read,table
from extend_board import NODE,component
from film_identity import digest,verified,write_json
from native_rst import read_rst
from stage_local_jobs import seal
from tab_seating import Z_BOARD

TRIAL='local_seat_faces_v1'
PILOTS=(959011,959012,959013,959014)

def landing_cards(campaign):
    key='bare_static';p=read(ROOT/'validation/global'/f'{key}.json')
    assert p['campaign']==campaign
    path=ROOT/'.runtime/archive'/campaign/key/'file.rst';verified(path,p['rst_sha256'])
    raw=read_rst(path);grid=raw.quadgrid
    pcb=grid.extract_cells((grid.cell_data['ansys_elem_type_num']==186)&(grid.cell_data['ansys_material_type']==208))
    from itertools import combinations
    skin=pcb.extract_surface(nonlinear_subdivision=0,algorithm='dataset_surface')
    native=skin.point_data['ansys_node_num'];i=np.searchsorted(raw.mesh.nnum,native)
    assert np.array_equal(raw.mesh.nnum[i],native)
    pts=raw.mesh.nodes[i]*1e3
    face_nodes={}
    faces=skin.faces;k=0
    while k<len(faces):
        count=faces[k];local=faces[k+1:k+1+count];k+=count+1
        if np.any(abs(pts[local,2]-Z_BOARD)>1e-6):continue
        keys=native[local]
        assert count in (3,4) and len(set(keys))==count
        for triple in combinations(keys,3):
            key=tuple(sorted(triple))
            assert key not in face_nodes
            face_nodes[key]=keys
    inventory=table(ROOT/'.runtime/board_surface_initial_v1/seat_faces.csv')
    shape=np.load(ROOT/'.runtime/mesh/case_3.npz')
    source=read(ROOT/'validation/board_surface_candidates.json')['tab_pairs']
    lines=['ALLSEL,ALL','ET,857,TARGE170','KEYOPT,857,2,1','ET,858,CONTA174',
           'KEYOPT,858,2,0','KEYOPT,858,9,0','KEYOPT,858,12,0','MP,MU,858,0']
    out=[]
    for j,spec in enumerate(source):
        real=spec['pair'];face=spec['cad_face'];xmin,xmax,ymin,ymax=spec['target_window_xy_mm']
        rows=inventory[(inventory['pair']==real)&(inventory['type']==857)]
        triangles=[]
        for row in rows:
            a,b,c=(int(row[n]) for n in ('node1','node2','node3'))
            poly=face_nodes[tuple(sorted([a,b,c]))]
            triangles.append((a,b,c))
            if len(poly)==4:
                fourth=(set(poly)-{a,b,c}).pop()
                triangles.append((a,c,fourth))
        facets=np.array(triangles);xyz=raw.mesh.nodes[np.searchsorted(raw.mesh.nnum,facets)]*1000
        normals=np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0])
        assert len(rows)>100 and np.all(normals[:,2]<0)
        assert np.all(xyz[:,:,0]>=xmin-1e-5) and np.all(xyz[:,:,0]<=xmax+1e-5)
        assert np.all(xyz[:,:,1]>=ymin-1e-5) and np.all(xyz[:,:,1]<=ymax+1e-5)
        ids=np.unique(facets);pilot=PILOTS[j];coords=raw.mesh.nodes[np.searchsorted(raw.mesh.nnum,ids)]*1000
        center=coords.mean(axis=0)
        lines+=['ALLSEL,ALL',f'R,{real}',f'RMODIF,{real},6,-3.6',f'RMODIF,{real},4,-0.0001',
                f'N,{pilot},'+','.join(f'{v:.12g}' for v in center),f'D,{pilot},ALL,0','TYPE,857',
                f'REAL,{real}','TSHAP,PILO',f'E,{pilot}']
        for n,point in zip(ids,coords,strict=True):lines.append(f'N,{3000000+n},'+','.join(f'{v:.12g}' for v in point))
        lines+=['TSHAP,TRIA']+['E,'+','.join(map(str,3000000+t)) for t in facets]
        lines+=['TSHAP','ALLSEL,ALL','ESEL,S,TYPE,,850']
        component(lines,'PB_TAB',NODE+np.unique(shape[str(face)]))
        lines+=['CMSEL,S,PB_TAB,NODE','TYPE,858','MAT,858',f'REAL,{real}','ESURF','ALLSEL,ALL']
        out.append(dict(real=real,board_pilot=pilot,native_parent_faces=len(rows),triangles=len(facets),tab_faces=spec['native_contact_faces_expected'],
                        area_mm2=float(-normals[:,2].sum()/2),normal='negative board Z',initial_gap_mm=3.))
    return '\n'.join(lines)+'\n',out,p['rst_sha256']

def stage(campaign):
    cards,counts,parent=landing_cards(campaign)
    src=read(ROOT/'validation/local_install_jobs.json')
    trial=ROOT/'.runtime'/TRIAL;trial.mkdir(exist_ok=True)
    models={}
    for old,ref in src.items():
        folder=ROOT/'.runtime/inputs'/old
        verified(folder/'model.inp',ref['input_sha256'])
        deck=(folder/'model.inp').read_text()
        for i in range(4):
            lo=950001+2*i;up=lo+1
            pattern=rf'(?m)^R,{870+i},-4,[^\n]+\nTYPE,854\nREAL,{870+i}\nE,{lo},{up}\n'
            deck,n=re.subn(pattern,'',deck);assert n==1
        marker='SAVE,model,db';assert deck.count(marker)==1
        deck=deck.replace(marker,cards+marker)
        nxt=old.replace('_approach1','_seatfaces1')
        models[nxt]=seal(trial/(nxt+'.inp'),deck.encode())
        if 'nylon' not in nxt:continue
        inventory=['ALLSEL,ALL','/GOPR','*CFOPEN,seat_inventory,csv','*VWRITE',"('pair,targets,contacts')",
                   '*DO,IR,880,883','ESEL,S,TYPE,,857','ESEL,R,REAL,,IR','*GET,NTA,ELEM,0,COUNT',
                   'ESEL,S,TYPE,,858','ESEL,R,REAL,,IR','*GET,NCO,ELEM,0,COUNT','*VWRITE,IR,NTA,NCO',
                   "(F4.0,',',F8.0,',',F8.0)",'*ENDDO','*CFCLOS','ALLSEL,ALL','FINISH','/SOLU','ANTYPE,STATIC',
                   'CNCHECK,DETAIL,880,883','CNCHECK,DETAIL,861,864','/COM,LOCAL_TAB_INITIAL_FINISHED','FINISH','/EXIT,NOSAVE']
        pre=seal(trial/'pre.inp',(deck.split(marker)[0]+'\n'.join(inventory)+'\n').encode())
    result=dict(models=models,preflight_sha256=pre,original_PCB_rst_sha256=parent,pairs=counts,
                scope='Local rigid board-face scenario. Preserves the original board footprint and through holes. Four short screw grips move independently of the fixed tab/PCB contacts.')
    write_json(ROOT/'validation/local_seat_inputs.json',result)

def verify():
    d=ROOT/'.runtime'/TRIAL;p=read(ROOT/'validation/local_seat_inputs.json')
    assert int((d/'exit.txt').read_text(encoding='utf-16').strip())==0 and digest(d/'pre.inp')==p['preflight_sha256']
    text=(d/'pre.out').read_text(errors='replace')
    assert 'LOCAL_TAB_INITIAL_FINISHED' in text and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',text)
    rows=table(d/'seat_inventory.csv');assert len(rows)==4
    result=[]
    for row,spec in zip(rows,p['pairs'],strict=True):
        assert row['pair']==spec['real'] and row['targets']==1+spec['triangles'] and row['contacts']==spec['tab_faces']
        tag=rf'Contact pair identified by real constant set\s+{spec["real"]}\b'
        block=re.split(tag,text,flags=re.I)[1].split('Contact pair identified')[0]
        gap=re.search(r'Min\.\s+Initial gap\s+([\d.E+-]+)',block,re.I)
        assert gap and abs(float(gap[1])-3.)<1e-4 and not re.search(r'Max\.\s+Initial penetration',block,re.I)
        result.append(dict(**spec,native_gap_mm=float(gap[1])))
    write_json(ROOT/'validation/local_seat_preflight.json',dict(input_sha256=p['preflight_sha256'],listing_sha256=digest(d/'pre.out'),pairs=result))
if __name__=='__main__':
    if sys.argv[1]=='audit':verify()
    else:stage(sys.argv[1])
