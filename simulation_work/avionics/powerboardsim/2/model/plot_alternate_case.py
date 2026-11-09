"""Compare a transverse section of each housing at a common, centred cell-axis datum."""

import numpy as np
import shapely
from shapely.affinity import affine_transform
from shapely.plotting import patch_from_polygon
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from matplotlib.patches import Patch

from case_fit import ROOT
from fit_figure import CELLS, midspan
from report_plot import plt


def zphr_section():
    path = ROOT/'geometry/candidates/zphr-av-fcpbcase.STEP'
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone and reader.TransferRoots()
    result = BRepAlgoAPI_Section(reader.OneShape(), gp_Pln(gp_Pnt(0,0,0), gp_Dir(1,0,0)), True)
    assert result.IsDone()
    edges = TopExp_Explorer(result.Shape(), TopAbs_EDGE)
    lines = []
    while edges.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(edges.Current()))
        points = [curve.Value(t) for t in np.linspace(curve.FirstParameter(), curve.LastParameter(), 257)]
        lines.append(shapely.LineString(np.round([(p.Z(), p.Y()) for p in points], 8)))
        edges.Next()
    shapes = list(shapely.get_parts(shapely.polygonize(lines)))
    assert len(shapes) == 1
    return shapes[0]


def draw():
    fig, axes = plt.subplots(2,1,figsize=(6.9,3.3),layout='constrained',sharex=True,sharey=True)
    cobalt, green, red = '#8AAEE8', '#CEDFC4', '#9D3832'
    sections = [(midspan(), 0., 0., 'Balius', 23.876),
                (zphr_section(), 12.81139998, 10.7, 'Zphr', 25.62279996)]
    cells = [shapely.Point(x-CELLS[1][0], z-CELLS[1][1]).buffer(10.7, quad_segs=192) for x,z in CELLS]
    for ax, (local, centre, height, name, pitch) in zip(axes, sections, strict=True):
        case = affine_transform(local, [1,0,0,-1,-centre,height])
        ax.add_patch(patch_from_polygon(case,facecolor=cobalt,edgecolor='#567EB9',lw=.5))
        for cell in cells:
            ax.add_patch(patch_from_polygon(cell,facecolor=green,edgecolor='#28511a',lw=.8))
            overlap = case.intersection(cell)
            if overlap.area > 1e-4:
                ax.add_patch(patch_from_polygon(overlap,facecolor=red,edgecolor=red,lw=.45))
        ax.set(xlim=(-100,75), ylim=(-18,15), aspect='equal', ylabel='Height [mm]')
        ax.set_title(f'{name}  $\\cdot$  {pitch:.3f} mm pocket pitch', loc='left', color='#08357E', fontsize=10)
        ax.tick_params(labelsize=8)
    axes[1].set_xlabel('Across the battery row [mm]')
    fig.legend(handles=[Patch(facecolor=cobalt,label='Case section'),Patch(facecolor=green,edgecolor='#28511a',label='Cells'),
                        Patch(color=red,label='Geometric overlap')], loc='outside upper center',ncol=3,frameon=False,fontsize=9)
    fig.savefig(ROOT/'docs/figures/alternate-case-sections.pdf',metadata={'CreationDate': None,'ModDate': None})
    plt.close(fig)


if __name__ == '__main__':
    draw()
