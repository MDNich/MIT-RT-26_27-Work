"""Show the native bare damage-law control alongside the three sealed initiation curves."""
import numpy as np

from compare_pull_laws import loading_curve
from film_identity import verified
from report_plot import plt
from snug_damage_family import AUDIT,INPUTS,NOMINAL,ROOT,law,read,result_file


def draw():
    r,identity=loading_curve('bare',True)
    bare=read(result_file(identity['case']))
    lo,hi=bare['damage_onset_bracket']
    assert bare['damage_reporting_threshold']==1e-4
    assert lo['damage']<=1e-4<hi['damage']
    for v in (lo,hi):
        station,=r[r['native_set']==v['native_set']]
        assert abs(station['ux_mm']-v['cell_ux_mm'])<1e-9 and abs(station['cell_fx_N']-v['cell_fx_N'])<1e-6
    series=read(AUDIT/'damage_family_inputs.json')['cases']['snug125_nylon']
    fig,(force,criterion,damage)=plt.subplots(1,3,figsize=(8.2,2.12),layout='constrained')
    force.plot(r['ux_mm'],r['cell_fx_N'],color='#08357E',lw=1.5)
    x=[v['cell_ux_mm'] for v in (lo,hi)];y=[v['cell_fx_N'] for v in (lo,hi)]
    force.scatter(x,y,marker='o',s=17,edgecolors='#7A0101',facecolors='white',zorder=3)
    force.annotate(r'First $D>10^{-4}$',xy=(x[1],y[1]),xytext=(.8,40),fontsize=8,
                   arrowprops=dict(arrowstyle='->',lw=.65,color='#7A0101'),color='#7A0101')
    force.set(xlabel='Cell travel [mm]',ylabel='Lateral force [N]',xlim=(0,3.55),ylim=(0,49),title='Bare-board pull')
    for source,color in [('damage_cont_e10u12','#3C78D8'),(NOMINAL,'#08357E'),('damage_cont_e60u12','#38761D')]:
        entry=series[source];path=INPUTS/entry['case']/'model.inp'
        verified(path,entry['input_sha256'])
        (points,uf),_=law(path.read_bytes())
        assert uf==.12
        tension=points[:,0]>=0
        criterion.plot(points[tension,0],points[tension,1],'.-',lw=1.3,ms=3,color=color,
                       label=rf"$\varepsilon_0={entry['eps0']:.1f}$")
    criterion.set(xlabel=r'Stress triaxiality $\eta$',ylabel='Initiation strain',title='Initiation curves',
                  xlim=(0,2),ylim=(0,.66))
    criterion.legend(frameon=False,ncol=1,fontsize=7,loc='upper right',handlelength=1.3)
    record=read(AUDIT/'bare_damage_cont_nominal_nickel_evolution.json')
    assert record['native_rst_sha256']==identity['rst_sha256'] and record['reconstruction_checked_at_positive_damage']
    states=[record['first_positive_native_damage'][0],*record['native_damage_states']]
    assert states[-1]==record['last_supported'] and len(states)>2
    xs=[s['travel_mm'] for s in states]
    damage.plot(xs,[100*s['native_max_point_damage'] for s in states],'o-',color='#7A0101',ms=2.2,lw=1.2,label='Peak point')
    damage.plot(xs,[100*s['native_max_section_damage'] for s in states],'s--',color='#08357E',ms=2.2,lw=1.1,label='Peak section mean')
    damage.set(xlabel='Cell travel [mm]',ylabel=r'Damage $D$ [\%]',title='Bare nickel after initiation',xlim=(3.245,3.354),ylim=(0,3))
    damage.set_xticks([3.25,3.30,3.35])
    damage.legend(loc='upper left',frameon=False,fontsize=7,handlelength=1.3)
    for axis in (force,criterion,damage):
        axis.title.set_fontsize(10)
        axis.spines[['top','right']].set_visible(False)
        axis.grid(axis='y',alpha=.15)
    fig.savefig(ROOT/'docs/figures/snug-nickel-damage-controls.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw()
