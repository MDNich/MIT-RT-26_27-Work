"""Plot frame-resolved cell clearance and a true-scale section through one verified overlap."""
from report_plot import plt
import numpy as np
from matplotlib.collections import LineCollection

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from curved_cell_contact import contact_solids, curved_skins, set_coordinates
from film_identity import verified
from motion_surface import displacement_basis
from seeded_motion import FRAMES, FS


def physical_section(variant, record, frame):
    campaign = record['campaign']
    basis = variant+'_basis'
    proof, _, rst = source(basis, campaign)
    assert proof['rst_sha256']==record['basis_sha256']
    groups = contact_solids(rst)
    ids = np.unique(np.concatenate([s.point_data['ansys_node_num'] for s in groups]))
    pos = np.searchsorted(rst.mesh.nnum, ids)
    assert np.array_equal(rst.mesh.nnum[pos], ids)
    modes = displacement_basis(rst, ids, field_files(basis,campaign,proof['rst_sha256'],rst.nsets))
    coord = ROOT/'.runtime/post'/campaign/(variant+'_motion_X')/'independent/coordinates.npz'
    verified(coord,record['axes']['X']['clip_sha256'])
    with np.load(coord) as data:
        assert data['time_s'][frame]==FRAMES[frame]/FS
        moved = (data['coordinates'][frame] @ modes.reshape(len(modes),-1)).reshape(len(ids),3)
    set_coordinates(groups,ids,rst.mesh.nodes[pos]+moved)
    cap, cells = curved_skins(groups,3)
    distance = cells.compute_implicit_distance(cap).point_data['implicit_distance']
    i = np.argmin(distance)
    p = cells.points[i]
    _, surf = cap.find_closest_cell(p,return_closest_point=True)
    surf = np.asarray(surf).ravel()
    normal = (surf-p)/np.linalg.norm(surf-p)
    depth_um = 1e6*np.linalg.norm(surf-p)
    actual = record['axes']['X']['full_skin_checks'][str(frame)]['3']['minimum_signed_vertex_gap_mm']
    assert abs(depth_um+1000*actual)<.001
    x = np.eye(3)[int(np.argmin(np.abs(normal)))]
    tangent = x - normal*(x@normal)
    tangent /= np.linalg.norm(tangent)
    plane = np.cross(normal,tangent)
    segments=[]
    for solid in (cap,cells):
        mesh = solid.slice(normal=plane, origin=surf)
        proj = 1e6*(mesh.points-surf) @ np.stack([tangent,normal],axis=1)
        lines = mesh.lines
        pieces=[]
        cursor=0
        while cursor<len(lines):
            n=lines[cursor]
            curve = proj[lines[cursor+1:cursor+n+1]]
            cursor += n+1
            if np.all(curve.min(0)<[165,90]) and np.all(curve.max(0)>[-165,-90]):
                pieces.append(curve)
        assert pieces
        segments.append(pieces)
    return segments, depth_um


def draw():
    variants = ['stand3_nylon','stand3_aluminium']
    records = [read(ROOT/'validation/film_cell_contact'/(v+'.json')) for v in variants]
    crossings = records[0]['axes']['X']['frames']['intersecting']
    frame = crossings[len(crossings)//2]
    segments, depth = physical_section(variants[0],records[0],frame)
    fig, (left,right) = plt.subplots(1,2,figsize=(8.4,3.5),width_ratios=[1.25,1],layout='constrained')
    time = (FRAMES-FRAMES[0])*1e3/FS
    rownames = []
    for j,axis in enumerate('XYZ'):
        for i,(data,screw) in enumerate(zip(records,['nylon','Al'],strict=True)):
            group = data['axes'][axis]['frames']
            assert sorted(group['separated']+group['intersecting']+group['unresolved'])==list(range(480))
            y=5-(2*j+i)
            rownames.append(axis+' / '+screw)
            for category,color,label in [('separated','#CEDBEC','Clear'),('intersecting','#7A0101','Intersecting'),
                                         ('unresolved','#FF7F0E','Unresolved')]:
                indices=group[category]
                if indices:
                    left.plot(time[indices],np.full(len(indices),y),'|',ms=14,mew=1,color=color,
                              label=label if i==j==0 else None)
    left.set(yticks=range(5,-1,-1),yticklabels=rownames,xlabel='Time from movie start [ms]',xlim=(-.4,29.65),ylim=(-.6,5.6))
    left.set_title('Cell and case surfaces at 480 instants',fontsize=11)
    left.tick_params(axis='y',length=0)
    left.legend(loc='upper left',bbox_to_anchor=(0,-.20),frameon=False,ncol=2,fontsize=8)
    # Sample the two local section boundaries along the narrow window shown in the figure.
    along = np.linspace(-150,150,401)
    boundaries = []
    for target, curves in zip((0.,-depth), segments, strict=True):
        heights = np.full_like(along,np.nan)
        for curve in curves:
            for a,b in zip(curve[:-1],curve[1:],strict=True):
                if a[0]>b[0]:
                    a,b = b,a
                if b[0]-a[0]<1e-10:
                    continue
                lane = (along>=a[0]) & (along<=b[0])
                z = a[1] + (along[lane]-a[0])*(b[1]-a[1])/(b[0]-a[0])
                old = heights[lane]
                heights[lane] = np.where(np.isnan(old) | (abs(z-target)<abs(old-target)),z,old)
        assert np.isfinite(heights).all()
        boundaries.append(heights)
    pla, cell = boundaries
    right.fill_between(along,-80,pla,color='#E5ECF7')
    right.fill_between(along,cell,80,color='#E5EFE1')
    right.fill_between(along,cell,pla,where=cell<pla,color='#CE8F89')
    for curves,color,label in zip(segments,['#08357E','#38761D'],['PLA face','Cell face'],strict=True):
        right.add_collection(LineCollection(curves,colors=color,linewidths=2,label=label))
    right.plot([0,0],[-depth,0],color='#7A0101',lw=1.6,marker='o',ms=3)
    right.annotate(f'{depth:.1f} µm overlap',xy=(0,-depth*.5),xytext=(9,-49),
                   arrowprops=dict(arrowstyle='-',color='#7A0101'),color='#7A0101',fontsize=9)
    right.set(xlim=(-150,150),ylim=(-80,80),aspect='equal',xlabel='Along surface tangent [µm]',ylabel='Along surface normal [µm]')
    right.set_title(f'X / nylon at frame {frame+1}',fontsize=11)
    right.legend(loc='upper right',frameon=False,ncol=2,fontsize=8)
    for ax in (left,right):
        ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/raised-film-contact.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    draw()
