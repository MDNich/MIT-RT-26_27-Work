"""Compare modeled screw force by travel and show the actual tab-to-board gap over one bearing."""
import argparse

from report_plot import plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from audit_local import ROOT,read,table
from film_identity import digest,verified
from installed_tab_gap import patch_volumes,triangles,overlap_vertices
from native_rst import read_rst


def tab_map(case,stamp):
    base=ROOT/'validation/partition_checks'/case
    histories=read(base/(stamp+'_history.json'))
    gap=read(base/(stamp+'_gap.json'))
    assert gap['checkpoint_sha256']==histories['manifest_sha256']
    campaign=histories['campaign']
    raw_path=ROOT/'.runtime/archive'/campaign/('stand3_nylon_static' if 'nylon' in case else 'stand3_aluminium_static')/'file.rst'
    verified(raw_path,gap['geometry_reference_sha256'])
    rst=read_rst(raw_path)
    path=ROOT/'.runtime/board_surface_initial_v1/seat_faces.csv'
    verified(path,gap['native_face_inventory_sha256'])
    seats=table(path)
    dpf=ROOT/'.runtime/post'/campaign/case/'partition_DPF'/stamp
    q=read(dpf/'request.json');points=np.asarray(q['nodes'])
    verified(dpf/'displacements.bin',gap['DPF_sha256'])
    fields=np.memmap(dpf/'displacements.bin',dtype='<f8',mode='r',shape=(len(q['sets']),len(points),3))
    series=[x for x in histories['history'] if x['loadstep']>=2]
    end=series[-1]
    j=int(np.argmax(end['drive_N']))
    pair=880+j
    native_set=end['native_set']
    facets=[]
    for mat,typ,z in [(850,858,-3.55118),(208,857,-.55118)]:
        domain=patch_volumes(rst,seats,mat,typ,z)[pair]
        facets.append(triangles(domain,rst,z,2,(points,fields[q['sets'].index(native_set)])))
    xy,h,begin,area=overlap_vertices(*facets)
    finish=np.r_[begin[1:],len(h)]-1
    faces=[]
    for a,b in zip(begin,finish,strict=True):
        faces.extend((a,i,i+1) for i in range(a+1,b-1))
    faces=np.array(faces)
    pos=xy[faces]
    det=(pos[:,1,0]-pos[:,0,0])*(pos[:,2,1]-pos[:,0,1])-(pos[:,1,1]-pos[:,0,1])*(pos[:,2,0]-pos[:,0,0])
    assert abs(abs(det).sum()*.5-area.sum())<1e-7
    return xy, faces[abs(det)>1e-14], h, series, gap


def draw(case,stamp):
    xy, faces, h, series, _ = tab_map(case,stamp)
    end = series[-1]
    fig,(left,right)=plt.subplots(1,2,figsize=(8.3,3.15),width_ratios=[1.3,1],layout='constrained')
    travel=[r['travel_mm'] for r in series]
    for i,(label,color) in enumerate([('Low X, low Y','#08357E'),('Low X, high Y','#3C78D8'),
                                      ('High X, low Y','#38761D'),('High X, high Y','#5A43A0')]):
        left.plot(travel,[r['drive_N'][i] for r in series],lw=1.4,marker='.',ms=3,color=color,label=label)
    left.axvspan(.95,1.1,color='#CE8F89',alpha=.35)
    left.axvspan(2.6,2.675,color='#3C78D8',alpha=.2)
    left.legend(loc='upper left',fontsize=7,frameon=False,ncol=2,columnspacing=.7)
    left.set(xlabel='Screw travel relative to PCB [mm]',ylabel='Axial drive reaction [N]',
             title='Four screw drives',xlim=(-.03,end['travel_mm']+.06),ylim=(-6,max(end['drive_N'])*1.06))
    cmap=LinearSegmentedColormap.from_list('printed_gap',[(0,'#7A0101'),(.05/2.5,'#CE8F89'),(.10/2.5,'#F5ECE1'),
                                                       (.3,'#CCE0F5'),(.65,'#3C78D8'),(1,'#08357E')])
    surf=right.tripcolor(xy[:,0],xy[:,1],faces,h,shading='gouraud',cmap=cmap,vmin=0,vmax=2.5,rasterized=True)
    right.autoscale();right.set(aspect='equal',title='Most heavily loaded tab',xlabel='PCB X [mm]',ylabel='PCB Y [mm]')
    cb=fig.colorbar(surf,ax=right,fraction=.055,pad=.04,ticks=[0,.5,1,1.5,2,2.5])
    cb.set_label('Tab-to-PCB gap [mm]')
    for ax in (left,right):ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures'/(case+'_'+stamp+'.pdf'),metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


