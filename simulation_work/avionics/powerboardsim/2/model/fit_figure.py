"""Draw the two assembled cross-sections from a slice through the imported STEP mesh."""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Circle,Rectangle,Patch
import numpy as np,pyvista as pv
ROOT=Path(__file__).resolve().parents[1]
m=np.load(ROOT/'.runtime/mesh/case_2.npz')
t=m['tets'][:,:4]
g=pv.UnstructuredGrid(np.c_[np.full(len(t),4),t],np.full(len(t),pv.CellType.TETRA),m['points'])
sec=g.slice(normal=(0,0,1),origin=(0,0,0)).triangulate()
tri=sec.faces.reshape(-1,4)[:,1:];xy=sec.points[tri][:,:,[0,1]]
fig,axes=plt.subplots(2,1,figsize=(7.2,4.0),layout='constrained',sharex=True,sharey=True)
for ax,h,label in zip(axes,[0,3],['Tabs flush','3 mm tab stand-off']):
    wall=xy.copy();wall[:,:,0]+=34.6075;wall[:,:,1]=-.55118-10-h-wall[:,:,1]
    ax.add_collection(PolyCollection(wall,facecolor='#8AAEE8',edgecolor='face',lw=.16))
    for center in [10.80367,34.697,58.555]:
        ax.add_patch(Circle((center,-11.822674),10.7,facecolor='#38761d',alpha=.23))
        ax.add_patch(Circle((center,-11.822674),10.7,fill=False,ec='#28511a',lw=1))
    ax.add_patch(Rectangle((0,-.55118),69.215,1.10236,color='#34343d'))
    ax.set_aspect('equal');ax.set(xlim=(-4,74),ylim=(-30,3),ylabel='Board Z [mm]');ax.set_title(label,loc='left',fontsize=10,color='#08357e')
axes[-1].set_xlabel('Board X [mm]');fig.legend(handles=[Patch(color='#8AAEE8',label='Printed case'),Patch(facecolor='#c8dbbc',edgecolor='#28511a',label='Cells'),Patch(color='#34343d',label='PCB')],loc='outside upper center',ncol=3,frameon=False,fontsize=9)
fig.savefig(ROOT/'docs/figures/midspan-fit.png',dpi=200);plt.close(fig)
