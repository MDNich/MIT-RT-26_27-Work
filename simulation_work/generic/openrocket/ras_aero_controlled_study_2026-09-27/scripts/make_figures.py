from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'comparison-results.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','savefig.facecolor':'white'})
OR='#167d9a'; RAS='#c9553a'; REPLAY='#7956a4'
labels={'B01':'4 in / square','B02':'4 in / rough square*','B03':'4 in / bevel','B04':'2.26 in / square','B05':'2.26 in / bevel'}
fig,ax=plt.subplots(figsize=(8,3.3),layout='constrained')
yy=np.arange(5)
for j,m in enumerate(['I500T-14A','J570W']):
 vals=[x['delta_pct']['apogee_m'] for x in D if x['motor']==m]
 bars=ax.barh(yy+(j-.5)*.32,vals,.29,color=[OR,RAS][j],label=m.replace('-14A',''))
 for b,v in zip(bars,vals):ax.text(v-.45,b.get_y()+b.get_height()/2,f'{v:.1f}%',va='center',ha='right',fontsize=9)
ax.set_yticks(yy,list(labels.values()));ax.invert_yaxis();ax.set_xlim(-35,1);ax.set_xlabel('Apogee difference: 100 x (RASAero / MIT OR - 1), %');ax.axvline(0,color='#444',lw=.8);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);ax.legend(loc='lower left',frameon=False,ncol=2)
fig.savefig(R/'figures/apogee-difference.png',dpi=220);plt.close(fig)
def read(p):
 rows=list(csv.DictReader(p.open()));return {k:np.array([float(r[k]) for r in rows]) for k in rows[0] if k!='Stage'}
fig,axes=plt.subplots(2,2,figsize=(8,5.3),layout='constrained')
for ax,base in zip(axes.flat,['B01-smooth-square','B03-smooth-bevel','B04-slender-square','B05-slender-bevel']):
 s=read(R/'evidence'/(base+'-turbulent-J570W-same-state.csv'))
 # Follow coast branch only to avoid mixing equal Mach values at different heights.
 mask=(s['ras_thrust_N']==0)&(s['velocity_m_s']>30)
 ax.plot(s['ras_mach'][mask],s['ras_cd'][mask],color=RAS,label='RASAero')
 ax.plot(s['ras_mach'][mask],s['or_cd'][mask],color=OR,label='MIT OR at same Mach / altitude')
 ax.set_title(labels[base[:3]],fontsize=11);ax.set_xlabel('Mach');ax.set_ylabel('Drag coefficient');ax.set_ylim(bottom=0);ax.grid(alpha=.2)
axes[0,0].legend(fontsize=8,frameon=False)
fig.savefig(R/'figures/drag-comparison.png',dpi=220);plt.close(fig)
fig,axes=plt.subplots(2,2,figsize=(8,5.1),layout='constrained')
for ax,base in zip(axes.flat,['B01-smooth-square','B03-smooth-bevel','B04-slender-square','B05-slender-bevel']):
 for sub,fn,tc,hc,col,lab in [('openrocket',base+'-J570W.csv','Time','Altitude',OR,'MIT OR'),('rasaero',base+'-turbulent-J570W.csv','Time (sec)','Altitude (ft)',RAS,'RASAero'),('openrocket',base+'-J570W-ras-cd-replay.csv','Time','Altitude',REPLAY,'MIT OR + RAS drag')]:
  a=read(R/sub/fn);h=a[hc]*(.3048 if sub=='rasaero' else 1);end=np.argmax(h)+1
  ax.plot(a[tc][:end],h[:end],color=col,label=lab,lw=1.6,ls='--' if col==REPLAY else '-')
 ax.set_title(labels[base[:3]],fontsize=11);ax.set_xlabel('Time, s');ax.set_ylabel('Altitude AGL, m');ax.grid(alpha=.2)
axes[0,0].legend(fontsize=8,frameon=False)
fig.savefig(R/'figures/trajectory-diagnostic.png',dpi=220);plt.close(fig)
print('Saved three study figures.')
