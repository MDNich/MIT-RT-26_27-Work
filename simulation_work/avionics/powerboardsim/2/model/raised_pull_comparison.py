"""Compare the same lateral displacement and the same applied force across three audited fixtures."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT,read
from compare_pull import series
from film_identity import digest,write_json


def compare():
    bare='bare_lateral_friction_locked'
    entries={'Bare board':series(bare)}
    studies={}
    for material in ('nylon','aluminium'):
        case='stand3_'+material+'_lateral_friction_locked_pin1'
        proof,rows=series(case)
        entries[material]=(proof,rows)
        root=ROOT/'validation'
        mat=read(root/'pull_material'/(case+'.json'))
        energy=read(root/'pulls'/(case+'_energy.json'))
        contact=read(root/'pulls'/(case+'_contact.json'))
        equal=read(root/'pulls'/('raised_'+material+'_work.json'))
        assert all(q['rst_sha256']==proof['rst_sha256'] for q in (mat,energy,contact,equal['work'][case]))
        crossings=list(mat['first_reference_crossings'].values())
        first=min(crossings,key=lambda a:a['native_set']) if crossings else None
        # The local 861 and 862 pairs join rigid hardware to PLA. The seat model
        # uses a separate, tighter screen for contact with the thin nickel shell.
        by_set=np.genfromtxt(root/'pulls'/(case+'_contact.csv'),delimiter=',',names=True,usecols=('native_set','pair','max_closed_corner_penetration_mm'))
        assert np.isclose(max(by_set['max_closed_corner_penetration_mm']),contact['max_closed_corner_penetration_mm'])
        assert set(by_set['pair'])=={861,862} and contact['max_closed_corner_penetration_mm']<.05
        studies[material]=dict(case=case,rst_sha256=proof['rst_sha256'],first_PLA_reference=first,
                stored_energy_sha256=digest(root/'pulls'/(case+'_energy.json')),contact=contact,
                matched_force_target_N=equal['target_cell_force_N'],matched_force_bracket=equal['cased_native_neighboring_states'],
                force_interpolation=equal['cased_interpolant'],all_PLA_crossings=mat['first_reference_crossings'])
    ref_x=np.array([v['ux_mm'] for v in entries['Bare board'][1]])
    last=min([ref_x[-1]]+[v['first_PLA_reference']['last_below_mm'] for v in studies.values() if v['first_PLA_reference']])
    compare_at={}
    for key,(proof,rows) in entries.items():
        x=np.array([v['ux_mm'] for v in rows]);assert np.allclose(x,ref_x,atol=1e-8,rtol=0)
        exact=np.flatnonzero(np.isclose(x,last,atol=1e-8,rtol=0));assert len(exact)==1
        index=int(exact[0])
        compare_at[key]=dict(**rows[index])
        if key!='Bare board':
            name=studies[key]['case']
            work=read(ROOT/'validation/pulls'/(name+'_energy.json'))['history']
            assert work[index]['native_set']==rows[index]['set']
            compare_at[key]['work']=work[index]
    fig,axes=plt.subplots(1,2,figsize=(7.8,2.95),layout='constrained')
    palette={'Bare board':'#08357E','nylon':'#3C78D8','aluminium':'#38761D'}
    for key,(proof,rows) in entries.items():
        x=np.array([v['ux_mm'] for v in rows])
        for ax,field,factor in zip(axes,('cell_force_N','nickel_peak_plastic_strain'),(1.,100.),strict=True):
            y=np.array([v[field] for v in rows])*factor
            cut=len(rows) if key=='Bare board' or not studies[key]['first_PLA_reference'] else int(np.searchsorted(x,last+1e-8))
            label=key if key=='Bare board' else key.capitalize()+' screws'
            ax.plot(x[:cut],y[:cut],'.-',color=palette[key],lw=1.55,ms=3.5,label=label)
            if cut<len(rows):ax.plot(x[cut-1:],y[cut-1:],'.--',color=palette[key],lw=1.4,ms=3.5)
    for ax,label in zip(axes,['Lateral cell force [N]','Peak nickel plastic strain [%]'],strict=True):
        ax.axvspan(*entries['nylon'][0]['pair_861']['contact_travel_bracket_mm'],color='#3C78D8',alpha=.12)
        ax.set(xlabel='Lateral cell travel [mm]',ylabel=label,xlim=(0,.51))
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.22)
    h,l=axes[0].get_legend_handles_labels();fig.legend(h,l,loc='outside lower center',ncol=3,frameon=False,fontsize=8)
    fig.savefig(ROOT/'docs/figures/raised-pull-comparison.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    write_json(ROOT/'validation/pulls/raised_screw_comparison.json',dict(bare_rst_sha256=entries['Bare board'][0]['rst_sha256'],
        last_common_state_before_PLA_crossing_mm=last,common_state=compare_at,variants=studies,
        scope='Native positive-X pull of the edge cell with fixed screw tops, both 3 mm cases and the unclad reference. '
              'The common-force values are interpolated within the recorded states, across first case contact.'))


if __name__=='__main__':compare()
