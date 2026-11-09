"""Prepare a flush approach with contact between actual tab and PCB faces. Never change a prior input."""
import json,re,sys
import numpy as np
from audit_local import ROOT,read,table
from extend_board import component,NODE
from film_identity import digest,write_json
from stage_local_jobs import seal
from prepare_board_install import text_commands
from seat_surface_control import pair_cards,constants
TRIAL='board_surface_initial_v1'
FACES=(33,29,25,37)
REALS=tuple(range(880,884))

def seat_surfaces(mesh):
    l=['ALLSEL,ALL',*pair_cards(857,858)];spec=[]
    p=mesh['points']
    for i,(tag,real) in enumerate(zip(FACES,REALS,strict=True)):
        ids=np.unique(mesh[str(tag)]);q=p[ids]
        assert np.max(abs(q[:,1]+10.))<1.e-6
        x=34.6075+q[:,0];y=60.3885+q[:,2]
        lim=[float(x.min()-2),float(x.max()+2),float(y.min()-2),float(y.max()+2)]
        l += ['ALLSEL,ALL',*constants(real),f'REAL,{real}','ESEL,S,MAT,,208','ESEL,R,ENAME,,185,187','NSLE,S',
              'NSEL,R,LOC,Z,-.00055119,-.00055117',f'NSEL,R,LOC,X,{lim[0]*.001:.12g},{lim[1]*.001:.12g}',
              f'NSEL,R,LOC,Y,{lim[2]*.001:.12g},{lim[3]*.001:.12g}','TYPE,857','TSHAP','ESURF',
              'ALLSEL,ALL','ESEL,S,TYPE,,850']
        component(l,'TABMATE',ids+NODE)
        l+=['CMSEL,S,TABMATE,NODE','TYPE,858','MAT,858',f'REAL,{real}','ESURF','ALLSEL,ALL']
        spec.append(dict(pair=real,cad_face=tag,native_contact_faces_expected=int(len(mesh[str(tag)])),
                         CAD_nodes=len(ids),target_window_xy_mm=lim))
    return l,spec

def revised(src,cmd):
    # Only remove the four surrogate pad springs; the short screw beams remain intact.
    for j in range(4):
        real=870+j;lo=950001+2*j;up=lo+1
        pat=rf'(?m)^R,{real},-\.004,[^\r\n]+\r\nTYPE,854\r\nREAL,{real}\r\nE,{lo},{up}\r\n'.encode()
        src,n=re.subn(pat,b'',src);assert n==1
    mark=b'ET,852,TARGE170\r\n';assert src.count(mark)==1
    return src.replace(mark,text_commands(cmd)+mark)

def inventory():
    return ['FINISH','/PREP7','/GOPR','ALLSEL,ALL','*CFOPEN,seat_faces,csv','*VWRITE',
            "('pair,type,element,node1,node2,node3,zmin_m,zmax_m,normal_z_m2')",
            '*DO,IR,880,883','*DO,IT,857,858','ESEL,S,TYPE,,IT','ESEL,R,REAL,,IR','*GET,NC,ELEM,0,COUNT',
            '*GET,IE,ELEM,0,NUM,MIN','*DO,J,1,NC','A1=NELEM(IE,1)','A2=NELEM(IE,2)','A3=NELEM(IE,3)',
            'ZZMIN=MIN(NZ(A1),NZ(A2),NZ(A3))','ZZMAX=MAX(NZ(A1),NZ(A2),NZ(A3))',
            'SZ=(NX(A2)-NX(A1))*(NY(A3)-NY(A1))-(NY(A2)-NY(A1))*(NX(A3)-NX(A1))',
            '*VWRITE,IR,IT,IE,A1,A2,A3,ZZMIN,ZZMAX,SZ',"(F4.0,',',F4.0,4(',',F9.0),3(',',E15.8))",
            'IE=ELNEXT(IE)','*ENDDO','*ENDDO','*ENDDO','*CFCLOS','ALLSEL,ALL','ESEL,S,TYPE,,854','*GET,NOLD,ELEM,0,COUNT',
            '*IF,NOLD,NE,0,THEN','/COM,UNEXPECTED_CO_MOVING_SEATS','*ENDIF','ALLSEL,ALL','FINISH','/SOLU',
            'ANTYPE,STATIC','NLGEOM,ON','CNCHECK,DETAIL,853,853','CNCHECK,DETAIL,880,883',
            '/COM,BOARD_SURFACE_INITIAL_DONE','FINISH','/EXIT,NOSAVE']

