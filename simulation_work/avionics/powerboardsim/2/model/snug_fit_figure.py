"""Plot the registered native Balius section and an exact section through the shortest washer gap."""
import json
import math

import gmsh
import numpy as np
import shapely
from shapely.plotting import patch_from_polygon
from matplotlib.patches import Patch

from case_fit import ROOT, PCB_BOTTOM, PCB_CENTER, old
from fit_figure import midspan, section, CELLS, HANDLES
from report_plot import plt

CASE = ROOT/'geometry/candidates/Balius-native-verification.STEP'
SPACING = 1.25


def washer_section(body, case, start, end):
    occ = gmsh.model.occ
    horizontal = end[:2] - start[:2]
    horizontal /= np.linalg.norm(horizontal)
    face = (2, occ.addRectangle(-3,-3,0,6,6))
    occ.rotate([face],0,0,0,1,0,0,math.pi/2)
    occ.rotate([face],0,0,0,0,0,1,math.atan2(*horizontal[::-1]))
    occ.translate([face],*start)
    profiles = []
    for target in (case,body):
        common,_ = occ.intersect([face],[target],removeObject=False,removeTool=False)
        occ.synchronize()
        lines = []
        for dim,tag in gmsh.model.getBoundary(common,oriented=False):
            assert dim==1
            a,b=gmsh.model.getParametrizationBounds(dim,tag)
            points=gmsh.model.getValue(dim,tag,np.linspace(a[0],b[0],181)).reshape(-1,3)-start
            lines.append(shapely.LineString(np.round(np.c_[points[:,:2]@horizontal,points[:,2]],8)))
        polygon=shapely.build_area(shapely.MultiLineString(lines))
        assert polygon.area > 0
        profiles.append(polygon)
    return profiles, np.array([np.dot(end[:2]-start[:2],horizontal),end[2]-start[2]])


def draw():
    audit=json.loads((ROOT/'validation/alternate_case_fit.json').read_text())
    gaps=audit['Balius_native']['shortest_gaps_mm']['1.25']
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0)
        occ=gmsh.model.occ
        occ.importShapes(str(old)); case,=occ.importShapes(str(CASE))
        occ.rotate([case],0,0,0,1,0,0,-math.pi/2)
        occ.translate([case],*PCB_CENTER,PCB_BOTTOM-10-SPACING)
        tag=min((6,9,10,11),key=lambda tag:gaps[str(tag)])
        dist,*p=occ.getDistance(*case,3,tag)
        assert abs(dist-gaps[str(tag)])<1e-7
        profiles,q=washer_section((3,tag),case,np.array(p[:3]),np.array(p[3:]))
        assert np.isclose(np.linalg.norm(q),dist)
    finally:
        gmsh.finalize()
    fig,(ax,zoom)=plt.subplots(1,2,figsize=(8.4,3.35),gridspec_kw={'width_ratios':[2.25,1]},layout='constrained')
    section(ax,midspan(CASE),SPACING,'Battery midspan')
    ax.set_xlabel('Board X [mm]')
    for (x,z),tag in zip(CELLS,(4,19,15),strict=True):
        ax.text(x,z,f'{gaps[str(tag)]:.3f} mm',ha='center',va='center',fontsize=8)
    for poly,color,edge in zip(profiles,('#8AAEE8','#C8CAD2'),('#658CCB','#444754'),strict=True):
        zoom.add_patch(patch_from_polygon(poly,facecolor=color,edgecolor=edge,lw=.8))
    zoom.plot([0,q[0]],[0,q[1]],'o-',lw=1.5,ms=3,color='#7A0101')
    zoom.annotate(f'{dist:.3f} mm',xy=q/2,xytext=(.46,-.46),ha='center',fontsize=9,
                  arrowprops={'arrowstyle':'->','lw':.8,'color':'#7A0101'},bbox={'facecolor':'white','edgecolor':'none','pad':1.2})
    zoom.set(aspect='equal',xlim=(-.75,1.0),ylim=(-.72,1.03),xlabel='In-plane distance [mm]',ylabel='Relative height [mm]')
    zoom.set_title('Closest outer washer',loc='left',fontsize=10,color='#08357E')
    fig.suptitle('Balius native case at 1.25 mm tab-to-board spacing',fontsize=13)
    fig.legend(handles=HANDLES+[Patch(facecolor='#C8CAD2',edgecolor='#444754',label='Washer')],loc='outside lower center',ncol=4,frameon=False,fontsize=8)
    fig.savefig(ROOT/'docs/figures/balius-native-fit-1p25mm.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw()
