from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plots import *
def render():
 r=rows(R/'chart-groups.csv');cc=[BLUE,GREEN,'#6B4AA5'];lab=['Full','Scalar','Transfer']
 fig,axs=plt.subplots(1,2,figsize=(8,2.8),sharey=True);fig.subplots_adjust(top=.77,bottom=.20,wspace=.2)
 for angle,ax in zip([0,4],axs):
  x=np.arange(4)
  for i,l in enumerate(lab):
   scores=[float(next(v['rmse'] for v in r if v['model']==l and v['alpha']==str(angle) and v['split']==g and v['band']=='sup')) for g in ('fit','holdout','blind','confirmation')]
   ax.bar(x+.24*(i-1),scores,width=.23,color=cc[i],label=['Full finite wing','Scalar trial','DATCOM blend'][i])
  ax.set_xticks(x,['Fit','Reserved','Blind I','Final']);ax.set_title(r'$\alpha='+str(angle)+r'^\circ$')
 axs[0].set_ylabel('CP RMSE vs RASAero ($D$)')
 fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False)
 save(fig,'transfer-tests')
if __name__=='__main__':render()
