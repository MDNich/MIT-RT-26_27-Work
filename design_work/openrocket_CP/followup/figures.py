"""Render the follow-up figures using the original study's Matplotlib PGF and pdfLaTeX setup."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plots import plt, BLUE, RED, GREEN, LIGHT, ORANGE, save, Line2D, D, R
import csv,gzip
import numpy as np
O=R/'followup'
def read(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return list(csv.DictReader(f))
styles={'transfer':(BLUE,'-','Prior blend'),'handover':(GREEN,'--','New handover'),'RAS':('#222222',':','RASAero II')}
def legend(fig):
    fig.legend(handles=[Line2D([],[],color=c,ls=ls,label=name) for c,ls,name in styles.values()],ncol=3,loc='upper center',frameon=False)
def plot_crossover():
    inc=read(O/'increments.csv');fig,axes=plt.subplots(1,2,figsize=(8,2.75))
    fig.subplots_adjust(left=.10,right=.99,top=.77,bottom=.21,wspace=.35)
    for ax,qty,ylabel,scale in zip(axes,['N','J'],[r'Installed-fin $C_N$',r'Installed-fin $C_{m,\rm nose}$'],[1,-1]):
        for model,(c,ls,_) in styles.items():
            z=[v for v in inc if v['model']==model and v['fixture']==('cdx' if model=='RAS' else 'ork') and v['term']=='installed fins' and float(v['alpha_deg'])==2 and float(v['mach'])<=2.30]
            x=np.array([float(v['mach']) for v in z]);y=scale*np.radians(2)*np.array([float(v[qty]) for v in z])
            ax.plot(x,y,color=c,ls=ls)
        ax.axvspan(1.74379366,2.00536271,color=LIGHT,alpha=.15);ax.axvline(2.26693176,color=ORANGE,lw=.8,ls=':')
        ax.set(xlabel='Mach number',ylabel=ylabel,xlim=(1.5,2.30))
    legend(fig);save(fig,'handover-loads')
    fig,ax=plt.subplots(figsize=(7.5,2.9));fig.subplots_adjust(top=.80,bottom=.20)
    for model,(c,ls,label) in styles.items():
        if model=='RAS':
            z=read(D/'inputs/native-iris-half/Iris-half-flight.csv');ts='Time (sec)';sm='Stability Margin (cal)'
        else:z=read(R/(model+'-preferred-candidate.csv.gz'));ts='time_s';sm='margin_cal'
        z=[v for v in z if 15.519<=float(v[ts])<=20.771]
        xx=np.array([float(v[ts]) for v in z]);yy=np.array([float(v[sm]) for v in z])
        ax.plot(xx,yy,ls=ls,color=c);k=yy.argmin();ax.plot(xx[k],yy[k],marker='o',color=c,ms=4)
    ax.set(xlabel='Time after booster ignition (s)',ylabel='Sustainer margin (cal)',xlim=(15.45,20.85));legend(fig);save(fig,'handover-flight')
def plot_components():
    r=read(O/'states.csv');fig,axes=plt.subplots(1,3,figsize=(8.5,2.55));fig.subplots_adjust(top=.72,bottom=.2,wspace=.37)
    for part,ax,title in zip(['forebody','finless','finned'],axes,['Bare forebody','Complete finless','Complete finned']):
        for mod,(color,ls,name) in styles.items():
            sel=[v for v in r if v['model']==mod and v['fixture']==('cdx' if mod=='RAS' else 'ork') and v['geometry']==part and float(v['alpha_deg'])==0]
            ax.plot([float(v['mach']) for v in sel],[float(v['cp_D']) for v in sel],color=color,ls=ls)
        ax.set(xlabel='Mach number',title=title);ax.ticklabel_format(useOffset=False,axis='y')
    axes[0].set_ylabel('CP aft of nose ($D$)');legend(fig);save(fig,'handover-components')
def plot_tunnel():
    rows=read(O/'tn-native.csv');fig,axes=plt.subplots(2,2,figsize=(7.5,4.3),sharex=True)
    fig.subplots_adjust(top=.82,bottom=.13,wspace=.28,hspace=.30)
    for j,mach in enumerate((1.50,2.02)):
        for i,metric in enumerate(('lift','moment')):
            ax=axes[i,j]
            for model,(c,ls,name) in list(styles.items())[:2]:
                z=[v for v in rows if v['model']==model and v['part']=='combined' and float(v['mach'])==mach]
                x=[.67,1.34,2.02,2.69,3.33,4.]
                ax.plot(x,[float(v['predicted_'+metric]) for v in z],color=c,ls=ls)
            for q,(a,v) in enumerate(zip(x,z)):
                ax.plot(a,float(v['measured_'+metric]),'o',ms=4,color='#222222',mfc='white' if q%2==0 else '#222222')
            if i==0:ax.set_title(f'Mach {mach:.2f}')
            if j==0:ax.set_ylabel([r'$C_{L\alpha}$ (/rad)',r'$C_{m\alpha}$ (/rad)'][i])
            if i==1:ax.set_xlabel('Full wing aspect ratio')
    handles=[Line2D([],[],color=c,ls=ls,label=name) for c,ls,name in list(styles.values())[:2]]
    for face,lab in [('white','Development'),('black','Reserved')]:handles.append(Line2D([],[],color='black',mfc=face,marker='o',ls='none',ms=4,label=lab))
    fig.legend(handles=handles,ncol=4,loc='upper center',frameon=False);save(fig,'handover-tn3795')
if __name__=='__main__':
    plot_crossover();plot_components();plot_tunnel()
