"""Generate a CAD case and compliant attachment for the October edge-cell local pull fixture.

Local units are N, mm and MPa. The historical model supplies the active rigid cell pilot
and flexible nickel strips. The other two cells and adjacent washers form a fixed fixture.
"""
import json
from pathlib import Path
import numpy as np
from extend_board import ROOT,SCREWS,NODE,component

def target_skin():
    """Tessellate the actual B-reps and orient triangles outward using their volume boundary."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE,TopAbs_REVERSED
    cad=STEPControl_Reader()
    cad.ReadFile(str(ROOT.parent/'1/src/Power_Board_Batt_Screw_defeatured_2.STEP'))
    cad.TransferRoots()
    ex=TopExp_Explorer(cad.OneShape(),TopAbs_SOLID)
    groups={'cell':[],'washer':[]}
    while ex.More():
        solid=ex.Current();prop=GProp_GProps();BRepGProp.VolumeProperties_s(solid,prop)
        vol=prop.Mass()
        kind='cell' if 25000<vol<25400 else 'washer' if 139<vol<141 else None
        if kind:groups[kind].append((prop.CentreOfMass().Coord(),vol,solid))
        ex.Next()
    assert len(groups['cell'])==3 and len(groups['washer'])==6
    items=list(zip([4,19,15],sorted(groups['cell'],key=lambda s:s[0][0])))
    items+=list(zip([1,6,9,10,11,20],sorted(groups['washer'],key=lambda s:(s[0][1],s[0][0]))))
    points=[];data={}
    for body,(_,vol,solid) in items:
        deflection,angle=(.005,.07) if body in (4,19,15) else (.02,.25)
        mesher=BRepMesh_IncrementalMesh(solid,deflection,False,angle,False);assert mesher.IsDone()
        faces=TopExp_Explorer(solid,TopAbs_FACE);tris=[];vertex={}
        while faces.More():
            face=TopoDS.Face(faces.Current());loc=TopLoc_Location()
            poly=BRep_Tool.Triangulation_s(face,loc)
            mapping={}
            for i in range(1,poly.NbNodes()+1):
                xyz=tuple(round(v,9) for v in poly.Node(i).Transformed(loc.Transformation()).Coord())
                if xyz not in vertex:vertex[xyz]=len(points);points.append(xyz)
                mapping[i]=vertex[xyz]
            for j in range(1,poly.NbTriangles()+1):
                a,b,c=[mapping[k] for k in poly.Triangle(j).Get()]
                tris.append((a,c,b) if face.Orientation()==TopAbs_REVERSED else (a,b,c))
            faces.Next()
        t=np.array(tris);xyz=np.array(points)[t];xyz-=xyz.mean(axis=(0,1))
        check=np.einsum('ij,ij->i',xyz[:,0],np.cross(xyz[:,1],xyz[:,2])).sum()/6
        assert abs(check/vol-1)<.01,(body,check,vol)
        data[str(body)]=t
    data['points']=np.asarray(points);out=ROOT/'.runtime/mesh/fixture_targets.npz'
    np.savez_compressed(out,**data)
    return out

def rigid_surface(lines,skin,bodies,pilot,real,tags,mesh):
    """Attach the target facets to their own rigid pilot and pair with selected PLA faces."""
    coords=skin['points'];tri=np.vstack([skin[str(body)] for body in bodies])
    base_node=1600000 if real==861 else 1800000
    lines.extend(['ALLSEL,ALL','TYPE,861',f'REAL,{real}','TSHAP,PILO',f'E,{pilot}'])
    for i in np.unique(tri):
        x,y,z=coords[i];lines.append(f'N,{base_node+i},{x:.9g},{y:.9g},{z:.9g}')
    lines.append('TSHAP,TRIA')
    for triangle in tri:lines.append('E,'+','.join(map(str,base_node+triangle)))
    lines.extend(['TSHAP','ALLSEL,ALL','ESEL,S,TYPE,,850'])
    faces=np.unique(np.concatenate([mesh[str(t)].ravel() for t in tags]))
    component(lines,'CASE_PATCH',NODE+faces)
    lines.extend(['CMSEL,S,CASE_PATCH,NODE','TYPE,862',f'REAL,{real}','MAT,862','ESURF','ALLSEL,ALL'])

def make(mesh,skin,variant,offset,pilot,initial_retreat_mm=0.):
    local=mesh['points']
    pts=np.column_stack((34.6075+local[:,0],60.3885+local[:,2],-.55118-10-offset-initial_retreat_mm-local[:,1]))
    e,nu,rho=SCREWS[variant]
    lines=['FINISH','/PREP7','ALLSEL,ALL','CSYS,0','ESYS,0','ET,850,SOLID187','MP,EX,850,3426.9','MP,EY,850,3426.9','MP,EZ,850,3064.9','MP,GXY,850,1269.22','MP,GXZ,850,1201.54','MP,GYZ,850,1201.54','MP,PRXY,850,.35','MP,PRXZ,850,.35','MP,PRYZ,850,.35','MP,DENS,850,1.17E-9','TYPE,850','MAT,850','REAL,1']
    for i,xyz in enumerate(pts):lines.append('N,'+str(NODE+i)+','+','.join(f'{v:.11g}' for v in xyz))
    for i,t in enumerate(mesh['tets'][:,[0,1,2,3,4,5,6,7,9,8]]+NODE):
        lines.extend(['EN,'+str(1200001+i)+','+','.join(map(str,t[:8])),'EMORE,'+','.join(map(str,t[8:]))])
    lines.extend(['ET,851,BEAM188',f'MP,EX,851,{e/1e6}',f'MP,PRXY,851,{nu}',f'MP,DENS,851,{rho*1e-12}','SECTYPE,851,BEAM,CSOLID','SECDATA,1.672,12,2','KEYOPT,851,3,3','ET,854,COMBIN39','KEYOPT,854,4,1'])
    for i,(sx,sy) in enumerate([(-1,-1),(-1,1),(1,-1),(1,1)]):
        case_xy=np.array([34.6075+sx*31.4275,60.3885+sy*56.62058])
        pcb_xy=np.array([34.6075+sx*31.4325,60.3885+sy*57.2135])
        axis=pcb_xy+.095*(case_xy-pcb_xy)/np.linalg.norm(case_xy-pcb_xy)
        ids=np.unique(mesh[str([42,38,40,44][i])])
        ring=ids[np.linalg.norm(pts[ids,:2]-axis,axis=1)<3.75]
        lo=950001+2*i;up=lo+1
        for node,z in [(lo,pts[ring,2].mean()),(up,-.55118-initial_retreat_mm)]:lines.append(f'N,{node},{axis[0]:.11g},{axis[1]:.11g},{z:.11g}')
        lines.extend(['TYPE,851','MAT,851','SECNUM,851',f'E,{lo},{up}',f'D,{up},ALL,0'])
        lines.extend(f'CERIG,{lo},{n},UXYZ' for n in (ring+NODE))
        k=3064.9*np.pi*(4**2-2.15**2)/(offset+2.0828)
        lines.extend([f'R,{870+i},-4,{-4*k:.11g},0,0,4,0','TYPE,854',f'REAL,{870+i}',f'E,{lo},{up}'])
    lines.extend(['ET,861,TARGE170','KEYOPT,861,2,1','ET,862,CONTA174','KEYOPT,862,9,2','MP,MU,862,0','R,861','R,862'])
    rigid_surface(lines,skin,[4],pilot,861,[10,11,12,13],mesh)
    fixed=959001;lines.extend([f'N,{fixed},34.6075,60.3885,-11.822674',f'D,{fixed},ALL,0'])
    rigid_surface(lines,skin,[15,19,1,6,9,10,11,20],fixed,862,list(range(5,46)),mesh)
    lines.extend(['ALLSEL,ALL','FINISH','/PREP7'])
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    target=ROOT/'.runtime/mesh/fixture_targets.npz'
    if not target.is_file():target_skin()
    mesh=np.load(ROOT/'.runtime/mesh/case_3.npz');skin=np.load(target)
    summary={}
    for case in ['lateral_friction_locked','lateral_friction_locked_fine','lateral_friction_locked_minus','damage_cont_nominal']:
        source=ROOT/'.runtime/local_inputs'/case
        pilot=json.loads((source/'mesh.json').read_text())['pilot']
        # Add the case and its load path before the original SAVE,model,db and uninterrupted SOLU history.
        for seat,h in [('flush',0.),('stand3',3.)]:
            for material in SCREWS:
                name=seat+'_'+material+'_'+case
                d=ROOT/'.runtime/local_cased'/name;d.mkdir(parents=True,exist_ok=True)
                extra=make(mesh,skin,material,h,pilot)
                text=(source/'run.dat').read_text()
                tag='SAVE,model,db';assert text.count(tag)==1
                text=text.replace(tag,extra+tag)
                (d/'run.dat').write_text(text)
                pre=text.split(tag)[0]+'\nALLSEL,ALL\n/COM,LOCAL_CASE_PREFLIGHT_END\nFINISH\n/EXIT,NOSAVE\n'
                (d/'preflight.dat').write_text(pre)
                import hashlib
                summary[name]={'source':case,'pilot':pilot,'rigid_neighbors':[15,19],'support_upper_pilots':[950002,950004,950006,950008,959001],'mm_N_MPa':True,'run_sha256':hashlib.sha256(text.encode()).hexdigest()}
    (ROOT/'validation/local_cased_candidates.json').write_text(json.dumps(summary,indent=2)+'\n')
