"""Compare early flush-installation PCB deflection at the same screw travels on both native meshes."""
import argparse

import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from native_rst import read_rst
from partition_tab_gap import check_geometry, export


def compare(nylon_checkpoint, aluminium_checkpoint, campaign, plot=False):
    pairs_path = ROOT/'validation/installation_comparisons'/f'flush_{nylon_checkpoint}_{aluminium_checkpoint}.json'
    pairs = read(pairs_path)
    assert pairs['campaign'] == campaign
    ramp = pairs['common_states']
    assert ramp[0]['travel_mm'] == 0 and len(ramp) >= 2
    sources = pairs['sources']
    assert sources['aluminium']['checkpoint'] == aluminium_checkpoint and sources['nylon']['checkpoint'] == nylon_checkpoint
    nylon = sources['nylon']['case']
    alu = sources['aluminium']['case']
    reference = read(ROOT/'validation/global/stand3_aluminium_static.json')
    mesh_path = ROOT/'.runtime/archive'/campaign/'stand3_aluminium_static/file.rst'
    verified(mesh_path, reference['rst_sha256'])
    mesh = read_rst(mesh_path)
    grid = mesh.quadgrid
    board = grid.extract_cells(grid.cell_data['ansys_material_type'] == 208)
    folder = ROOT/'.runtime/partition_snapshots'/campaign/alu/aluminium_checkpoint
    verified(folder/'receipts.json', sources['aluminium']['source_sha256'])
    manifest = read(folder/'receipts.json')
    assert manifest['case'] == alu and manifest['campaign'] == campaign
    ids, ne = check_geometry(mesh, [board], folder, manifest)
    lock_proof_path = ROOT/'validation/pcb_installation'/(nylon+'.json')
    lock_proof = read(lock_proof_path)
    assert lock_proof['campaign'] == campaign and (len(ids),ne)==(lock_proof['PCB_nodes'],lock_proof['PCB_elements'])
    closed = ROOT/'.runtime/archive'/campaign/nylon/'file.rst'
    verified(closed, lock_proof['rst_sha256'])
    original = read_rst(closed)
    grid0 = original.quadgrid
    board0 = grid0.extract_cells(grid0.cell_data['ansys_material_type'] == 208)
    assert np.array_equal(np.sort(board0.cell_data['ansys_elem_num']), np.sort(board.cell_data['ansys_elem_num']))
    assert np.array_equal(np.unique(board0.point_data['ansys_node_num']), ids)
    xyz = mesh.mesh.nodes[positions(mesh.mesh.nnum,ids)]
    assert np.array_equal(original.mesh.nodes[positions(original.mesh.nnum,ids)],xyz)
    elements = np.sort(board.cell_data['ansys_elem_num'])
    def original_connectivity(raw):
        order = np.argsort(raw.mesh.enum)
        indices = order[positions(raw.mesh.enum[order],elements)]
        geometry = raw.mesh.elem
        return np.stack([geometry[i][10:] for i in indices])
    assert np.array_equal(original_connectivity(mesh), original_connectivity(original))
    fix = np.sort(mesh.mesh.node_components['_FIXEDSU'])
    bearings = np.arange(960101,960105)
    heads = np.arange(950002,950010,2)
    nodes = np.unique(np.r_[ids, fix, bearings, heads])
    sets = [r['aluminium']['native_set'] for r in ramp]
    disp, sha = export(folder, manifest, nodes, sets, aluminium_checkpoint+'_pcb_common')
    gap_path = ROOT/'validation/partition_checks'/alu/(aluminium_checkpoint+'_gap.json')
    gap = read(gap_path)
    assert gap['checkpoint_sha256']==sources['aluminium']['source_sha256']
    subset = ROOT/'.runtime/post'/campaign/alu/'partition_DPF'/aluminium_checkpoint
    req = read(subset/'request.json')
    verified(subset/'displacements.bin',gap['DPF_sha256'])
    check = np.fromfile(subset/'displacements.bin','<f8').reshape(len(req['sets']),len(req['nodes']),3)
    shared, here, there = np.intersect1d(nodes,req['nodes'],return_indices=True)
    assert len(shared)>1000
    index_sets = [req['sets'].index(s) for s in sets]
    gap_error = float(np.max(abs(disp[:,here] - check[index_sets][:,there])))
    assert gap_error < 1e-9 and abs(disp[:,positions(nodes,fix)]).max() < 1e-11
    archive_sets = [r['native_set'] for r in lock_proof['history']]
    archived = ROOT/'.runtime/post'/campaign/nylon/'dpf_u'/('sets_'+'_'.join(map(str,archive_sets)))
    a = disp[:,positions(nodes,ids),2]*1000
    a = a - a[0]
    b = disp[:,positions(nodes,bearings),2]*1000
    h = disp[:,positions(nodes,heads),2]*1000
    assert np.allclose(h-b, np.array([r['travel_mm'] for r in ramp])[:,None],rtol=0,atol=2e-7)
    results=[]
    for i,pair in enumerate(ramp):
        k = pair['nylon']['native_set']
        record = lock_proof['history'][archive_sets.index(k)]
        assert abs(record['travel_mm']-pair['travel_mm'])<1e-7
        stem=archived/f'set_{k:04d}'
        verified(stem.with_suffix('.ids'),record['node_ids_sha256'])
        verified(stem.with_suffix('.u'),record['displacement_sha256'])
        numbers=np.fromfile(stem.with_suffix('.ids'),'<i4')
        order=np.argsort(numbers)
        values=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)[order[positions(numbers[order],ids)],2]*1000
        if i==0:nylon_lock=values.copy()
        delta_nylon=values-nylon_lock
        assert np.isclose(delta_nylon.min(),record['min_incremental_Z_mm'],atol=1e-9)
        diff=a[i]-delta_nylon
        j=int(np.abs(diff).argmax()); peak=int(a[i].argmin())
        results.append(dict(travel_mm=pair['travel_mm'],nylon_set=k,aluminium_set=sets[i],
            nylon_peak_toward_cells_mm=-record['min_incremental_Z_mm'], aluminium_peak_toward_cells_mm=float(-a[i].min()),
            nylon_peak_node=record['min_node'],aluminium_peak_node=int(ids[peak]),aluminium_peak_xyz_mm=(xyz[peak]*1000).tolist(),
            nylon_bearing_toward_cells_mm=(-np.array(record['bearing_delta_Z_mm'])).tolist(),
            aluminium_bearing_toward_cells_mm=(b[0]-b[i]).tolist(),largest_abs_pointwise_change_mm=float(abs(diff[j])),
            aluminium_minus_nylon_at_that_node_mm_toward_cells=float(-diff[j]),maximum_change_node=int(ids[j])))
    result=dict(campaign=campaign,pcb_nodes=len(ids),elements=ne,sets=results,matched_load_record_sha256=digest(pairs_path),
        nylon_board_history_sha256=digest(lock_proof_path),aluminium_partition_sha256=sources['aluminium']['source_sha256'],
        aluminium_DPF_sha256=sha,aluminium_geometry_control_rst_sha256=reference['rst_sha256'],subset_control_sha256=digest(gap_path),
        subset_check_nodes=len(shared),subset_max_component_difference_m=gap_error,
        scope='Board-normal translations from the six-bolt locked state of each separate installation, on the same PCB nodes '
              'and connectivity. Comparisons cover common saved states before the native material and penetration screens.')
    write_json(ROOT/'validation/pcb_installation'/f'flush_pair_{aluminium_checkpoint}.json',result)
    print(results[-1],flush=True)
    if plot:
        draw(mesh, ids, -delta_nylon, -a[-1], results)
    return result


