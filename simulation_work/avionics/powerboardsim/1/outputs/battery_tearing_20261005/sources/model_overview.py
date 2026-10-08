"""Geometry-only overview from the sealed attachment mesh (not a solved result)."""
from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
S=Path(__file__).resolve().parent.parent
m=json.loads((S/'runtime/nominal_coarse/mesh.json').read_text())
xyz={int(k):v for k,v in m['nodes'].items()}; conn=m['elements'];verts=np.array([[xyz[n] for n in e] for e in conn])
fig=plt.figure(figsize=(10,5.8));ax=fig.add_subplot(111,projection='3d')
ax.add_collection3d(Poly3DCollection(verts,facecolors='#aab9c6',edgecolors='#536473',linewidths=.1,alpha=.9))
th=np.linspace(0,2*np.pi,65); yy=np.linspace(25.407,95.407,12)
v=np.array([np.column_stack([10.803671+10.7*np.cos(th),np.full_like(th,y),-11.822674+10.7*np.sin(th)]) for y in yy])
ax.plot_wireframe(v[:,:,0],v[:,:,1],v[:,:,2],color='#646b73',linewidth=.5,rstride=2,cstride=8,alpha=.45)
for cy in [17.906999,102.907004]:
 for dz in [-.15,.15]:
  ax.plot(10.81234894+5.5626*np.cos(th),cy+5.5626*np.sin(th),np.full_like(th,-1.197679+dz),color='#087e8b',lw=2)
ax.quiver(10.8,60.4,-11.8,15,0,0,color='#be4b34',arrow_length_ratio=.22,linewidth=2)
ax.text(25.8,60.4,-10,'+X pull',color='#be4b34',fontsize=10)
ax.set(xlim=(-2,29),ylim=(8,114),zlim=(-26,5),xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)')
ax.set_box_aspect((31,106,31));ax.view_init(elev=28,azim=-40)
ax.set_title('Local edge-battery attachment model',pad=0)
fig.text(.04,.065,'Grey: rigid battery surrogate. Silver: two 0.15 mm nickel strips.\nTeal: rigid washer/backing platens, initially clamped at 750 N each.\nGeometry view only. PCB compliance and battery-to-PCB contact are excluded.',fontsize=10)
fig.subplots_adjust(left=.01,right=.98,bottom=.18,top=.95)
fig.savefig(S/'figures/model_overview.png',dpi=200)
