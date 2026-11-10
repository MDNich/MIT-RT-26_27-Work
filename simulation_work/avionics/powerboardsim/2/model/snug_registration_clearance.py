"""Calculate the rigid assembly's mounting-clearance limits for a pure PCB X or Y translation."""
import math
import re
import gmsh
import numpy as np
from alternate_case_fit import cylinders
from audit_local import ROOT,read
from case_fit import old,PCB_CENTER,PCB_BOTTOM
from case_drawdown_geometry import first_touch
from film_identity import verified,digest,write_json
from stage_snug_fit import AUDIT,STEP,STEP_HASH,SPACING


def run():
    verified(STEP,STEP_HASH)
    hardware=read(ROOT/'validation/rigid_case_drawdown.json')['hardware_STEP_sha256'];verified(old,hardware)
    path=AUDIT/'global_inputs.json';manifest=read(path)['snug125_nylon_static']
    assert manifest['step_sha256']==STEP_HASH and manifest['tab_spacing_mm']==SPACING
    case_centres=np.array([r['case_center_mm'] for r in manifest['supports']])
    pcb_centres=np.array([r['board_center_mm'] for r in manifest['supports']])
    bores=cylinders(STEP);radii=[]
    for xy in case_centres:
        sizes={round(radius,8) for radius,axis,loc in bores if abs(axis[1])>.999999 and
               np.linalg.norm(np.asarray(PCB_CENTER)+np.array(loc)[[0,2]]-xy)<1.e-6}
        radius,=sizes;assert 2.49<radius<2.55;radii.append(radius)
    features=ROOT/'geometry/october/pcb2_mount_drills.features'
    verified(features,'6b89fc05646cadd1479303aad7a449ebee7ab4eb611e2f1c2871af7e87ee4bde')
    drill=features.read_text()
    assert 'UNITS=MM' in drill
    sizes={int(i):float(d)/1000 for i,d in re.findall(r'(?m)^\$(\d+) r([.0-9]+)$',drill)}
    points=[(float(x),float(y),sizes[int(i)]) for x,y,i in re.findall(r'(?m)^P ([.0-9]+) ([.0-9]+) (\d+) P ',drill)]
    matched=[[r for x,y,r in points if np.linalg.norm(np.array([x,y])-xy)<1e-5] for xy in pcb_centres]
    assert all(len(v)==1 for v in matched) and len({v[0] for v in matched})==1
    bolt=2.;pcb=matched[0][0]/2
    assert abs(pcb-2.1)<1e-5
    allowed=(pcb-bolt)+(np.array(radii)-bolt)
    delta=case_centres-pcb_centres
    assert np.all(np.linalg.norm(delta,axis=1)<allowed)
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0);occ=gmsh.model.occ
        cap,=occ.importShapes(str(STEP));occ.rotate([cap],0,0,0,1,0,0,-math.pi/2)
        occ.translate([cap],*PCB_CENTER,PCB_BOTTOM-10-SPACING)
        board=occ.importShapes(str(old));assert len(board)==35
        pos=np.zeros(2)
        def set_pose(new):
            nonlocal pos
            if np.any(new!=pos):occ.translate([cap],*(new-pos),0.)
            pos=new.copy()
        gaps=np.array([occ.getDistance(*cap,*body)[0] for body in board])
        assert np.min(gaps)>1e-6
        exact=read(ROOT/'validation/alternate_case_fit.json')['Balius_native']['shortest_gaps_mm']['1.25']
        for i,g in exact.items():assert abs(gaps[int(i)-1]-g)<1e-7
        rows={}
        for a,axis in enumerate('XY'):
            for sign in (-1,1):
                direction=sign*np.eye(2)[a]
                # For an independently centred straight screw, the admissible centre disks
                # overlap when hole-axis separation <= the sum of the two radial clearances.
                parallel=delta@direction;normal=delta-parallel[:,None]*direction
                limits=-parallel+np.sqrt(allowed**2-np.sum(normal**2,axis=1))
                limit=float(limits.min());assert limit>0
                candidate=np.flatnonzero(gaps<=limit+1e-6)
                def distance(x):
                    set_pose(direction*x)
                    return min(occ.getDistance(*cap,*board[i])[0] for i in candidate)
                # Every omitted rigid body stays clear by the translation Lipschitz bound.
                limiters=np.flatnonzero(np.isclose(limits,limit,rtol=0,atol=1.e-8))
                row=dict(hole_limit_mm=limit,hole_limiting_tabs=(limiters+1).tolist(),
                         candidate_hardware_bodies=(candidate+1).tolist())
                if not candidate.size:
                    row['event']='hole limit';row['hardware_gap_lower_bound_at_limit_mm']=float(gaps.min()-limit)
                else:
                    contact=first_touch(distance,stroke=limit,resolution=.00001)
                    if contact is None:
                        row['event']='hole limit';set_pose(direction*limit)
                        row['minimum_hardware_gap_at_limit_mm']=float(min(occ.getDistance(*cap,*b)[0] for b in board))
                    else:
                        lo,hi=contact
                        assert distance(lo)>1.e-6 and distance(hi)<=1.e-6
                        ids=[i for i in candidate if occ.getDistance(*cap,*board[i])[0]<=1e-6]
                        assert ids
                        further=min(hi+.01,limit);assert further>hi
                        set_pose(direction*further)
                        volumes={}
                        for i in ids:
                            common,_=occ.intersect([cap],[board[i]],removeObject=False,removeTool=False)
                            volumes[str(i+1)]=sum(occ.getMass(*b) for b in common if b[0]==3)
                            assert not any(b==cap or b in board for b in common)
                            occ.remove(common,recursive=True)
                        assert min(volumes.values())>1.e-7
                        row.update(event='hardware contact',first_clear_touch_mm=[lo,hi],bodies=[i+1 for i in map(int,ids)],
                                   overlap_check_at_mm=further,overlap_mm3=volumes)
                set_pose(np.zeros(2))
                assert abs(occ.getDistance(*cap,*board[18])[0]-gaps[18])<1e-7
                # Independently reposition a fresh copy at the limiting pose. Use a solid
                # intersection as a second test at all potentially touching hardware bodies.
                check_at=row.get('overlap_check_at_mm',limit)
                copy,=occ.copy([cap]);occ.translate([copy],*(direction*check_at),0.)
                confirm={}
                for i in candidate:
                    shape,_=occ.intersect([copy],[board[i]],removeObject=False,removeTool=False)
                    assert not any(b in board or b in (copy,cap) for b in shape)
                    confirm[str(int(i)+1)]=sum(occ.getMass(*b) for b in shape if b[0]==3)
                    occ.remove(shape,recursive=True)
                occ.remove([copy],recursive=True)
                for key,volume in confirm.items():
                    if key in row.get('overlap_mm3',{}):
                        assert abs(volume-row['overlap_mm3'][key])<1e-6
                    elif row['event']=='hole limit':
                        assert abs(volume)<1e-7
                row['fresh_pose_overlap_mm3']=confirm
                excess=np.linalg.norm(delta+limit*direction,axis=1)-allowed
                assert abs(excess.max())<1.e-10 and np.allclose(excess[limiters],0.,atol=1e-9)
                rows['+'+axis if sign>0 else '-'+axis]=row
        write_json(AUDIT/'rigid_registration_limits.json',dict(step_sha256=STEP_HASH,hardware_sha256=hardware,
               registration_sha256=digest(path),PCB2_tgz_sha256='9ade1b62e979de876af1fe63bbfe641e43b0bf9e2c6c3b3475f6c1cfe34607fc',
               PCB_drill_member='odb/steps/pcb/layers/drill_non-plated_bottom_layer-top_layer/features',PCB_drill_member_sha256='616d64b1c9f26130b9d8600679b6cc08c93a7fd2257b4e5d92a23026fba9c8e9',PCB_drill_sha256=digest(features),tab_spacing_mm=SPACING,screw_diameter_mm=2*bolt,
               PCB_bore_diameter_mm=2*pcb,case_bore_radii_mm=radii,axes=rows,
               scope='Rigid case translation relative to the fixed PCB and cells, no rotation, preload or deformation. '
                     'All four M4 axes may float independently in the intersecting circular bore clearances. '
                     'Distances are nominal CAD margins, not print tolerances or predicted contact forces.'))
        print(rows)
    finally:gmsh.finalize()


if __name__=='__main__':run()
