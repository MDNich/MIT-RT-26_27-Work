"""Make the numerical tables and PGF/pdfLaTeX figures in the team's palette."""
import sys
from pathlib import Path

from evaluate import ROOT,OUT,read,col
sys.path.insert(0,str(ROOT))
from plots import plt, BLUE, RED, GREEN, ORANGE, save
import numpy as np

W = ROOT/'docs/writeup'

def tex(name, rows):
    (W/(name+'.tex')).write_text(''.join(' & '.join(map(str,row))+r' \\'+'\n' for row in rows))

scores={(r['case'],int(r['angle']),r['model']):float(r['cp_rms_D']) for r in read(OUT/'native-scores.csv')}
names={'A-straight':'A, straight','A-step':'A, internal step','A-boattail':'A, boattail','A-flare':'A, flare',
       'B-straight':'B, straight','B-boattail':'B, boattail','B-flare':'B, flare','B-finned-straight':'B, finned straight',
       'B-finned-boattail':'B, finned boattail','C-finned-straight':'C, finned straight','C-finned-boattail':'C, finned boattail',
       'forebody':'Iris, truncated forebody','finless':'Iris, stepped finless','finned':'Iris, stepped finned',
       'Iris-constant-finless':'Iris, straight finless','Iris-constant-finned':'Iris, straight finned'}
models=('previous','narrow','combined')
tex('afterbody-static',[(display,*[f'{scores[case,a,m]:.2f}' for a in (0,2,4) for m in models]) for case,display in names.items()])
pairs=read(OUT/'paired-increments.csv')
tex('afterbody-pairs',[(names[case],*[f"{float(next(x[k] for x in pairs if x['variant']==case and x['angle']=='2' and x['model']==m)):.4f}"
                                         for k in ('delta_cn_rms_error','delta_J_rms_error') for m in models])
                       for case in ('A-step','A-boattail','A-flare','B-boattail','B-flare','B-finned-boattail','C-finned-boattail','finless','finned')])
display={'previous':'Prior blend','narrow':'Boattail + equal tubes','combined':'All three methods','RASAero':'RASAero II'}
events=read(OUT/'iris-flight.csv')
tex('afterbody-flight',[(display[r['model']],*[f"{float(r[k]):.3f}" for k in ('burnout_cal','minimum_cal','minimum_s','rms_cal','bias_cal')]) for r in events])

cases=('A-boattail','B-boattail','B-finned-boattail','C-finned-boattail')
fig,ax=plt.subplots(1,2,figsize=(8.5,3.05),gridspec_kw={'width_ratios':[1,1.12]})
fig.subplots_adjust(left=.08,right=.99,top=.86,bottom=.27,wspace=.33)
x=np.arange(len(cases))
for j,(mode,color,label) in enumerate([('previous',RED,'Prior blend'),('narrow',BLUE,'Boattail + equal tubes')]):
    ax[0].bar(x+(j-.5)*.34,[scores[c,0,mode] for c in cases],width=.32,color=color,label=label)
ax[0].set(xticks=x,xticklabels=['A\nbare','B\nbare','B\nfinned','C\nfinned'],ylabel='CP RMS error ($D$)',title=r'Boattails, $M=1.5$--3, $\alpha=0^\circ$')
ax[0].legend(fontsize=7.5,frameon=False)
for key,path,color,style,label in [('ras',next((ROOT/'inputs/native-afterbody/iris-flight').glob('*.csv')),'black','-','RASAero II'),
                                   ('previous',ROOT/'results/transfer-preferred-candidate.csv.gz',RED,'--','Prior blend'),
                                   ('combined',ROOT/'results/afterbody-preferred-candidate.csv.gz',GREEN,'-.','All three methods')]:
    rows=read(path)
    t=col(rows,'Time (sec)' if key=='ras' else 'time_s')
    v=col(rows,'Stability Margin (cal)' if key=='ras' else 'margin_cal')
    idx=(t>15.51)&(t<20.78)
    ax[1].plot(t[idx],v[idx],color=color,ls=style,label=label)
ax[1].set(xlabel='Flight time (s)',ylabel='Stability margin (cal)',title='Iris sustainer burn',xlim=(15.5,20.8))
ax[1].legend(fontsize=7.5,frameon=False)
save(fig,'afterbody-comparison')
