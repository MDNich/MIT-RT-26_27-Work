"""Intersect the supplied STEP and original hardware at registered mounting positions (mm)."""
import json,math
from pathlib import Path
import gmsh

ROOT=Path(__file__).resolve().parents[1]
case=next((ROOT/'geometry').glob('*.STEP'))
old=ROOT.parent/'1/src/Power_Board_Batt_Screw_defeatured_2.STEP'
# Coordinates of four nonplated mounting holes in the archived PCB ODB++ drill file.
PCB_CENTER=(34.6075,60.3885)
PCB_BOTTOM=-0.55118
GROUPS={'cells':[4,15,19],'nickel':[2,7,8,14,17,21],'fasteners':[22,23,24,25,26,27]}
def run(clearance):
    gmsh.initialize()
    gmsh.option.setNumber('General.Terminal',0)
    occ=gmsh.model.occ
    hardware=occ.importShapes(str(old)); cap,=occ.importShapes(str(case)); original=occ.getMass(*cap)
    # Local z -> assembly y; local y -> negative assembly z. Tabs' mating plane y=-10.
    occ.rotate([cap],0,0,0,1,0,0,-math.pi/2)
    occ.translate([cap],*PCB_CENTER,PCB_BOTTOM-10-clearance)
    records=[]
    for d,t in hardware:
        result,_=occ.intersect([cap],[(d,t)],removeObject=False,removeTool=False)
        volume=sum(occ.getMass(dd,tt) for dd,tt in result if dd==3)
        if any(x==cap or x in hardware for x in result):raise RuntimeError('Unexpected overlap identity')
        occ.remove(result,recursive=True)
        if volume>1e-5:
            group=next((k for k,vs in GROUPS.items() if t in vs),'other hardware')
            records.append({'body':t,'type':group,'overlap_mm3':volume})
    gmsh.finalize()
    return dict(tab_standoff_mm=clearance,case_origin_z_mm=PCB_BOTTOM-10-clearance,case_volume_mm3=original,overlaps=records)
if __name__=='__main__':
    data=[run(c) for c in (0,1.271494,1.5,2,3,5)]
    (ROOT/'validation/case_fit.json').write_text(json.dumps(data,indent=2)+'\n')
    for r in data:print(r['tab_standoff_mm'],[(v['body'],round(v['overlap_mm3'],2)) for v in r['overlaps']])
