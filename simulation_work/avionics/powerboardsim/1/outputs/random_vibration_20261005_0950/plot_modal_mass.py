from rv_paths import *
import csv,json,itertools
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ma=json.loads((R/'modal_basis/audit.json').read_text())
fig,ax=plt.subplots(figsize=(7.6,3.1),layout='constrained')
ax.axvspan(20,2000,color='#166979',alpha=.075,label='Input PSD range')
for axis,color in [('X','#b85034'),('Y','#166979'),('Z','#17354b')]:
 rows=list(csv.DictReader((R/'modal_basis'/('participation_'+axis+'.csv')).open()))
 vals=list(itertools.accumulate(float(r['fraction_of_total_mass'])*100 for r in rows))
 assert abs(vals[-1]/100-ma['effective_mass_fraction'][axis])<1e-10
 freq=[float(r['frequency_hz']) for r in rows]
 ax.step([0,*freq,4000],[0,*vals,vals[-1]],where='post',lw=1.7,color=color,label=f'{axis}: {vals[-1]:.2f}% retained')
ax.set(xlim=(0,4000),ylim=(0,100),xlabel='Frequency (Hz)',ylabel='Cumulative effective mass (%)')
ax.grid(alpha=.2);ax.legend(loc='lower right',fontsize=8)
fig.savefig(R/'modal_effective_mass.pdf');fig.savefig(R/'modal_effective_mass.png',dpi=180)
