from pull_paths import *
import sys,json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.colors import Normalize
case=sys.argv[1];D=S/'runtime'/case;m=json.loads((D/'mesh.json').read_text());cfg=json.loads((D/'config.json').read_text())
n=np.genfromtxt(D/'nodal.csv',delimiter=',',names=True);pos=np.array([[x[k] for k in ['x_mm','y_mm','z_mm']] for x in n]);u=np.array([[x[k] for k in ['ux_mm','uy_mm','uz_mm']] for x in n]);conn=np.array(m['elements'])-1
q=np.genfromtxt(D/'element_top.csv',delimiter=',',names=True);qb=np.genfromtxt(D/'element_bottom.csv',delimiter=',',names=True) if (D/'element_bottom.csv').exists() else q
plastic=np.maximum(q['eppl'],qb['eppl']);stress=np.maximum(q['seqv_MPa'],qb['seqv_MPa']);mag=np.linalg.norm(u,axis=1)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelcolor':'#17354b','text.color':'#17354b'})
for what in ['deformation','plastic_zoom','mesh']:
 fig=plt.figure(figsize=(10,6),layout='constrained');ax=fig.add_subplot(111,projection='3d')
 if what=='deformation':
  p=pos+u;vals=mag[conn].mean(axis=1);norm=Normalize(0,max(vals));title='Local edge-battery study | actual deformation (scale 1:1)';lab='Displacement magnitude (mm)';lim=((0,23),(6,115),(-25,3))
 elif what=='plastic_zoom':
  p=pos+u;vals=plastic*100;norm=Normalize(0,max(vals));title='Nickel plastic strain near the lower washer | scale 1:1';lab='Equivalent plastic strain (%)';lim=((2,20),(8,28),(-8,1))
 else:
  p=pos;vals=np.array([0 if x=='clamp' else 1 if x=='flat' else 2 for x in m['region']]);norm=Normalize(0,2);title=f'Local shell mesh | {len(conn):,} nickel elements';lab='';lim=((1,21),(8,30),(-20,1))
 cmap=plt.get_cmap('viridis' if what=='mesh' else 'turbo')
 valid=np.ones(len(conn),bool) if what=='deformation' else p[conn].mean(axis=1)[:,1]<30
 poly=Poly3DCollection(p[conn[valid]],facecolors=cmap(norm(vals[valid])),edgecolors='#33444b' if what=='mesh' else 'none',linewidths=.15)
 ax.add_collection3d(poly)
 if what=='deformation':
  # Light cylinder is a geometric rigid-battery reference; shell displacement is native FE data.
  theta=np.linspace(0,2*np.pi,50);yy=np.array([25.407,95.407]);tt,ys=np.meshgrid(theta,yy)
  xs=10.803671+10.7*np.cos(tt);zs=-11.822674+10.7*np.sin(tt)
  ax.plot_surface(xs,ys,zs,color='#a6b7ad',alpha=.15,linewidth=0)
  ax.quiver(10.803671,60.407,-11.822674,8*cfg['sign'],0,0,color='#d44b36',linewidth=2,arrow_length_ratio=.25)
  ax.text(10.803671+9*cfg['sign'],60.407,-11.822674,'Applied X displacement',fontsize=9)
  ax.view_init(elev=24,azim=-68)
 else:ax.view_init(elev=30,azim=-62)
 ax.set(xlim=lim[0],ylim=lim[1],zlim=lim[2],xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)');ax.set_box_aspect([b-a for a,b in lim]);ax.set_title(title,pad=15)
 if what=='deformation':
  ax.set_axis_off();ax.text2D(.08,.03,'Grey cylinder: undeformed battery reference',transform=ax.transAxes,fontsize=9)
 else:
  from matplotlib.ticker import MaxNLocator
  for a in [ax.xaxis,ax.yaxis,ax.zaxis]:a.set_major_locator(MaxNLocator(4))
 if what!='mesh':
  cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),ax=ax,shrink=.72,pad=.05);cb.set_label(lab)
 for a in [ax.xaxis,ax.yaxis,ax.zaxis]:a.pane.fill=False
 fig.savefig(S/'figures'/f'{case}_{what}.png',dpi=220);plt.close(fig)
print('Saved',case)

from matplotlib.collections import PolyCollection
fig,ax=plt.subplots(figsize=(8,6),layout='constrained')
valid=np.array([r in ['flat','clamp'] for r in m['region']]) & (pos[conn].mean(axis=1)[:,1]<30)
p=pos+u;col=PolyCollection(p[conn[valid]][:,:,:2],array=plastic[valid]*100,cmap='turbo',edgecolors='none');ax.add_collection(col)
col.set_clim(0,max(plastic)*100);fig.colorbar(col,ax=ax,label='Equivalent plastic strain (%)',shrink=.85)
ax.add_patch(plt.Circle((10.81234894,17.906999),5.5626,fill=False,ls='--',lw=1.2,color='white'))
ax.set(xlim=(2.5,19.5),ylim=(9.7,26.2),xlabel='X (mm)',ylabel='Y (mm)',title='Flat nickel leg: washer footprint and plastic strain')
ax.set_aspect('equal');ax.text(.02,.02,'Dashed circle: nominal washer edge\nElement summaries, max(top, bottom)\nDeformed coordinates, scale 1:1',transform=ax.transAxes,fontsize=9,bbox=dict(facecolor='white',alpha=.9,edgecolor='none'))
fig.savefig(S/'figures'/f'{case}_plastic_plan.png',dpi=220);plt.close(fig)
