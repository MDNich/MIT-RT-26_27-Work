"""Match interim distributed installation fields to the final combined native result and POST1 tables."""
import numpy as np

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from global_contact import histories
from installed_tab_gap import run as combined_gaps
from native_rst import read_rst


def reconcile(case,campaign):
    root=ROOT/'validation/partition_checks'/case
    snapshots=sorted(root.glob('*_history.json'))
    if not snapshots:return
    vault=ROOT/'.runtime/archive'/campaign/case
    ledger=read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
    files={f['name']:f['sha256'] for f in ledger['files']}
    for name in ['file.rst','board_drives.csv']:
        verified(vault/name,files[name])
    material=read(ROOT/'validation/installation_material'/(case+'.json'))
    support=read(ROOT/'validation/board_reactions'/(case+'.json'))
    assert support['rst_sha256']==material['rst_sha256']==files['file.rst']
    rows={a['native_set']:a for a in material['history']}
    reactions={a['native_set']:a for a in support['history']}
    post=table(vault/'board_drives.csv')
    rst=read_rst(vault/'file.rst')
    pairs={853:853,**{i:858 for i in range(880,884)}}
    for summary in snapshots:
        name=summary.name.removesuffix('_history.json')
        saved=read(summary)
        sources=root/(name+'_sources.json')
        assert digest(sources)==saved['manifest_sha256'] and saved['case']==case and saved['campaign']==campaign
        assert read(sources)['model_sha256']==files['model.inp']
        indices=[r['native_set']-1 for r in saved['history']]
        contact=histories(rst,pairs,indices)
        max_drive=max_gap=max_stress=0.
        max_area=0.
        for j,r in enumerate(saved['history']):
            k=r['native_set']
            assert abs(r['time']-rst.time_values[k-1])<1e-10
            assert rst._resultheader['ls_table'][k-1,0]==r['loadstep']
            block=post[post['set']==k]
            assert np.array_equal(block['foot'],range(4))
            max_drive=max(max_drive,float(np.abs(block['drive_N']-r['drive_N']).max()))
            assert np.allclose(r['fixed_face_net_force_N'],reactions[k]['net_force_N'],atol=1e-7)
            assert np.allclose(r['fixed_face_net_moment_Nm'],reactions[k]['net_moment_Nm'],atol=1e-8)
            for pair in pairs:
                assert contact[pair][j]==r['contact'][str(pair)]
            for field,data in r['material'].items():
                for actual,other in [('peak','all_'),('peak_over_2mm_away','away_')]:
                    diff=abs(data[actual]-rows[k][other+field])
                    assert np.isclose(data[actual],rows[k][other+field],rtol=2e-6,atol=1e-8)
                    if field.endswith('_MPa'):max_stress=max(max_stress,diff)
        assert max_drive<.001
        shape=root/(name+'_gap.json')
        if shape.is_file():
            interim=read(shape)
            assert interim['checkpoint_sha256']==digest(sources)
            last=indices[-1]+1
            combined=read(combined_gaps(case,campaign,[last]))['measurements'][str(last)]['subdivisions']
            for level,feet in interim['gaps'][str(last)]['levels'].items():
                for pair,rec in feet.items():
                    for key in ('minimum_gap_mm','maximum_gap_mm'):
                        max_gap=max(max_gap,abs(rec[key]-combined[level][pair][key]))
                    for key in ('projected_overlap_mm2','area_gap_le_50um_mm2','area_gap_le_zero_mm2'):
                        if key in rec:
                            max_area=max(max_area,abs(rec[key]-combined[level][pair][key]))
            assert max_area<1e-4
            assert max_gap<1e-5
        write_json(root/(name+'_combined_comparison.json'),dict(case=case,campaign=campaign,
            checkpoint_sha256=digest(sources),combined_rst_sha256=files['file.rst'],matched_sets=len(indices),
            max_drive_difference_N=max_drive,max_material_stress_difference_MPa=max_stress,
            max_extreme_gap_difference_mm=max_gap if shape.is_file() else None,
            max_footprint_area_difference_mm2=max_area if shape.is_file() else None))


if __name__=='__main__':
    import sys
    reconcile(*sys.argv[1:])
