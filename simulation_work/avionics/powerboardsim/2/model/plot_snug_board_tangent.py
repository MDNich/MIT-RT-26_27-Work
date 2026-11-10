"""Compare native PCB displacement at bolt lock and the small-load lateral flexibility at that state."""
import numpy as np

from film_identity import digest, write_json
from report_plot import plt
from snug_board_pull import AUDIT, BRANCHES, ROOT, read


def compare():
    checks={}
    sources={}
    data={}
    bare=None
    for branch in BRANCHES:
        file=AUDIT/f'{branch}_full_board_tangent.json'
        row=read(file)
        sources[file.name]=digest(file)
        assert row['branch']==branch and row['cell_order']==['left','middle','right']
        diag=np.diag(row['cell_X_um_per_N'])
        if bare is None:
            bare=diag
        prior=read(AUDIT/f'{branch}_cell_flexibility.json')
        assert prior['basis_sha256']==row['basis_rst_sha256']
        checks[branch]=dict(loaded_cell_X_um_per_N=diag.tolist(),
                loaded_cell_travel_change_pct=(100*(diag/bare-1)).tolist(),
                left_relative_to_clamps_um_per_N=row['left_relative_to_its_clamps_X_um_per_N'][0],
                left_relative_roll_um_per_N=row['left_relative_roll_X_um_per_N'][0],
                retained_minus_full_relative_pct=row['four_kHz_minus_full_relative_pct'])
        data[branch]=row
    pcb={}
    for branch in BRANCHES[1:]:
        f=ROOT/'validation/static'/f'{branch}_static.json'
        s=read(f)
        sources[f.name]=digest(f)
        for model in ('bare',branch):
            r=s['models'][model+'_static']
            assert r['source_rst_sha256']==data[model]['static_rst_sha256']
            value=1000*r['scopes']['pcb']['peak_total_U_mm']
            assert model not in pcb or pcb[model]==value
            pcb[model]=value
    mesh_checks={}
    for nominal in BRANCHES[1:]:
        fine=AUDIT/f'{nominal}_mesh15_full_board_tangent.json'
        if not fine.is_file():
            continue
        ref=data[nominal]
        row=read(fine)
        assert row['branch']==nominal+'_mesh15' and row['force_cards_sha256']==ref['force_cards_sha256']
        assert row['basis_rst_sha256']!=ref['basis_rst_sha256']
        sources[fine.name]=digest(fine)
        R=np.diag(row['cell_X_um_per_N'])
        mesh_checks[nominal]=dict(fine_loaded_cell_X_um_per_N=R.tolist(),
            fine_change_vs_bare_pct=(100*(R/bare-1)).tolist(),
            fine_change_vs_nominal_pct=(100*(R/np.diag(ref['cell_X_um_per_N'])-1)).tolist(),
            fine_left_relative_to_clamps_um_per_N=row['left_relative_to_its_clamps_X_um_per_N'][0])
    write_json(AUDIT/'full_board_tangent_comparison.json',dict(inputs=sources,comparisons=checks,mesh_checks=mesh_checks,
        pcb_lock_displacement_um=pcb,scope='Separate unit loads on the three installed cells. Small motion about bolt lock.'))
    return pcb,checks


def draw():
    pcb,rows=compare()
    fig,axes=plt.subplots(1,2,figsize=(7.6,2.7),layout='constrained',sharey=True)
    labels=['Bare','Nylon','Aluminium']
    colors=['#08357E','#3C78D8','#38761D']
    for ax,values,title,unit,limit,fmt in [
            (axes[0],[pcb[b] for b in BRANCHES],'PCB after bolt lock',r'Peak displacement [$\mu$m]',59,'.1f'),
            (axes[1],[rows[b]['loaded_cell_X_um_per_N'][1] for b in BRANCHES],'Middle cell under lateral load',
             r'Centre travel per newton [$\mu$m/N]',.65,'.3f')]:
        y=[2,1,0]
        bars=ax.barh(y,values,color=colors,height=.51)
        ax.bar_label(bars,labels=[format(v,fmt) for v in values],padding=4,fontsize=9)
        ax.set(yticks=y,yticklabels=labels,ylim=(-.55,2.55),xlim=(0,limit),xlabel=unit,title=title)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='x',alpha=.17)
        ax.set_axisbelow(True)
    fig.savefig(ROOT/'docs/figures/snug-installed-lateral-response.pdf',
                metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw()
