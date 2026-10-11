"""Plot native solved shell fields; never synthesizes deformation or damage."""
from pathlib import Path
import sys,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
S=Path(__file__).resolve().parent.parent
case=sys.argv[1];D=S/'runtime'/case
assert not (D/'REJECTED_LOAD_HISTORY.json').exists(),'Rejected load history is diagnostic only'
assert (D/'LOAD_HISTORY_VERIFIED.json').exists(),'Require verified continuous load history'
audit=D/'ACCEPTED.json'
if not audit.exists():audit=D/'CONVERGED_STATES_AUDIT.json'
a=json.loads(audit.read_text())
h=np.atleast_1d(np.genfromtxt(D/'history.csv',delimiter=',',names=True))
row=int(sys.argv[2]) if len(sys.argv)>2 else len(h)-1
color_max=float(sys.argv[3]) if len(sys.argv)>3 else 1.0
assert 0 < color_max <= 1
suffix='_detail' if color_max != 1 else ''
j=int(h['step'][row])
mesh=json.loads((D/'mesh.json').read_text())
n=np.atleast_1d(np.genfromtxt(D/f'nodes_{j}.csv',delimiter=',',names=True))
e=np.atleast_1d(np.genfromtxt(D/f'damage_{j}.csv',delimiter=',',names=True))
xyz=np.column_stack([n[k] for k in ['x_mm','y_mm','z_mm']])
dis=np.column_stack([n[k] for k in ['ux_mm','uy_mm','uz_mm']])
conn=np.asarray(mesh['elements'],dtype=int)-1
assert np.array_equal(e['element'],np.arange(1,len(conn)+1))
assert np.array_equal(n['node'],np.arange(1,len(n)+1))
damage=np.maximum.reduce([e['damage_top'],e['damage_mid'],e['damage_bot']])
attachment=np.asarray(mesh['attachment'],dtype=int)-1
attachment=np.unique(attachment)
x=xyz[attachment];y=(xyz+dis)[attachment];xc=x.mean(0);yc=y.mean(0)
U,sv,Vt=np.linalg.svd((x-xc).T@(y-yc));R=Vt.T@U.T
if np.linalg.det(R)<0:Vt[-1]*=-1;R=Vt.T@U.T
def transform(v):return (v-xc)@R.T+yc
fiterr=float(np.max(np.linalg.norm(transform(x)-y,axis=1)))
plt.rcParams.update({'font.size':10,'axes.titlesize':12,'font.family':'DejaVu Sans'})
fig=plt.figure(figsize=(9.6,6.0));ax=fig.add_subplot(111,projection='3d')
poly=Poly3DCollection((xyz+dis)[conn],edgecolors=(.2,.2,.2,.12),linewidths=.12,cmap='magma',alpha=1)
poly.set_array(damage);poly.set_clim(0,color_max);ax.add_collection3d(poly)
theta=np.linspace(0,2*np.pi,49);ys=np.linspace(25.407,95.407,9)
shell=[]
for yb in ys:
    v=np.column_stack([10.803671+10.7*np.cos(theta),np.full_like(theta,yb),-11.822674+10.7*np.sin(theta)])
    shell.append(transform(v))
shell=np.asarray(shell)
ax.plot_wireframe(shell[:,:,0],shell[:,:,1],shell[:,:,2],color='#8b9298',alpha=.35,linewidth=.45,rstride=2,cstride=6)
for cy in [17.906999,102.907004]:
    v=np.column_stack([10.81234894+5.5626*np.cos(theta),cy+5.5626*np.sin(theta),np.full_like(theta,-1.197679)])
    ax.plot(v[:,0],v[:,1],v[:,2],color='#166979',linewidth=1.3)
v=np.vstack([xyz+dis,shell.reshape(-1,3)])
lo=v.min(0)-2;hi=v.max(0)+2
ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),zlim=(lo[2],hi[2]),
       xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)')
ax.set_box_aspect(hi-lo);ax.view_init(elev=22,azim=-65)
ax.set_title('Edge-battery attachment: solved damage and deformation\n'+
             f'Battery movement {h["ux_mm"][row]:.2f} mm; lateral reaction {abs(h["fx_N"][row]):.2f} N')
cb=fig.colorbar(poly,ax=ax,shrink=.65,pad=.06);cb.set_label('Maximum top/mid/bottom element-summary damage')
fig.text(.05,.04,'Converged state; deformation scale 1:1. Grey battery follows rigid attachment motion.\n750 N initial preload per washer; PCB compliance excluded. Damage is not element deletion.',fontsize=9,color='#333333')
fig.subplots_adjust(left=.01,right=.9,bottom=.12,top=.9)
out=S/'figures'/f'{case}_step{j}_assembly{suffix}.png';fig.savefig(out,dpi=220);plt.close(fig)
# Plan view of the lower-Y washer leg, use undeformed coordinates to locate damaged material.
cent=xyz[conn].mean(1)
mask=(np.array(mesh['region'])!='vertical')&(cent[:,1]<60)
fig,ax=plt.subplots(figsize=(7.0,5.5))
pc=PolyCollection(xyz[conn[mask],:2],array=damage[mask],cmap='magma',edgecolors=(.3,.3,.3,.2),linewidths=.25)
pc.set_clim(0,color_max);ax.add_collection(pc)
ax.plot(10.81234894+5.5626*np.cos(theta),17.906999+5.5626*np.sin(theta),'--',color='#4fbaad',lw=1.6,label='Washer outer edge')
ax.set(xlim=(2.7,18.9),ylim=(9.6,26.2),aspect='equal',xlabel='X (mm)',ylabel='Y (mm)',
       title=f'Nickel at washer: damage at {h["ux_mm"][row]:.2f} mm battery movement')
ax.legend(loc='lower left',fontsize=8,facecolor='white',framealpha=.9)
if color_max != 1:
    ax.text(10.81235,17.907,f'Detail scale\n0 to {color_max:g}\n\nUndeformed\ncoordinates',
            ha='center',va='center',fontsize=8,color='black')
fig.colorbar(pc,ax=ax,shrink=.88,label='Maximum surface/midplane summary damage')
fig.tight_layout();fig.savefig(S/'figures'/f'{case}_step{j}_washer{suffix}.png',dpi=220);plt.close(fig)
(S/'figures'/f'{case}_step{j}_provenance{suffix}.json').write_text(json.dumps(dict(case=case,row=row,step=j,
    nodal_file=str(D/f'nodes_{j}.csv'),element_file=str(D/f'damage_{j}.csv'),
    rigid_battery_fit_max_error_mm=fiterr,scale=1,color_range=[0,color_max],
    maximum_summary_damage=float(damage.max())),indent=2))
print(out)
