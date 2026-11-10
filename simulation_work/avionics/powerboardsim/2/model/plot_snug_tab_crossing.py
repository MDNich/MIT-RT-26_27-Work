"""Plot the first directional material crossing in the snug nylon side-pull fixture."""
import argparse
import re

import numpy as np
from matplotlib.collections import PolyCollection

from audit_local import read
from film_identity import digest, verified
from report_plot import plt
from snug_local_checkpoint import CASE
from snug_mount_reactions import ring_nodes
from snug_tab_crossing import local_points
from stage_snug_fit import AUDIT, BEARINGS, INPUTS, MESH, ROOT


def draw(checkpoint):
    stem = CASE+'_'+checkpoint
    src = AUDIT/(stem+'_checkpoint.json')
    history = read(src)
    geometry = read(AUDIT/(stem+'_tab_corners.json'))
    assert geometry['checkpoint_sha256'] == digest(src)
    stop = history['first_excluded_set']
    assert stop and history['first_print_crossings']['all_layer_tension_MPa']['native_set'] == stop
    rows = [row for row in history['states'][:stop] if row['loadstep'] == 3]
    upper = geometry['stations'][-1]
    lower = geometry['stations'][0]
    assert upper['native_set'] == stop == lower['native_set']+1 and lower['within_screens']
    peak = upper['metrics']['layer_tension_MPa']
    bearing, = peak['bearing_faces']
    assert peak['tied_node_distance_mm'] > 2.
    meshfile = MESH/'case_1.5.npz'
    verified(meshfile, geometry['mesh_sha256'])
    deck = INPUTS/CASE/'model.inp'
    verified(deck, history['input_sha256'])
    model = deck.read_text()
    rings, _ = ring_nodes(model)
    master = 950001 + 2*BEARINGS.index(bearing)
    pilot, = re.findall(rf'(?im)^N,{master},([^\r\n]+)$', model)
    axis = np.fromstring(pilot, sep=',')
    with np.load(meshfile) as mesh:
        pts = local_points(mesh['points'])
        facets = mesh[str(bearing)]
    tie = rings[master]-2100001
    hotspot = np.asarray(peak['xyz_mm'])
    assert np.linalg.norm(pts[peak['node']-2100001]-hotspot) < 1.e-7
    assert set(tie).issubset(facets.ravel())
    assert abs(np.linalg.norm(pts[tie]-hotspot,axis=1).min()-peak['tied_node_distance_mm']) < 1.e-7

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.8, 2.75), layout='constrained',
                                 gridspec_kw={'width_ratios': [1.48, 1]})
    travel = [r['travel_mm'] for r in rows]
    for metric, label, colour in (('layer_tension_MPa','Through-layer tension','#08357E'),
                                  ('in_plane_tension_MPa','In-plane tension','#38761D'),
                                  ('layer_tensile_strain','Through-layer strain','#5A43A0')):
        ratio = [r['printed_coupon_percent'][metric] for r in rows]
        ax.plot(travel, ratio, '-o', color=colour, ms=2.1, lw=1.3, label=label)
    ax.axhline(100,ls='--',color='#7A0101',lw=.9)
    ax.axvspan(lower['travel_mm'],upper['travel_mm'],color='#CE8F89',alpha=.35,zorder=0)
    ax.set(xlabel='Prescribed cell travel [mm]', ylabel=r'Percentage of coupon reference [\%]',
           title='Forward pull with nylon screws', ylim=(0, max(110, 1.04*max(r['printed_coupon_percent']['layer_tension_MPa'] for r in rows))))
    ax.legend(loc='upper left', bbox_to_anchor=(.01,.87), frameon=False, fontsize=8)
    ax.spines[['right','top']].set_visible(False)
    ax.grid(axis='y', alpha=.13)
    # Trace the six-node boundary with its mid-side vertices. Adjacent subfaces
    # of the bearing are all on the same native STEP plane.
    polygon = pts[facets[:, [0,3,1,4,2,5]], :2]
    bx.add_collection(PolyCollection(polygon, facecolor='#D7E5F7', edgecolor='#91AED6', linewidth=.32))
    edge_record=read(AUDIT/(stem+'_tab_edge.json'))
    assert edge_record['checkpoint_sha256']==digest(src)
    edge=np.asarray(edge_record['geometry']['high_Y']['ends_mm'])
    bx.plot(edge[:,0],edge[:,1],color='#5A43A0',lw=1.7,label='Tab-root edge')
    bx.scatter(pts[tie,0], pts[tie,1], color='#08357E', s=4, label='Tied bearing nodes', zorder=2)
    bx.scatter(*hotspot[:2], color='#7A0101', marker='*', s=85, label='Peak layer tension', zorder=3)
    bx.plot(*axis[:2], '+', color='#666666', ms=6)
    bx.set(aspect='equal', xlabel='PCB X [mm]', ylabel='PCB Y [mm]', title='High-Y, low-X tab')
    bx.autoscale();bx.margins(.13)
    bx.legend(loc='upper left',bbox_to_anchor=(1.01,.94),frameon=False,fontsize=7,handlelength=.9)
    bx.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/snug-pull-tab-limit.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint')
    draw(parser.parse_args().checkpoint)
