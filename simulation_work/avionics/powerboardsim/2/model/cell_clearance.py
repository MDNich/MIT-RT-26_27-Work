"""Find geometric first contact under rigid lateral translation of one cell, with the case held stationary."""
import json,math
from pathlib import Path
import gmsh
ROOT=Path(__file__).resolve().parents[1]
def run():
    gmsh.initialize();gmsh.option.setNumber('General.Terminal',0)
    occ=gmsh.model.occ
    cells=occ.importShapes(str(ROOT.parent/'1/src/Power_Board_Batt_Screw_defeatured_2.STEP'))
    cap,=occ.importShapes(str(next((ROOT/'geometry').glob('*.STEP'))))
    occ.rotate([cap],0,0,0,1,0,0,-math.pi/2)
    occ.translate([cap],34.6075,60.3885,-13.55118)
    data=[]
    for tag in [4,19,15]:
        cell=(3,tag)
        for direction in [-1,1]:
            lo,hi=0.,.5
            def distance(dx):
                moving,=occ.copy([cell]);occ.translate([moving],direction*dx,0,0)
                d=occ.getDistance(*moving,*cap)[0];occ.remove([moving],True)
                return float(d)
            clearance=distance(0)
            assert clearance>0 and distance(hi)<1e-6
            while hi-lo>1.e-5:
                mid=(hi+lo)/2
                if distance(mid)<1.e-6:hi=mid
                else:lo=mid
            data.append(dict(step_body=tag,direction=direction,rest_distance_mm=clearance,
                             contact_translation_bracket_mm=[lo,hi]))
    gmsh.finalize();return data
if __name__=='__main__':
    rows=run();print(rows)
    (ROOT/'validation/rigid_cell_clearance.json').write_text(json.dumps(rows,indent=2)+'\n')
