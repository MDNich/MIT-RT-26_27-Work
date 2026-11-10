"""Compare the load path before and after the case engages the fixed middle cell."""
import numpy as np
from audit_local import ROOT,read
from compare_pull import series
from film_identity import digest,write_json
from report_plot import plt
from stage_snug_fit import AUDIT
from snug_local_checkpoint import CASE


def draw():
    stem=CASE+'_ls3_ss18'
    p=AUDIT/(stem+'_checkpoint.json');c=read(p)
    earlier=AUDIT/(CASE+'_ls3_ss12_checkpoint.json');before=read(earlier)
    assert c['input_sha256']==before['input_sha256'] and c['rst_sha256']!=before['rst_sha256']
    assert c['states'][:before['converged_sets']]==before['states']
    for suffix,key in [('nickel_strain','states'),('mount_reactions','states')]:
        old=read(AUDIT/(CASE+'_ls3_ss12_'+suffix+'.json'));new=read(AUDIT/(stem+'_'+suffix+'.json'))
        assert new['checkpoint_sha256']==digest(p) and old['checkpoint_sha256']==digest(earlier)
        a,b=old[key],new[key][:len(old[key])]
        if suffix=='nickel_strain':assert a==b
        else:
            for x,y in zip(a,b,strict=True):
                assert x['native_set']==y['native_set']
                for tab,other in zip(x['tabs'],y['tabs'],strict=True):
                    assert tab['pilot']==other['pilot']
                    for k in ('translation_XYZ_mm','force_XYZ_N','moment_XYZ_Nmm','peak_shank_fibre_MPa','minimum_opposing_load_N'):
                        np.testing.assert_allclose(tab[k],other[k],atol=1e-8,rtol=1e-8)
    src=AUDIT/(stem+'_fixed_targets.json');targets=read(src)
    assert targets['checkpoint_sha256']==digest(p)
    by_set={r['native_set']:r['possible_target_bodies'] for r in targets['loaded_states']}
    info=read(ROOT/'validation/rigid_case_drawdown.json')
    centres={i['STEP_body']:i['STEP_centre_mm'][0] for i in info['records'] if i['STEP_body'] in (4,19,15)}
    assert centres[4]<centres[19]<centres[15]
    rows=[r for r in c['states'] if r['loadstep']==3 and r['within_screens']]
    t=np.array([r['travel_mm'] for r in rows]);forces=np.array([r['cell_force_N'] for r in rows])
    group={k:[] for k in (15,19)}
    for r in rows:
        g=by_set.get(r['native_set'],{});assert all(k in ('15','19') for k in g)
        for k in group:group[k].append(g[str(k)]['force_N'][0] if str(k) in g else 0.)
        assert abs(sum(a[-1] for a in group.values())-r['neighbor_resistance_N'])<.01
    indices=np.flatnonzero(np.array(group[19])>0);i=int(indices[0]);assert i>0
    write_json(AUDIT/(stem+'_load_paths.json'),dict(case=CASE,earlier_sha256=digest(earlier),checkpoint_sha256=digest(p),
               agreed_prefix_sets=before['converged_sets'],fixed_targets_sha256=digest(src),
               middle_contact_travel_bracket_mm=t[i-1:i+1].tolist(),middle_contact_load_bracket_N=forces[i-1:i+1].tolist(),
               endpoint=dict(travel_mm=t[-1],cell_force_N=forces[-1],middle_cell_N=group[19][-1],right_cell_N=group[15][-1],
                             percent_to_fixed_middle=100*group[19][-1]/forces[-1])))
    _,bare=series(c['bare_case'])
    fig,(ax,bx)=plt.subplots(1,2,figsize=(7.7,2.7),layout='constrained')
    for a in (ax,bx):
        a.axvspan(t[i-1],t[i],color='#3C78D8',alpha=.12)
        a.set_xlim(.157,.271);a.set_xlabel('Left-cell travel [mm]')
        a.spines[['top','right']].set_visible(False)
        a.grid(axis='y',lw=.4,color='#dddddd')
    ax.plot(t,forces,'o-',color='#08357E',lw=1.5,ms=3,label='Applied')
    ax.plot(t,group[19],'s--',color='#38761D',lw=1.4,ms=3,label='Middle cell')
    ax.set_ylim(0,1790);ax.set_ylabel('Lateral force [N]')
    ax.legend(loc='upper left',fontsize=8,frameon=False)
    for field,label,color in [('screw_support_resistance_N','Case mounts','#08357E'),
                              ('nickel_clamp_resistance_N','Nickel clamps','#5A43A0')]:
        bx.plot(t,[r[field] for r in rows],'.-',color=color,lw=1.4,ms=4,label=label)
    bx.plot(t,group[15],'.-',color='#38761D',lw=1.4,ms=4,label='Right cell')
    bx.plot([r['ux_mm'] for r in bare],[r['cell_force_N'] for r in bare],ls=':',lw=1.4,color='#7A0101',label='Bare applied')
    bx.set_ylim(0,132);bx.legend(loc='upper left',ncol=2,fontsize=7.5,frameon=False)
    for a,title in zip((ax,bx),('Applied force and middle-cell reaction','Other load paths'),strict=True):
        a.set_title(title,fontsize=10.3,loc='left',color='#08357E')
    fig.savefig(ROOT/'docs/figures/snug-fixed-middle-pull.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
