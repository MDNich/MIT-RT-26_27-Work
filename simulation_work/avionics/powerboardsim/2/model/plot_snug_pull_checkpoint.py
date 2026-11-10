"""Plot the matched forward-pull comparison at the load reached by the bare fixture."""
from audit_local import ROOT, read
from compare_pull import series
from film_identity import verified
from report_plot import plt
from stage_snug_fit import AUDIT

CASE = 'snug125_nylon_lateral_friction_locked_pin1_m15'
CHECKPOINT = AUDIT / (CASE + '_ls3_ss12_checkpoint.json')


def plot():
    record = read(CHECKPOINT)
    assert record['case'] == CASE and not record['completed']
    bare, baseline = series(record['bare_case'])
    assert bare['rst_sha256'] == record['bare_rst_sha256']
    endpoint = record['last_common_travel']['cased']
    final, = [r for r in record['states'] if r['native_set'] == endpoint['set']]
    assert final['within_screens'] and final['cell_force_N'] == endpoint['cell_force_N']
    rows = [r for r in record['states'] if r['within_screens'] and r['loadstep'] >= 2]
    load = record['equal_bare_endpoint_load']['bare']['cell_force_N']
    hit = record['equal_bare_endpoint_load']['cased']
    assert hit and hit['native_travel_mm'][0] <= hit['travel_mm'] <= hit['native_travel_mm'][1]
    onset=read(AUDIT/'directional_first_contact.json')
    verified(CHECKPOINT,onset['checkpoint_sha256'])
    fig, (cx, ax, bx) = plt.subplots(1, 3, figsize=(8.15, 2.5), layout='constrained',
                                    gridspec_kw={'width_ratios': [.85, 1.45, 1.12]})
    for y,direction in ((1,'positive_X'),(0,'negative_X')):
        cases=onset['directions'][direction]['meshes']['native_1.5_mm']['checks']
        values=[abs(force) for check in cases.values() for force in check['bare_reaction_N']]
        force=(min(values)+max(values))/2
        cx.hlines(y,0,force,color='#8EACD5',lw=2)
        cx.plot(force,y,marker='D',color='#08357E',ms=4)
        cx.annotate(f'{force:.2f} N',(force,y),xytext=(0,8),textcoords='offset points',
                    ha='center',fontsize=8)
    cx.set(xlim=(-.2,8.1),ylim=(-.55,1.65),yticks=[1,0],yticklabels=['Toward','Away'],
           xticks=[0,2,4,6,8],xlabel='Bare force magnitude [N]',title='First pocket contact')
    ax.plot([r['ux_mm'] for r in baseline], [r['cell_force_N'] for r in baseline],
            '.-', ms=3.2, lw=1.3, color='#08357E', label='Bare')
    ax.plot([r['travel_mm'] for r in rows], [r['cell_force_N'] for r in rows],
            'o-', ms=2.8, lw=1.4, color='#38761D', label='Nylon mount')
    ax.axhline(load, lw=.8, color='#777777', ls=':', zorder=-1)
    ax.scatter([hit['travel_mm'], baseline[-1]['ux_mm']], [load, load], marker='D',
               s=26, color='#7A0101', zorder=4)
    ax.set(xlabel='Travel toward middle cell [mm]', ylabel='Applied force [N]',
           xlim=(-.012,.522), ylim=(-.4,12.5), title='Travel at 8.54 N')
    ax.legend(loc='lower right', fontsize=8, frameon=False)
    ax.annotate('0.034 mm', (hit['travel_mm'],load), xytext=(7,6), textcoords='offset points', fontsize=8)
    ax.annotate('0.500 mm', (.5,load), xytext=(-3,6), ha='right', textcoords='offset points', fontsize=8)
    names=('Case screws','Fixed neighbour','Nickel clamps')
    vals=[final[k] for k in ('screw_support_resistance_N','neighbor_resistance_N','nickel_clamp_resistance_N')]
    bx.barh(names, vals, color=['#38761D','#3C78D8','#5A43A0'], height=.5)
    for i,v in enumerate(vals):
        bx.text(v+1.3,i,f'{v:.1f}',va='center', fontsize=9)
    bx.invert_yaxis()
    bx.set(xlim=(0,110), xlabel='Lateral support reaction [N]', title='Load paths at 0.207 mm')
    for a in (cx,ax,bx):
        a.title.set(color='#08357E',fontsize=11)
        a.tick_params(labelsize=9)
        a.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/snug-forward-pull.pdf', metadata={'CreationDate':None, 'ModDate':None})
    plt.close(fig)


if __name__ == '__main__':
    plot()
