"""Plot matched bond loads and the simultaneous force paths at the middle cell."""
import argparse
import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from report_plot import plt
from snug_attachment_history import BRANCHES

LABELS = ('Bare board','Nylon screws','Aluminium screws')
COLORS = ('#08357E','#3C78D8','#38761D')


def compare(method):
    source = ROOT/'validation/snug125'
    checks = {}
    loads = np.empty((3,3))
    transfer = []
    for j,variant in enumerate(BRANCHES):
        for i,axis in enumerate('XYZ'):
            case = f'{variant}_{axis}_bond_'
            paths = [source/(case + key + '.json') for key in (method,'independent','exact')]
            current,common,exact = [read(path) for path in paths]
            for info in (current,common,exact):
                assert (info['variant'],info['axis'],info['samples'])==(variant,axis,9*65536+1)
                assert info['load_sha256']==common['load_sha256'] and info['basis_rst_sha256']==common['basis_rst_sha256']
                assert info['attachment_audit_sha256']==common['attachment_audit_sha256']
                assert max(info['relative_interface_vs_modal_inertia_L2'].values())<.0005
                assert info['modes_3500Hz']<info['modes']
            verified(ROOT/'validation/cell_attachment'/(variant+'.json'),current['attachment_audit_sha256'])
            value = current['largest_bond']['magnitude_N']
            shifts = dict(integration=exact['largest_bond']['magnitude_N']/common['largest_bond']['magnitude_N']-1,
                          modal_cutoff=current['largest_bond_3500Hz']['magnitude_N']/value-1)
            if method=='native':
                shifts['native_vs_independent']=value/common['largest_bond']['magnitude_N']-1
                assert abs(shifts['native_vs_independent'])<.005
            checks[case.rstrip('_')]=dict(method=method,source_sha256=[digest(p) for p in paths],relative_differences=shifts)
            loads[j,i]=value
            if axis=='Z':
                ends=current['middle_cell_at_its_largest_bond']
                contributions=np.array([ends[field] for field in ('governing_bond_xyz_N','opposite_bond_xyz_N','pocket_xyz_N')])
                total=np.array(ends['all_interfaces_xyz_N'])
                assert np.allclose(contributions.sum(axis=0),total,atol=1.e-9)
                transfer.append([*contributions[:,0],total[0]])
    fig, (ax,mid)=plt.subplots(1,2,figsize=(8,3.05),layout='constrained')
    for j,(label,color) in enumerate(zip(LABELS,COLORS,strict=True)):
        dx=(j-1)*.24
        ax.bar(np.arange(3)+dx,loads[j],width=.22,color=color,label=label)
        mid.bar(np.arange(4)+dx,transfer[j],width=.22,color=color)
    ax.set(xticks=range(3),xticklabels=['Base X','Base Y','Base Z'],ylabel='Dynamic force magnitude [N]',
           title='Largest load at a single nickel bond',ylim=(0,85))
    mid.set(xticks=range(4),xticklabels=['Peak bond','Other bond','Pocket','Sum'],ylabel='Signed force along PCB X [N]',
            title='Middle-cell load paths under base Z')
    mid.axhline(0,color='#303030',lw=.7)
    for panel in (ax,mid):
        panel.tick_params(axis='x',labelsize=9)
        panel.grid(axis='y',alpha=.18)
        panel.set_axisbelow(True)
        panel.spines[['top','right']].set_visible(False)
    fig.legend(*ax.get_legend_handles_labels(),loc='outside lower center',ncol=3,frameon=False)
    out=ROOT/'docs/figures/snug-attachment-history.pdf'
    fig.savefig(out,metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    write_json(source/'bond_history_comparison.json',dict(method=method,checks=checks,
               peak_bond_N_rows_bare_nylon_aluminium_columns_XYZ=loads.tolist(),
               base_Z_simultaneous_middle_cell_X_N_rows_bare_nylon_aluminium=transfer,
               scope='Peak vector magnitude over six bonds and every sample of the given nine-second record. '
                     'Signed PCB-X components on the right use each assembly\'s own instant of maximum middle-cell '
                     'bond force under Z excitation. Independent exact-input and modal-cutoff checks use the same bonds.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--method',choices=('independent','native'),default='independent')
    compare(p.parse_args().method)
