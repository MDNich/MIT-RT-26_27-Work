"""Add the registered CAD mesh, four compliant screw shanks and unilateral dry contacts to an archived global model."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import io
import re
ROOT=Path(__file__).resolve().parents[1]
NODE=800001
FACE_MATERIALS=[173,174,176,178,179,180,181,182,183,186,187,189,191,192,193]
SCREWS={'nylon':(3000e6,.39,1140.),'aluminium':(69e9,.33,2700.)}

def component(lines,name,nids):
    ids=sorted(set(map(int,nids)))
    if not ids:raise ValueError(f'Empty selection {name}')
    lines.extend([f'CMBLOCK,{name},NODE,{len(ids)}','(8i10)'])
    lines.extend(''.join(f'{n:10d}' for n in ids[i:i+8]) for i in range(0,len(ids),8))

def board_feet(deck):
    """Read PCB connectivity and mounting coordinates from this exact Workbench deck."""
    body=re.search(rb"Elements for Body (208) 'PCB\|PCB'.*?eblock,\d+,COMPACT,,(\d+)\s*\r?\n[^\n]*\n",deck,re.I|re.S)
    assert body and int(body[1])==208
    conn=io.BytesIO(deck[body.end():])
    pcb=set()
    for _ in range(int(body[2])):
        values=list(map(int,conn.readline().split()))
        pcb.update(values[1:])
    header=re.search(rb"(?im)^nblock,3,[^\n]*\n[^\n]*\n",deck)
    pts=[];nodes=[]
    for row in io.BytesIO(deck[header.end():]):
        if not row[:9].strip().isdigit():break
        node=int(row[:9])
        if node not in pcb:continue
        xyz=[1000*float(row[i:i+20]) for i in (9,29,49)]
        if abs(xyz[2]+.55118)<.002 and (xyz[0]<8 or xyz[0]>61) and (xyz[1]<8 or xyz[1]>112):
            nodes.append(node);pts.append(xyz)
    if not pts:raise ValueError('No lower PCB corner nodes found')
    return np.asarray(nodes),np.asarray(pts)


def build(mesh_path,board,material,offset,*,retreat_mm=0., bearing_faces=(42,38,40,44), tab_thickness_mm=2.0828, case_node_start=NODE):
    mesh=np.load(mesh_path)
    local=mesh['points'];pts=np.column_stack((34.6075+local[:,0],60.3885+local[:,2],-.55118-10-offset-local[:,1]))
    if retreat_mm:
        assert offset==0 and retreat_mm==3.
        pts[:,2]-=retreat_mm
    pcb_ids,pcb_pts=board
    e,nu,rho=SCREWS[material]
    ln=['! Power-board case. Geometry in m; elastic modulus Pa; density kg/m3.','FINISH','/PREP7','ALLSEL,ALL','CSYS,0','ESYS,0','ET,850,SOLID187','MP,EX,850,3.4269E9','MP,EY,850,3.4269E9','MP,EZ,850,3.0649E9','MP,PRXY,850,.35','MP,PRYZ,850,.35','MP,PRXZ,850,.35','MP,GXY,850,1.26922E9','MP,GYZ,850,1.20154E9','MP,GXZ,850,1.20154E9','MP,DENS,850,1170','TYPE,850','MAT,850','REAL,1']
    ln.extend(f'N,{case_node_start+i},{x*.001:.12g},{y*.001:.12g},{z*.001:.12g}' for i,(x,y,z) in enumerate(pts))
    # 10-node tetrahedra; Gmsh edges J-K-L etc have the last two edge nodes reversed relative to SOLID187.
    tet=mesh['tets'][:,[0,1,2,3,4,5,6,7,9,8]]+case_node_start
    for i,row in enumerate(tet):
        ln.append('EN,'+str(1200001+i)+','+','.join(map(str,row[:8])))
        ln.append('EMORE,'+','.join(map(str,row[8:])))
    ln.extend(['ESEL,S,TYPE,,850','CM,CASEPLA,ELEM','ALLSEL,ALL','ET,851,BEAM188',f'MP,EX,851,{e}',f'MP,PRXY,851,{nu}',f'MP,DENS,851,{rho}','SECTYPE,851,BEAM,CSOLID','SECDATA,.001672,12,2','KEYOPT,851,3,3'])
    # Compression-only seat for the tab or printed spacer. COMBIN39 uses relative axial
    # displacement along its 3D node line. The screw-material-independent pad carries clamp compression.
    ln.extend(['ET,854,COMBIN39','KEYOPT,854,4,1'])
    if retreat_mm:
        # The PCB feet stay on the real board. The short upper screw heads follow their
        # flexible board pilot plus an imposed relative-Z seating displacement.
        ln.extend(['ET,856,MASS21','KEYOPT,856,3,0','R,856,1e-10,1e-10,1e-10,1e-18,1e-18,1e-18'])
    mounts=[]
    for i,(sx,sy) in enumerate([(-1,-1),(-1,1),(1,-1),(1,1)]):
        hole=np.array([34.6075+sx*31.4275,60.3885+sy*56.62058])
        board=np.array([34.6075+sx*31.4325,60.3885+sy*57.2135])
        axis=board+(hole-board)/np.linalg.norm(hole-board)*.095
        zboard=pcb_pts[:,2].min()
        rxy=np.linalg.norm(pcb_pts[:,:2]-axis,axis=1)
        patch=pcb_ids[(rxy<=3.75)&(np.abs(pcb_pts[:,2]-zboard)<0.001)]
        ztab=-.55118-offset-tab_thickness_mm
        # Apply washer footprint at the outer tab face; these four slightly oblique planes are read from supplied CAD.
        tag=bearing_faces[i]
        tab=np.unique(mesh[str(tag)]);tabrad=np.linalg.norm(pts[tab,:2]-axis,axis=1)
        rail=tab[tabrad<3.75]
        if min(len(rail),len(patch))<3:raise ValueError((i,len(rail),len(patch)))
        ztab=pts[rail,2].mean()
        lower,upper=950001+2*i,950002+2*i
        for n,z in ((lower,ztab),(upper,zboard-retreat_mm)):
            ln.append(f'N,{n},{axis[0]*.001:.12g},{axis[1]*.001:.12g},{z*.001:.12g}')
        ln.extend(['TYPE,851','MAT,851','SECNUM,851',f'E,{lower},{upper}'])
        board_pilot=upper
        if retreat_mm:
            board_pilot,act=960101+i,960111+i
            # Only the head DOFs are eliminated. Each board pilot is a retained master
            # for one non-overlapping PCB footprint. The extra nodes have negligible inertia.
            for n in (board_pilot,act):
                ln.extend([f'N,{n},{axis[0]*.001:.12g},{axis[1]*.001:.12g},{zboard*.001:.12g}',
                           'TYPE,856','REAL,856',f'E,{n}'])
            ln.append(f'D,{act},ALL,0')
            for dof in ('UX','UY','UZ','ROTX','ROTY','ROTZ'):
                ce=f'CE,NEXT,0,{upper},{dof},1,{board_pilot},{dof},-1'
                ln.append(ce+(f',{act},UZ,-1' if dof=='UZ' else ''))
        for pilot,name,slaves in [(board_pilot,'PCBSEAT',patch),(lower,'TABSEAT',rail+case_node_start)]:
            component(ln,name,slaves)
            ln.append('ALLSEL,ALL')
            ln.extend(f'CERIG,{pilot},{int(slave)},UXYZ' for slave in slaves)
        area=np.pi*(4.0**2-2.15**2)*1e-6
        kseat=3.0649e9*area/((offset+tab_thickness_mm)*1e-3)
        real=870+i
        # Beyond the tab thickness the 3 mm variant has an assumed PLA annulus.
        ln.extend([f'R,{real},-.004,{-kseat*.004:.12g},0,0,.004,0','TYPE,854',f'REAL,{real}',f'E,{lower},{upper}'])
        mounts.append(dict(case_center_mm=hole.tolist(),board_center_mm=board.tolist(),screw_axis_mm=axis.tolist(),bearing_nodes=[len(patch),len(rail)],grip_mm=float(zboard-retreat_mm-ztab)))
    # Both sides use deformable solids. ESURF generates the surface topology and outward normals.
    ln.extend(['ET,852,TARGE170','ET,853,CONTA174','KEYOPT,853,9,2','KEYOPT,853,12,0','MP,MU,853,0','R,853','REAL,853','TYPE,852'])
    for i,body in enumerate(FACE_MATERIALS):
        ln.append(f'ESEL,{"S" if i==0 else "A"},MAT,,{body}')
    ln.extend(['ESEL,R,ENAME,,185,187','NSLE,S','ESURF','ALLSEL,ALL','ESEL,S,TYPE,,850','TYPE,853','REAL,853','MAT,853'])
    # All exterior faces can meet the cell, strips or washers as the tab seating load builds.
    ln.extend(['NSLE,S','ESURF','ALLSEL,ALL','ESEL,S,TYPE,,853','CM,CASECONTACT,ELEM','ALLSEL,ALL','FINISH','/SOLU'])
    if retreat_mm:
        ln[-2:-2]=['RMODIF,853,6,-0.0006']
    return '\r\n'.join(ln)+'\r\n',mounts

def main():
    p=argparse.ArgumentParser();p.add_argument('--mesh',default='3');a=p.parse_args()
    mesh=ROOT/f'.runtime/mesh/case_{a.mesh}.npz'
    receipt={}
    for case in ['static','original','refined']:
        base=(ROOT/f'.runtime/inputs/bare_{case}/model.inp').read_bytes()
        feet=board_feet(base)
        for seat,offset in [('flush',0.),('stand3',3.)]:
            for mat in SCREWS:
                deck,mt=build(mesh,feet,mat,offset)
                anchor=b'/gst,on,on'
                assert base.lower().count(anchor)==1
                idx=base.lower().index(anchor)
                final=base[:idx]+deck.encode()+base[idx:]
                key=f'{seat}_{mat}_{case}'
                folder=ROOT/'.runtime/inputs'/key;folder.mkdir(parents=True,exist_ok=True)
                dst=folder/'model.inp'
                if dst.exists() and dst.read_bytes()!=final:raise ValueError(f'Input changed for {key}')
                dst.write_bytes(final)
                receipt[key]=dict(tab_separation_mm=offset,material=mat,footprints=mt,staged_sha256=hashlib.sha256(final).hexdigest())
    (ROOT/'validation/cased_inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
