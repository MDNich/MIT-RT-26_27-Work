"""Compare modeled screw force by travel and show the actual tab-to-board gap over one bearing."""
import argparse

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from audit_local import ROOT,read,table
from film_identity import digest,verified
from installed_tab_gap import patch_volumes,triangles,overlap_vertices
from native_rst import read_rst


def draw(case,stamp):
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
    surf=right.tripcolor(xy[:,0],xy[:,1],faces[abs(det)>1e-14],h,shading='gouraud',cmap=cmap,vmin=0,vmax=2.5,rasterized=True)
    right.autoscale();right.set(aspect='equal',title='Most heavily loaded tab',xlabel='PCB X [mm]',ylabel='PCB Y [mm]')
    cb=fig.colorbar(surf,ax=right,fraction=.055,pad=.04,ticks=[0,.5,1,1.5,2,2.5])
    cb.set_label('Tab-to-PCB gap [mm]')
    for ax in (left,right):ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures'/(case+'_'+stamp+'.pdf'),metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case');p.add_argument('stamp')
    a=p.parse_args();draw(a.case,a.stamp)