def compare(nylon_stamp, aluminium_stamp):
    fig,axes=plt.subplots(1,3,figsize=(8.6,2.7),width_ratios=[1.7,.65,.65],layout='constrained')
    colors=LinearSegmentedColormap.from_list('tab_gap', ['#8E2328','#F3C2A6','#EEF1F5','#9DBCE2','#08357E'])
    for ax,screw,stamp,color in zip(axes[1:],('nylon','aluminium'),(nylon_stamp,aluminium_stamp),('#2355A5','#38761D'),strict=True):
        xy,faces,h,series,gaps=tab_map('flush_'+screw+'_surf1_static',stamp)
        end=series[-1]
        assert np.argmax(end['drive_N'])==2
        travel,low,high=[],[],[]
        for state in gaps['gaps'].values():
            feet=state['levels']['2']
            fractions=[100*rec['area_gap_le_50um_mm2']/rec['projected_overlap_mm2'] for rec in feet.values()]
            assert all(0 <= f <= 100 for f in fractions)
            travel.append(state['travel_mm']);low.append(min(fractions));high.append(max(fractions))
        assert np.all(np.diff(travel)>0) and abs(travel[-1]-end['travel_mm'])<1.e-7
        axes[0].fill_between(travel,low,high,color=color,alpha=.35)
        axes[0].plot(travel,high,color=color,label=screw.capitalize(),marker='o',markersize=2.5,lw=1.3)
        surf=ax.tripcolor(xy[:,0],xy[:,1],faces,h,shading='gouraud',cmap=colors,vmin=0,vmax=.25,rasterized=True)
        ax.set(aspect='equal',title=f'{screw.capitalize()}\n{travel[-1]:.2f} mm travel',xlabel='X [mm]')
        ax.set_xticks([63,67]);ax.set_yticks([0,5,10,15]);ax.spines[['top','right']].set_visible(False)
    axes[0].set(xlabel='Screw travel relative to PCB [mm]',ylabel='Area within 0.05 mm of PCB [\\%]',
                title='Near-seat footprint, four tabs',xlim=(2.42,3.015),ylim=(-.7,20))
    axes[0].set_xticks([2.45,2.60,2.75,2.90,3.00]);axes[0].legend(frameon=False,loc='upper left',fontsize=8)
    axes[0].spines[['top','right']].set_visible(False)
    axes[1].set_ylabel('Y [mm]')
    bar=fig.colorbar(surf,ax=axes[-1],pad=.04,extend='max',ticks=[0,.05,.15,.25])
    bar.set_label('Tab-to-board gap [mm]')
    fig.savefig(ROOT/'docs/figures/flush-tab-seating.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('case')
    p.add_argument('stamp')
    p.add_argument('--paired-aluminium', metavar='CHECKPOINT',
                   help='Use a nylon checkpoint and this aluminium checkpoint for the end-state comparison.')
    a=p.parse_args()
    if a.paired_aluminium:
        if a.case != 'flush_nylon_surf1_static':
            p.error('The paired comparison uses the flush nylon case as its first input.')
        compare(a.stamp,a.paired_aluminium)
    else:
        draw(a.case,a.stamp)
