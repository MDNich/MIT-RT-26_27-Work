"""Every plotted mark is drawn by Matplotlib's PGF backend and typeset by pdfLaTeX."""
import os
from pathlib import Path
if Path('/Library/TeX/texbin').exists(): os.environ['PATH']='/Library/TeX/texbin:'+os.environ.get('PATH','')
import matplotlib as mpl
mpl.use('pgf')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from analyze import *
plt.rcParams.update({'pgf.texsystem':'pdflatex','pgf.rcfonts':False,'text.usetex':True,'font.family':'serif',
    'font.size':10,'axes.labelsize':10,'legend.fontsize':9,'axes.spines.right':False,'axes.spines.top':False,
    'axes.linewidth':.65,'axes.grid':True,'grid.alpha':.18,'axes.axisbelow':True,'lines.linewidth':1.55,
    'pgf.preamble':r'\usepackage[T1]{fontenc}\usepackage{lmodern}'})
F=D/'figures'; F.mkdir(exist_ok=True)
BLUE,RED,GREEN='#08357E','#7A0101','#38761D'
ORANGE,LIGHT,PURPLE='#B45F06','#6D9EED','#CC00AA'
colors=[RED,BLUE,GREEN];styles=['--','-','-.'];labels=['Legacy','Full finite wing','RAS fit']
def save(fig,name):
    fig.savefig(F/(name+'.pdf'),backend='pgf',bbox_inches='tight',pad_inches=.055)
    plt.close(fig)
def key(fig,refs=True):
    handles=[Line2D([],[],color=c,ls=s,label=l) for c,s,l in zip(colors,styles,labels)]
    if refs: handles.append(Line2D([],[],color='black',marker='o',ls='none',ms=3,label='RASAero II'))
    fig.legend(handles=handles,loc='upper center',ncol=len(handles),frameon=False,bbox_to_anchor=(.5,1.035))
def static():
    design,splits,data=load();k=float(rows(R/'fits.csv')[0]['k'])
    _,grid,scores=fit(data,design['fit'])
    fig,ax=plt.subplots(1,2,figsize=(8.0,2.85),gridspec_kw={'width_ratios':[1,1.25]})
    fig.subplots_adjust(wspace=.42,top=.87,bottom=.24)
    ax[0].plot(grid,scores,color=BLUE);ax[0].plot(k,scores[round(k*1000)],'o',color=GREEN)
    ax[0].annotate(r'$k=0.459$',(k,scores[459]),xytext=(5,14),textcoords='offset points')
    ax[0].set(xlabel=r'Fraction of adjustment $k$',ylabel='Training CP RMSE ($D$)',title='Five calibration geometries')
    groups=['fit','holdout','blind']; names=['Calibration','Reserved','Fresh blind'];x=np.arange(3)
    met=rows(R/'group-metrics.csv')
    for j,mod in enumerate(['legacy','finite','fit']):
        yy=[float(next(r['rmse'] for r in met if r['split']==g and r['alpha']=='0' and r['band']=='sup' and r['model']==mod)) for g in groups]
        ax[1].bar(x+(j-1)*.24,yy,width=.23,color=colors[j],label=labels[j])
    ax[1].set(xticks=x,xticklabels=names,ylabel='CP RMSE ($D$)',title=r'$M=1.50$--$3.00$, $\alpha=0^\circ$')
    ax[1].legend(loc='upper center',bbox_to_anchor=(.5,-.18),ncol=3,fontsize=8,frameon=False)
    save(fig,'calibration')
    fig,axs=plt.subplots(2,3,figsize=(8.5,4.3),sharex=True)
    fig.subplots_adjust(hspace=.43,wspace=.36,top=.87,bottom=.12);key(fig)
    samples=[('Hsq','Baseline'),('Hsq-span1.625','Shortened span'),('Ssq-unswept','Slender, unswept'),('short-span','Blind: short span'),('wide-unswept','Blind: wide, unswept'),('highly-swept','Blind: highly swept')]
    for idx,(ax,(n,title)) in enumerate(zip(axs.flat,samples)):
        m,x,N,y,Q,t,*_=data[n,0];s=(m>=.5)&(m<=3)
        for cp,c,ls in zip([x,y,mix(k,x,N,y,Q)],colors,styles):ax.plot(m[s],cp[s],color=c,ls=ls)
        ax.plot(m[s][::12],t[s][::12],'.',color='black',ms=3.5)
        ax.set_title(title,fontsize=10)
        if idx%3==0:ax.set_ylabel('Nose to CP ($D$)')
        if idx>=3:ax.set_xlabel('Mach number')
    save(fig,'planforms')
    fig,axs=plt.subplots(1,2,figsize=(7.4,2.65));fig.subplots_adjust(wspace=.33,top=.80,bottom=.18)
    tunnel=rows(R/'tunnel.csv')
    for i,(g,ax) in enumerate(zip(['ARCAS','Yuska-B'],axs)):
        r0=[r for r in tunnel if r['geometry']==g and r['model']=='legacy' and float(r['mach'])>=1.5]
        r1=[r for r in tunnel if r['geometry']==g and r['model']=='candidate' and float(r['mach'])>=1.5]
        col=lambda rows,c:np.array([float(r[c]) for r in rows]); m=col(r0,'mach')
        x=col(r0,'predicted_cp_d'); y=col(r1,'predicted_cp_d'); t=col(r0,'measured_cp_d')
        for cp,c,ls in zip([x,y,mix(k,x,col(r0,'predicted_cna'),y,col(r1,'predicted_cna'))],colors,styles):ax.plot(m,cp-t,color=c,ls=ls,marker='o',ms=3)
        ax.axhline(0,color='black',lw=.8);ax.set(xlabel='Mach number',title=g)
        if not i:ax.set_ylabel('CP error vs tunnel ($D$)')
    key(fig,False);save(fig,'tunnel')
if __name__=='__main__': static()
