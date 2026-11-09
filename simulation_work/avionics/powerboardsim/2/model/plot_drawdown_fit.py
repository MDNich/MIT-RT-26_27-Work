"""Illustrate rigid contact order and the curvature sensitivity of the middle-cell check."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT, read
from film_identity import verified


def plot():
    v = ROOT / 'validation'
    mesh = read(v / 'rigid_mesh_drawdown.json')
    verified(v / 'rigid_case_drawdown.json', mesh['STEP_audit_sha256'])
    bodies = {r['STEP_body']: r for r in read(v / 'rigid_case_drawdown.json')['records']}
    groups = [('Four outer washers', [6, 9, 10, 11]), ('Middle cell', [19]), ('Two outer cells', [4, 15]),
              ('Four nickel strips', [2, 7, 8, 14]), ('Two nickel strips', [17, 21])]
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.5, 2.12), layout='constrained', gridspec_kw={'width_ratios': [1.2, 1]})
    for j, (name, tags) in enumerate(groups):
        values = [float(np.mean(bodies[i]['first_touch_travel_bracket_mm'])) for i in tags]
        assert np.ptp(values) < .001
        x = values[0]
        a.hlines(j, 0, x, color='#3C78D8', lw=1.)
        a.scatter(x, j, s=22, color='#08357E')
        a.text(x + .06, j, f'{x:.3f}', va='center', fontsize=8, color='#08357E')
    a.set(yticks=range(len(groups)), yticklabels=[g[0] for g in groups], ylim=(4.55, -.6), xlim=(0, 3.06),
          xticks=[0, 1, 2, 3], xlabel='Case travel toward the PCB [mm]')
    a.axvline(3, color='#888888', ls=':', lw=1)
    a.set_title('First contact in the rigid STEP assembly', fontsize=10)

    levels = mesh['middle_cell_native_quadratic_subdivision']
    x = list(range(1, len(levels)+1))
    y = [np.mean(levels[str(k)]) for k in x]
    ref = np.mean(bodies[19]['first_touch_travel_bracket_mm'])
    b.axhline(ref, color='#38761D', ls='--', lw=1.3, label=f'STEP  {ref:.3f} mm')
    b.plot(x, y, 'o-', color='#08357E', markersize=4, label='Quadratic FE surface')
    b.set(xticks=x, xlabel='Surface subdivision level', ylabel='Travel to first contact [mm]', ylim=(1.42, 1.81))
    b.set_title('Middle cell on the same native mesh', fontsize=10)
    b.legend(loc='lower right', frameon=False, fontsize=8)
    for ax in (a, b):
        ax.spines[['top', 'right']].set_visible(False)
        ax.tick_params(labelsize=8)
        ax.xaxis.label.set_size(9)
        ax.yaxis.label.set_size(9)
    fig.savefig(ROOT / 'docs/figures/flush-drawdown-fit.pdf', metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)
    plan_view(mesh, groups[0][1])


def plan_view(mesh_check, first_washers):
    import shapely
    from matplotlib.patches import Patch, PathPatch
    from matplotlib.path import Path
    from case_drawdown_mesh import case_skin
    from clearance_response import surface
    from native_rst import read_rst

    # Use registered physical mesh outlines viewed through the cover, including the bores.
    cap, _, sha = case_skin(3)
    assert sha == mesh_check['case_mesh_sha256']['3mm']
    case = 'stand3_nylon_static'
    source = ROOT / '.runtime/archive' / mesh_check['campaign'] / case / 'file.rst'
    verified(source, mesh_check['undeformed_geometry_RST_sha256'])
    rst = read_rst(source)
    fig, ax = plt.subplots(figsize=(5.35, 3.15), layout='constrained')
    palette = {'Case': ('#ECF2FB', '#08357E'), 'Cells': ('#DCE8D8', '#38761D'),
               'First washers': ('#CE8F89', '#7A0101'), 'Inner washers': ('#E9E9E9', '#777777')}

    def project(skin, category, zorder):
        xy = skin.points[:, [1, 0]] * 1000
        polys = shapely.polygons(xy[skin.regular_faces])
        # Snapping below one micron prevents hairline gaps where projections share an edge.
        merged = shapely.union_all(polys[shapely.area(polys) > 1e-9], grid_size=.0001)
        for piece in shapely.get_parts(merged):
            if piece.geom_type != 'Polygon' or piece.area < .001:
                continue
            piece = shapely.orient_polygons(piece)
            # Ignore sub-pixel internal slivers from projecting nearly edge-on triangles.
            holes = [ring for ring in piece.interiors if shapely.Polygon(ring).area >= .05]
            rings = [np.array(ring.coords) for ring in [piece.exterior, *holes]]
            paths = [Path(ring, [Path.MOVETO, *([Path.LINETO] * (len(ring)-2)), Path.CLOSEPOLY]) for ring in rings]
            fill, edge = palette[category]
            ax.add_patch(PathPatch(Path.make_compound_path(*paths), facecolor=fill, edgecolor=edge, lw=.9, zorder=zorder))

    project(cap, 'Case', 1)
    for material, result in mesh_check['results'].items():
        tag = result['STEP_body']
        if tag in [4, 15, 19]:
            project(surface(rst, [int(material)])[0], 'Cells', 2)
        elif tag in [1, 6, 9, 10, 11, 20]:
            project(surface(rst, [int(material)])[0], 'First washers' if tag in first_washers else 'Inner washers', 3)
    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.tick_params(labelsize=8)
    ax.set_xlabel('Board Y [mm]', fontsize=9)
    ax.set_ylabel('Board X [mm]', fontsize=9)
    ax.spines[['right','top']].set_visible(False)
    handles = [Patch(facecolor=fill, edgecolor=edge, label=key) for key, (fill,edge) in palette.items()]
    ax.legend(handles=handles, ncols=2, loc='lower center', bbox_to_anchor=(.5, 1.01),
              frameon=False, fontsize=8, columnspacing=1.5, borderaxespad=0.)
    fig.savefig(ROOT / 'docs/figures/washer-location.pdf', metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


if __name__ == '__main__':
    plot()
