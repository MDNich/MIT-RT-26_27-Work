"""Compare a fresh nominal bare damage pull to October over their shared physical travel."""
import argparse
import hashlib

import numpy as np
from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json


def measured_curve(rows):
    assert np.array_equal(rows['set'],np.arange(1,len(rows)+1))
    assert np.all(np.diff(rows['time'])>0) and np.all(rows['substep']!=999999)
    locked=np.flatnonzero(rows['loadstep']==2)
    assert len(locked) and abs(rows['time'][locked[-1]]-2.)<1.e-8
    curve=rows[locked[-1]:]
    assert abs(curve['ux_mm'][0])<1.e-9 and np.all(np.diff(curve['ux_mm'])>0)
    assert np.max(abs(curve['ux_mm']-(curve['time']-2)))<1e-6
    return curve


def overlap(original,repeat):
    original=measured_curve(original);repeat=measured_curve(repeat)
    first=max(original['ux_mm'][0],repeat['ux_mm'][0]);last=min(original['ux_mm'][-1],repeat['ux_mm'][-1])
    assert last>first
    grid=np.unique(np.r_[original['ux_mm'],repeat['ux_mm']]);grid=grid[(grid>=first)&(grid<=last)]
    assert grid[0]==first and grid[-1]==last
    values={}
    for field in ['fx_N','clamp1_N','clamp2_N','peeq','damage']:
        a,b=[np.interp(grid,rows['ux_mm'],rows[field]) for rows in (original,repeat)]
        diff=np.abs(a-b);ix=diff.argmax();norm=np.max(abs(a))
        values[field]=dict(max_absolute_difference=float(diff[ix]),location_mm=float(grid[ix]),
                max_difference_over_reference_peak=float(diff[ix]/norm) if norm else None,
                reference_at_common_end=float(a[-1]),repeat_at_common_end=float(b[-1]))
    same=len(original)==len(repeat) and np.allclose(original['ux_mm'],repeat['ux_mm'],rtol=0,atol=1.e-8)
    return dict(common_travel_mm=[float(first),float(last)],same_saved_pull_grid=bool(same),common_grid_points=len(grid),
                October_last_mm=float(original['ux_mm'][-1]),repeat_last_mm=float(repeat['ux_mm'][-1]),fields=values)


def compare(case,campaign,plot=False):
    assert case=='bare_damage_cont_nominal'
    root=ROOT/'validation'
    ref=read(root/'october_damage_reference.json')
    oct_csv=root/'pull_repeats/october_damage_nominal_inventory.csv'
    # Git stores the table as LF text. Rebuild the original Windows line endings for the archive check.
    archive_bytes=oct_csv.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    if hashlib.sha256(archive_bytes).hexdigest()!=ref['source_hashes']['set_inventory.csv']:
        raise ValueError('October set inventory differs from the verified archive')
    old=table(oct_csv)
    assert len(old)==ref['converged_native_sets']
    assert np.isclose(old['damage'].max(),ref['peak_damage'],atol=1.e-9)
    receipt=ROOT/'.runtime/receipts'/campaign/case
    assert (receipt/'released.txt').is_file()
    ledger=read(receipt/'archived.json');assert ledger['case']==case and ledger['campaign']==campaign
    folder=ROOT/'.runtime/archive'/campaign/case
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    source=read(root/'local_inputs.json')['damage_cont_nominal']['files']
    for name,prior in [('model.inp','run.dat'),('local_post.inp','post.dat')]:
        assert hashes[name]==source[prior]
        verified(folder/name,source[prior])
    verified(folder/'set_inventory.csv',hashes['set_inventory.csv'])
    new=table(folder/'set_inventory.csv')
    paths=[root/d/(case+'.json') for d in ('local','partial_local','review_local')]
    (accepted,)=[p for p in paths if p.is_file()]
    proof=read(accepted);assert proof['rst_sha256']==hashes['tear.rst'] and proof['campaign']==campaign
    maps=root/'damage_footprint'/(case+'.json');verified(maps,proof['damage_footprint_sha256'])
    fresh=read(maps);orig=read(root/'damage_footprint/october_nominal.json')
    assert fresh['mesh_sha256']==orig['mesh_sha256'] and fresh['threshold']==orig['threshold']
    assert fresh['inventory_sha256']==hashes['set_inventory.csv']
    assert orig['rst_sha256']==ref['source_hashes']['tear.rst']
    report=overlap(old,new)
    report['all_pull_section_exports_byte_identical']=(
        fresh['per_state_field_hash_manifest_sha256']==orig['per_state_field_hash_manifest_sha256'])
    report['original_damage_map_sha256']=digest(root/'damage_footprint/october_nominal.json')
    report.update(case=case,campaign=campaign,original_source_sha256=ref['source_hashes']['tear.rst'],repeat_rst_sha256=hashes['tear.rst'],
            original_inventory_sha256=ref['source_hashes']['set_inventory.csv'],repeat_inventory_sha256=hashes['set_inventory.csv'],
            repeat_audit_sha256=digest(accepted),damage_map_sha256=digest(maps),requested_path_completed=proof['full_requested_path'],
            original_onset=ref['damage_onset_bracket'],repeat_onset=proof['damage_onset_bracket'],
            original_sets=len(old),repeat_sets=len(new),
            scope='Comparison of two native runs with identical nominal fixture, loading and damage decks. '
                  'Force, clamp reactions, plastic strain and section damage are evaluated only over shared travel. '
                  'Differing saved increments use piecewise linear interpolation.')
    write_json(root/'pull_repeats'/(case+'.json'),report)
    print(case,report['common_travel_mm'],report['fields']['fx_N'],flush=True)
    if plot:
        plot_comparison(old,new,ref['damage_reporting_threshold'])


def plot_comparison(original,repeat,threshold):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig,(force,damage)=plt.subplots(1,2,figsize=(7.7,2.25),layout='constrained')
    curves=[measured_curve(original),measured_curve(repeat)]
    onset_windows=[]
    for curve in curves:
        hits=np.flatnonzero(curve['damage']>threshold)
        if len(hits):
            onset_windows.append(curve['ux_mm'][max(0,hits[0]-2)])
    start=min(onset_windows)
    for curve,label,color,repeat_run in zip(curves,['October','Repeat'],['#08357E','#38761D'],[False,True],strict=True):
        travel=curve['ux_mm']
        # Markers retain the saved equilibria when the two native curves coincide.
        force.plot(travel,curve['fx_N'],color=color,label=label,linewidth=1.3,
                   linestyle='none' if repeat_run else '-',marker='o' if repeat_run else None,
                   markevery=5,markersize=3,markerfacecolor='none')
        window=travel>=start
        damage.plot(travel[window],curve['damage'][window],color=color,label=label,linewidth=1.3,
                    linestyle='none' if repeat_run else '-',marker='o' if repeat_run else '.',
                    markersize=4,markerfacecolor='none' if repeat_run else color)
    force.set_ylabel('Pull reaction [N]')
    damage.set_ylabel('Peak section damage')
    damage.axhline(threshold,linestyle=':',color='#777777',linewidth=1,label='Reporting threshold')
    force.set_ylim(bottom=0)
    for ax in (force,damage):
        ax.set_xlabel('Cell travel [mm]')
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.17)
        ax.legend(frameon=False,fontsize=8,loc='upper left')
    fig.savefig(ROOT/'docs/figures/bare-nominal-damage-repeat.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case');p.add_argument('--campaign',default='nov08_01')
    p.add_argument('--plot',action='store_true')
    a=p.parse_args();compare(a.case,a.campaign,a.plot)