def draw(mesh, ids, nylon, aluminium, history):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import Normalize
    from clearance_response import surface

    skin, faces, numbers, _ = surface(mesh, [208])
    xyz = skin.points * 1000
    top = faces[np.all(np.isclose(xyz[faces,2], xyz[:,2].max(), rtol=0, atol=1.e-6), axis=1)]
    index = positions(ids, numbers)
    limits = Normalize(min(nylon.min(), aluminium.min()), max(nylon.max(), aluminium.max()))
    fig, axes = plt.subplots(1,3,figsize=(7.8,2.4),width_ratios=(1,1,1.9),layout='constrained')
    for j,(field,name) in enumerate([(nylon,'Nylon'),(aluminium,'Aluminium')]):
        ax = axes[j]
        colors = PolyCollection(xyz[top,:2],array=field[index[top]].mean(1),cmap='viridis',norm=limits,
                                edgecolors='none',antialiaseds=False,rasterized=True)
        ax.add_collection(colors)
        ax.autoscale()
        ax.set_aspect('equal')
        ax.set_title(name, fontsize=10)
        ax.set_xlabel('PCB X [mm]', fontsize=8)
        if j==0:
            ax.set_ylabel('PCB Y [mm]', fontsize=8)
    bar = fig.colorbar(colors,ax=axes[:2],pad=.04,shrink=.8,aspect=20)
    bar.set_label('Toward cells [mm]',fontsize=8)
    bar.ax.tick_params(labelsize=7)
    trend=axes[2]
    for tag,name,color,marker in [('nylon','Nylon','#3C78D8','o'),('aluminium','Aluminium','#38761D','^')]:
        trend.plot([r['travel_mm'] for r in history],[r[tag+'_peak_toward_cells_mm'] for r in history],
                   marker=marker,ms=3,lw=1.4,color=color,label=name)
    trend.set_xlabel('Screw travel [mm]', fontsize=8)
    trend.set_ylabel('Peak movement [mm]', fontsize=8)
    trend.legend(frameon=False,fontsize=8)
    trend.grid(axis='y',alpha=.2)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.tick_params(labelsize=8)
    fig.savefig(ROOT/'docs/figures/flush-pcb-screw-comparison.pdf',dpi=240,bbox_inches='tight',pad_inches=.07,
                metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('nylon_checkpoint');p.add_argument('aluminium_checkpoint');p.add_argument('--campaign',default='nov08_01')
    p.add_argument('--plot',action='store_true')
    args=p.parse_args()
    compare(args.nylon_checkpoint,args.aluminium_checkpoint,args.campaign,args.plot)