def stage():
    cmd,spec=seat_surfaces(np.load(ROOT/'.runtime/mesh/case_3.npz'))
    refs=read(ROOT/'validation/board_install_candidates.json');records={}
    for material in refs:
        base=ROOT/'.runtime/board_install_v1'/material
        assert digest(base/'static.inp')==refs[material]['static_sha256']
        folder=ROOT/'.runtime/board_surface_v1'/material;folder.mkdir(parents=True,exist_ok=True)
        static=revised((base/'static.inp').read_bytes(),cmd)
        marker=b'/gst,on,on';i=static.lower().index(marker)
        static_sha=seal(folder/'static.inp',static)
        pre_sha=seal(folder/'pre.inp',static[:i]+text_commands(inventory()))
        if material=='nylon':
            d=ROOT/'.runtime'/TRIAL;d.mkdir(exist_ok=True);assert seal(d/'pre.inp',static[:i]+text_commands(inventory()))==pre_sha
        records[material]=dict(static_sha256=static_sha,preflight_sha256=pre_sha,parent_static_sha256=refs[material]['static_sha256'],
                               restart_sha256=refs[material]['modal_restart_sha256'])
    write_json(ROOT/'validation/board_surface_candidates.json',dict(candidates=records,tab_pairs=spec,assumptions=
        'Four frictionless face pairs at actual tab undersides, PCB underside retained, no compression pad spring. Short shank, four driven heads and original six bolts unchanged. Prepared inputs only.'))

def audit():
    d=ROOT/'.runtime'/TRIAL
    assert int((d/'exit.txt').read_text(encoding='utf-16').strip())==0
    src=read(ROOT/'validation/board_surface_candidates.json')
    assert digest(d/'pre.inp')==src['candidates']['nylon']['preflight_sha256']
    listing=(d/'pre.out').read_text(errors='replace')
    assert 'BOARD_SURFACE_INITIAL_DONE' in listing and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
    assert not re.search(r'^\s*UNEXPECTED_CO_MOVING_SEATS\s*$',listing,re.M)
    assert not re.search(r'(?:constraint equation|rigid region|dependent node|ESURF).{0,100}(?:skipped|ignored|does not exist)',listing,re.I)
    faces=table(d/'seat_faces.csv');assert len(np.unique(faces['element']))==len(faces)
    assert np.array_equal(np.unique(faces['pair']),REALS)
    seen={};pairs={}
    # CNCHECK reports gaps and directions; also verify every generated face's own normal.
    for block in re.split(r'(?=Contact pair identified by real constant set)',listing,flags=re.I)[1:]:
        pair=int(re.search(r'constant set\s+(\d+)',block,re.I)[1])
        m=re.search(r'Min\.\s+Initial gap\s+([\d.E+-]+)',block,re.I)
        assert m and not re.search(r'Max\.\s+Initial penetration',block,re.I)
        seen[pair]=float(m[1])*1e3
    assert abs(seen[853]-.198685224)<.001
    for s in src['tab_pairs']:
        ir=s['pair'];assert abs(seen[ir]-3)<1e-4
        out={}
        for typ,name,sign,z in [(857,'PCB',-1,-.00055118),(858,'PLA',1,-.00355118)]:
            a=faces[(faces['pair']==ir)&(faces['type']==typ)]
            assert len(a)>10 and np.all(sign*a['normal_z_m2']>0)
            assert np.allclose(a['zmin_m'],z,rtol=0,atol=1e-8) and np.allclose(a['zmax_m'],z,rtol=0,atol=1e-8)
            if typ==858:assert len(a)==s['native_contact_faces_expected']
            out[name+'_facets']=len(a)
        pairs[ir]=dict(**out,initial_gap_mm=seen[ir])
    rec=dict(pairs=pairs,cell_interface_gap_mm=seen[853],input_sha256=digest(d/'pre.inp'),listing_sha256=digest(d/'pre.out'),
             scope='Initial native geometry/contact only; all tab normals face the board, all four patch pairs start open. No installation result.')
    write_json(ROOT/'validation/board_surface_initial.json',rec);print(rec)

if __name__=='__main__':{'stage':stage,'audit':audit}[sys.argv[1]]()
