from analyze import *
from itertools import groupby
from shutil import copyfile
W=D/'docs/writeup'; S=D/'docs/slides'
def tex(name,rs):
    (W/(name+'.tex')).write_text(''.join(' & '.join(map(str,r))+r' \\'+'\n' for r in rs))
fmt=lambda v:f'{float(v):.2f}'
lab={'fit':'Trial','finite':'Full','legacy':'Legacy','RAS':'RASAero II','charts':'Charts','transfer':'DATCOM blend'}
gt=rows(R/'group-metrics.csv')
def get(z,**k):return next(r for r in z if all(r[key]==str(val) for key,val in k.items()))
tex('groups',[(s.title(),a,*[fmt(get(gt,split=s,alpha=a,band='sup',model=m)['rmse']) for m in ('legacy','finite','fit')]) for s in ('fit','holdout','blind','control') for a in (0,2,4)])
ct=rows(R/'case-metrics.csv');gg=rows(R/'geometry.csv')
tex('matrix',[(r['case'],r['split'],f"{float(r['D_in']):g}",f"{float(r['nose_in']):g}/{float(r['body_in']):g}",r['count'],f"{float(r['root']):g}/{float(r['tip']):g}",f"{float(r['span']):g}/{float(r['sweep']):g}",*[fmt(get(ct,case=r['case'],model=m,band='sup',alpha=0)['rmse']) for m in ('legacy','finite','fit')]) for r in gg])
t=rows(R/'tunnel-metrics.csv');tex('tunnel-table',[(r['vehicle'],lab[r['model']],*[fmt(r[key]) for key in ('cp_rmse','cna_rmse','moment_rmse')]) for r in t])
fs=rows(R/'iris-events.csv')
tex('events',[(lab[r['model']],f"{float(r['mach']):.3f}",f"{float(r['cg_m']):.4f}",f"{float(r['cp_m']):.4f}",fmt(r['margin']),fmt(r['min_margin']),fmt(r['min_time'])) for r in fs])
e=rows(R/'iris-errors.csv')
tex('replay-table',[(r['test'].split(': ')[1],lab[r['model']],r['points'],fmt(r['cp_bias']),fmt(r['cp_rms'])) for r in sorted([z for z in e if z['test'].startswith('replay')],key=lambda r:r['test'])])
de=rows(R/'body-fin-audit.csv')
tex('body-table',[(r['case'],lab.get(r['model'],r['model']),*[fmt(r[v]) for v in ('body_N','body_X','added_N','added_X')]) for r in de if r['mach']=='2.5' and r['case'] in ('Hsq','wide-unswept','short-span') and r['model'] in ('RAS','finite','fit')])
for path in (W,S):
    (path/'figures').mkdir(exist_ok=True)
    for f in (D/'figures').glob('*.pdf'):copyfile(f,path/'figures'/f.name)
