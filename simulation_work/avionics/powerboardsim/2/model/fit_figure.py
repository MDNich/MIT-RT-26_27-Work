"""Draw the supplied case STEP at registered PCB stand-offs in the battery midspan plane."""
import math
from pathlib import Path

import numpy as np
import shapely
from shapely.plotting import patch_from_polygon
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from matplotlib.patches import Circle, Rectangle, Patch
from case_fit import PCB_BOTTOM, PCB_CENTER, case
from report_plot import plt

ROOT = Path(__file__).resolve().parents[1]
CELLS = [(10.803671,-11.822669),(34.697020,-11.822681),(58.555674,-11.822669)]
HANDLES = [Patch(color='#8AAEE8',label='Printed case'),
           Patch(facecolor='#c8dbbc',edgecolor='#28511a',label='Cells'), Patch(color='#34343d',label='PCB')]


def midspan():
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(case)) == IFSelect_RetDone and reader.TransferRoots()
    cut = BRepAlgoAPI_Section(reader.OneShape(),gp_Pln(gp_Pnt(0,0,0),gp_Dir(0,0,1)),True)
    assert cut.IsDone()
    edges = TopExp_Explorer(cut.Shape(),TopAbs_EDGE)
    lines = []
    while edges.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(edges.Current()))
        start, end = curve.FirstParameter(),curve.LastParameter()
        # Sampling semicircles at this resolution makes their chord error below a micrometre.
        xy = [curve.Value(t).Coord()[:2] for t in np.linspace(start,end,257)]
        lines.append(shapely.LineString(np.round(xy,8)))
        edges.Next()
    pieces = list(shapely.get_parts(shapely.polygonize(lines)))
    assert len(pieces)==1 and pieces[0].area>0
    return pieces[0]


def section(ax, poly, height, title):
    from shapely.affinity import affine_transform
    wall = affine_transform(poly, [1,0,0,-1,PCB_CENTER[0],PCB_BOTTOM-10-height])
    ax.add_patch(patch_from_polygon(wall,facecolor='#8AAEE8',edgecolor='#658CCB',lw=.45))
    for x,z in CELLS:
        ax.add_patch(Circle((x,z),10.7,facecolor='#38761d',alpha=.23))
        ax.add_patch(Circle((x,z),10.7,fill=False,ec='#28511a',lw=1))
    ax.add_patch(Rectangle((0,PCB_BOTTOM),69.215,1.10236,color='#34343d'))
    ax.set(aspect='equal',xlim=(-4,74),ylim=(-30,3),ylabel='Board Z [mm]')
    ax.set_title(title,loc='left',fontsize=10,color='#08357e')


def draw():
    poly=midspan()
    dest=ROOT/'docs/figures'
    fig,axes=plt.subplots(2,1,figsize=(7.2,4.),layout='constrained',sharex=True,sharey=True)
    for ax,h,label in zip(axes,[0,3],['Tabs flush','3 mm tab stand-off'],strict=True):
        section(ax,poly,h,label)
    axes[-1].set_xlabel('Board X [mm]')
    fig.legend(handles=HANDLES,loc='outside upper center',ncol=3,frameon=False,fontsize=9)
    fig.savefig(dest/'midspan-fit.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.0,3.25),layout='constrained')
    section(ax,poly,2.5,'2.5 mm tab stand-off')
    ax.set_xlabel('Board X [mm]')
    fig.legend(handles=HANDLES,loc='outside upper center',ncol=3,frameon=False,fontsize=10)
    # The inner middle cradle is a 10.795 mm semicircle centred at local (0,0).
    floor = PCB_BOTTOM-10-2.5-math.sqrt(10.795**2-(CELLS[1][0]-PCB_CENTER[0])**2)
    bottom = CELLS[1][1]-10.7
    ax.annotate(f'{bottom-floor:.2f} mm floor gap',xy=(CELLS[1][0],(floor+bottom)/2),xytext=(23,-28.3),
                fontsize=9,arrowprops=dict(arrowstyle='->',color='#28334A',lw=.8))
    fig.savefig(dest/'midspan-fit-2p5mm.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw()
