"""Compare native PCB stresses in corresponding through-thickness columns of the original board mesh."""
import argparse

import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.colors import PowerNorm

from audit_local import ROOT
from case_stress import source
from film_identity import write_json
from report_plot import plt
from stage_snug_fit import AUDIT
from study_cases import native_case

BRANCHES=('bare','snug125_nylon','snug125_aluminium')
LABELS=('Bare board','Nylon screws','Aluminium screws')


def cross(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def face_geometry(corners,mids):
    """Integrate the area enclosed by quadratic edges and compare a chord approximation."""
    # Translating to each face centre avoids subtracting nearly equal global coordinates.
    origin=corners.mean(axis=1,keepdims=True)
    a=corners-origin
    b=np.roll(a,-1,axis=1)
    m=mids-origin
    integral=cross(a,-3*a+4*m-b)+4*cross(m,b-a)+cross(b,a-4*m+3*b)
    area=abs(integral.sum(axis=1))/12
    paths=[]
    for t in np.arange(12)/12:
        paths.append((1-t)*(1-2*t)*a+4*t*(1-t)*m+t*(2*t-1)*b)
    outline=np.stack(paths,axis=2).reshape(len(a),-1,2)
    polygon_area=abs(cross(outline,np.roll(outline,-1,axis=1)).sum(axis=1))*.5
    return area,polygon_area


def board_columns(campaign):
    proof,_,rst=source('bare_static',campaign)
    grid=rst.quadgrid
    meta=grid.cell_data
    pcb=grid.extract_cells((meta['ansys_material_type']==208)&(meta['ansys_elem_type_num']==186))
    assert set(pcb.celltypes)=={25,26}
    node_ids=pcb.point_data['ansys_node_num']
    element_ids=pcb.cell_data['ansys_elem_num']
    cols=[]
    geom={}
    for cell_type,n in ((25,4),(26,3)):
        take=pcb.celltypes==cell_type
        span=pcb.cell_offsets[:-1][take,None]+np.arange(5*n)
        ids=pcb.cell_connectivity[span]
        xyz=1000*pcb.points[ids]
        assert np.max(abs(xyz[:,:n,:2]-xyz[:,n:2*n,:2]))<1e-7
        assert np.max(abs(xyz[:,2*n:3*n,:2]-xyz[:,3*n:4*n,:2]))<1e-7
        middle=np.where(abs(xyz[:,0,2])<1e-7,0,n)
        row=np.arange(len(ids))[:,None]
        center=middle[:,None]+np.arange(n)
        outside=n-middle[:,None]+np.arange(n)
        boundary=node_ids[ids[row,center]]
        sides=xyz[row,outside,2]
        assert np.max(abs(xyz[row,center,2]))<1e-7 and np.max(abs(abs(sides)-.55118))<1e-7
        assert np.max(np.ptp(sides,axis=1))<1e-7
        xy=xyz[row,center,:2]
        mid=xyz[row,2*n+center,:2]
        areas,chords=face_geometry(xy,mid)
        assert (areas>0).all() and np.max(abs(chords/areas-1))<.002
        # Integrate both physical layers independently before matching them by mid-plane node IDs.
        layers={}
        for j,e in enumerate(element_ids[take]):
            key=tuple(sorted(boundary[j]))
            group=layers.setdefault(key,[])
            group.append((int(e),float(sides[j,0]),float(areas[j]),float(chords[j])))
            geom[int(e)]=np.sort(node_ids[ids[j,:2*n]])
            if len(group)==2:
                a,b=group
                assert a[1]*b[1]<0 and abs(a[2]/b[2]-1)<1e-7
                # Include midside nodes in the drawn outline. Statistics use the integrated area.
                poly=np.stack((xy[j],mid[j]),axis=1).reshape(-1,2)
                cols.append((a[0],b[0],a[2],a[3],poly))
        assert all(len(pair)==2 for pair in layers.values())
    assert len(cols)*2==len(element_ids) and len(geom)==len(element_ids)
    # Independent gross-area check from the native element volumes at the first preload station.
    enum,energy,_=rst.element_solution_data(0,'ENG')
    pos=np.searchsorted(enum,element_ids)
    assert np.array_equal(enum[pos],element_ids)
    thickness=1000*(pcb.bounds.z_max-pcb.bounds.z_min)
    volume=np.array([float(energy[i][0]) for i in pos])
    area_from_volumes=1e9*volume.sum()/thickness
    assert np.all(volume>0) and abs(area_from_volumes/sum(c[2] for c in cols)-1)<1e-5
    ref=dict(rst_sha256=proof['rst_sha256'],native_volume_set=1,
             native_volume_divided_by_thickness_mm2=float(area_from_volumes),nominal_thickness_mm=float(thickness))
    return ref,cols,geom,(rst.mesh.nnum,rst.mesh.nodes)


def area_quantile(values,weights,q):
    order=np.argsort(values)
    area=np.cumsum(weights[order])
    return float(values[order[np.searchsorted(area,q*area[-1])]])


def analyze(axis,campaign,reference,columns,corners,pose,plot):
    elements=np.array([[row[0],row[1]] for row in columns])
    area=np.array([row[2] for row in columns])
    chord_area=sum(row[3] for row in columns)
    sorted_e=np.array(sorted(corners))
    results={}
    fields=[]
    for branch in BRANCHES:
        case=native_case(branch,'psd_'+axis)
        audit,_,rst=source(case,campaign)
        scope=audit['native_psd_fields']['scopes']['pcb']
        enum,raw,ids=rst.element_solution_data([3,1],'ENS')
        pos=np.searchsorted(enum,sorted_e)
        assert np.array_equal(enum[pos],sorted_e)
        element_max=np.empty(len(pos))
        for i,(idx,e) in enumerate(zip(pos,sorted_e,strict=True)):
            native_nodes=ids[idx]
            assert np.array_equal(np.unique(native_nodes),corners[e])
            stored=raw[idx].reshape(len(native_nodes),11)[:,10]
            assert np.isfinite(stored).all() and stored.min()>=0
            element_max[i]=float(stored.max())*1e-6
        values=element_max[np.searchsorted(sorted_e,elements)].max(axis=1)
        assert np.isclose(values.max(),scope['equivalent_stress_rms_Pa']*1e-6,rtol=1e-12)
        assert sorted_e[element_max.argmax()]==scope['stress_element']
        loc=np.searchsorted(pose[0],scope['stress_node'])
        assert pose[0][loc]==scope['stress_node']
        record=dict(case=case,rst_sha256=audit['rst_sha256'],peak_element=scope['stress_element'],peak_node=scope['stress_node'],
                    original_peak_xyz_mm=(1000*pose[1][loc]).tolist(),maximum_MPa=float(values.max()),area_median_MPa=area_quantile(values,area,.5),
                    area_95th_percentile_MPa=area_quantile(values,area,.95))
        if fields:
            bare=fields[0]
            assert (bare>0).all()
            ratio=values/bare
            record.update(footprint_percent_over_1p1_times_bare=float(100*area[ratio>1.1].sum()/area.sum()),
                          footprint_percent_below_0p9_times_bare=float(100*area[ratio<.9].sum()/area.sum()),
                          area_median_paired_ratio=area_quantile(ratio,area,.5))
        results[branch]=record
        fields.append(values)
    write_json(AUDIT/('pcb_footprint_'+axis+'.json'),dict(campaign=campaign,base=axis,area_reference=reference,
        columns=len(area),SOLID186_elements=len(sorted_e),footprint_area_mm2=float(area.sum()),
        relative_chord_area_error=abs(float(chord_area/area.sum()-1)),models=results,
        scope='Each original PCB mesh column represents two thickness layers. Its scalar is the largest stored '
              'equivalent RMS stress among all corners of those two solids. Area statistics weight the original '
              'quadratic footprint. Each model uses its own locked contact tangent and the same single-axis base spectrum.'))
    if plot:
        fig,axes=plt.subplots(1,3,figsize=(7.1,3.35),layout='constrained',sharex=True,sharey=True)
        scale=PowerNorm(.5,vmin=0,vmax=max(v.max() for v in fields))
        for ax,field,title,branch in zip(axes,fields,LABELS,BRANCHES,strict=True):
            collection=PolyCollection([row[4] for row in columns],array=field,norm=scale,cmap='viridis',
                                      rasterized=True,edgecolors='none',antialiaseds=False)
            ax.add_collection(collection)
            peak=results[branch]['original_peak_xyz_mm'][:2]
            ax.plot(*peak,'o',ms=8,mfc='none',mew=1.2,mec='#7A0101')
            ax.set(title=title,xlim=(-3,73),ylim=(-3,124),aspect='equal',xlabel='PCB X [mm]')
            ax.spines[['top','right']].set_visible(False)
        axes[0].set_ylabel('PCB Y [mm]')
        fig.colorbar(collection,ax=axes,shrink=.90).set_label('Equivalent stress [MPa RMS]')
        fig.savefig(ROOT/'docs/figures'/('snug-native-pcb-'+axis.lower()+'.pdf'),
                    dpi=190,metadata={'CreationDate':None,'ModDate':None})
        plt.close(fig)
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('axis',choices=('X','Y','Z'))
    parser.add_argument('--plot',action='store_true')
    parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args()
    analyze(args.axis,args.campaign,*board_columns(args.campaign),args.plot)
