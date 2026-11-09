"""Map peak stored PCB corner stress on the original board coordinates for a native PSD pair."""
import argparse

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from matplotlib.collections import PolyCollection
from scipy.spatial import ConvexHull
import numpy as np

from audit_local import ROOT,read
from film_identity import verified,write_json
from native_rst import read_rst
from study_cases import native_case


def draw(variant,axis):
    sources=[]; reference=None
    for label in ('bare',variant):
        key=native_case(label,'psd_'+axis)
        proof=read(ROOT/'validation/global'/f'{key}.json')
        path=ROOT/'.runtime/archive'/proof['campaign']/key/'file.rst'
        verified(path,proof['rst_sha256']);raw=read_rst(path)
        g=raw.grid;meta=g.cell_data
        pcb=g.extract_cells(np.isin(meta['ansys_elem_type_num'],[185,186,187])&(meta['ansys_material_type']==208))
        points=np.unique(pcb.point_data['ansys_node_num'])
        if reference is None:
            ref=read(ROOT/'validation/global/bare_static.json')
            restfile=ROOT/'.runtime/archive'/ref['campaign']/ref['case']/'file.rst'
            verified(restfile,ref['rst_sha256']);rest=read_rst(restfile,parse_vtk=False)
            j=np.searchsorted(rest.mesh.nnum,points);assert np.array_equal(rest.mesh.nnum[j],points)
            reference=(points.copy(),1000*rest.mesh.nodes[j,:3],ref['rst_sha256'])
        ids,xyz,rest_sha=reference
        assert np.array_equal(points,ids)
        sel=pcb.cell_data['ansys_elem_num']
        enum,fields,nodes=raw.element_solution_data([3,1],'ENS')
        rows=np.searchsorted(enum,sel);assert np.array_equal(enum[rows],sel)
        values=np.empty(len(rows))
        order=pcb.point_data['ansys_node_num']
        polys=[]
        connectivity,offsets,cell_types=pcb.cell_connectivity,pcb.cell_offsets,pcb.celltypes
        for j,i in enumerate(rows):
            n=nodes[i];loc=np.searchsorted(ids,n)
            assert np.array_equal(ids[loc],n)
            values[j]=float(fields[i].reshape(len(n),11)[:,10].max())*1e-6
            # VTK linear_copy retains the original padded connectivity of a quadratic cell.
            ncorner={12:8,13:6}[int(cell_types[j])]
            assert offsets[j+1]-offsets[j]>=ncorner
            native_nodes=order[connectivity[offsets[j]:offsets[j]+ncorner]]
            corners=xyz[np.searchsorted(ids,native_nodes)]
            # The two caps can have different XY coordinates, so project all physical corners.
            assert len(corners) in (6,8)
            xy=corners[:,:2]
            polys.append(xy[ConvexHull(xy).vertices])
        expected=proof['native_psd_fields']['scopes']['pcb']
        node=expected['stress_node'];idx=np.searchsorted(ids,node);mx=float(np.max(values))
        assert ids[idx]==node and np.isfinite(values).all() and np.isclose(mx,expected['equivalent_stress_rms_Pa']*1e-6)
        peak_element=int(sel[np.argmax(values)])
        assert peak_element==expected['stress_element']
        sources.append((polys,values,dict(case=key,peak_MPa=mx,node=node,peak_element=peak_element,
            reference_location_mm=xyz[idx].tolist(),PCB_elements=len(values),rst_sha256=proof['rst_sha256'])))
    fig,axes=plt.subplots(1,2,figsize=(6.7,3.6),layout='constrained',sharey=True)
    scale=PowerNorm(.5,vmin=0,vmax=max(q[2]['peak_MPa'] for q in sources))
    material='aluminium' if 'aluminium' in variant else 'nylon'
    seat='3 mm stand-off' if variant.startswith('stand3') else 'Flush'
    for ax,(xy,s,source),title in zip(axes,sources,['Without case',seat+' / '+material],strict=True):
        ix=np.argsort(s)
        im=PolyCollection([xy[i] for i in ix],array=s[ix],cmap='viridis',norm=scale,
                          rasterized=True,antialiaseds=False,edgecolors='none')
        ax.add_collection(im)
        x,y,_=source['reference_location_mm']
        ax.plot(x,y,'o',ms=8,mec='#7A0101',mfc='none',mew=1.4)
        ax.set_title(title,fontsize=10)
        ax.set_xlabel('PCB X [mm]')
        ax.set_xlim(-3,74);ax.set_ylim(-3,125);ax.set_aspect('equal')
        ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('PCB Y [mm]')
    bar=fig.colorbar(im,ax=axes,shrink=.86,ticks=[0,5,15,30,50,70,90])
    bar.set_label('Equivalent stress [MPa RMS]')
    dest=f'{variant}-native-{axis.lower()}-pcb'
    fig.savefig(ROOT/'docs/figures'/f'{dest}.pdf',dpi=200,metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    write_json(ROOT/'validation/psd_comparisons'/f'{dest}.json',dict(proofs=[q[2] for q in sources],reference_sha256=rest_sha,
        scope='Original PCB coordinates. Each solid footprint uses its largest stored corner stress. Higher values are drawn last through the thickness.'))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant');parser.add_argument('axis',choices=list('XYZ'));a=parser.parse_args()
    draw(a.variant,a.axis)
