"""Sample small-motion relative approach on the locked mesh; a linear clearance screen, never an impact prediction."""
import re,sys
import numpy as np
from native_rst import read_rst
from audit_local import ROOT,read
from film_identity import verified,write_json,digest
from independent_psd import moments
from seeded_motion import participation
from basis_comparison import field_files
from extend_board import FACE_MATERIALS

def surface(r,mats):
    g=r.quadgrid
    mask=np.isin(g.cell_data['ansys_material_type'],mats)&np.isin(g.cell_data['ansys_elem_type_num'],[185,186,187])
    s=g.extract_cells(mask).extract_surface(nonlinear_subdivision=1,algorithm='dataset_surface').triangulate()
    faces=s.regular_faces;ids=s.point_data['ansys_node_num']
    idx=np.searchsorted(r.mesh.nnum,ids);assert np.array_equal(r.mesh.nnum[idx],ids)
    # Use double-precision nodal coordinates. Each subdivided vertex must be an original FE vertex or midside node.
    pts=r.mesh.nodes[idx];assert np.max(abs(s.points-pts))<1e-8
    s.points=pts; tri=pts[faces];n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    norm=np.linalg.norm(n,axis=1);assert norm.min()>0
    return s,faces,ids,n/norm[:,None]

def pairs(lhs,rhs,cut_mm):
    surf,tri,ni,ns=lhs; tar,tf,tids,nt=rhs
    rows=[]
    for shape in [np.array([1/3,1/3,1/3]),*np.eye(3)]:
        p=np.einsum('i,jik->jk',shape,surf.points[tri])
        j,q=tar.find_closest_cell(p,return_closest_point=True)
        v=q-p;L=np.linalg.norm(v,axis=1);u=v/np.maximum(L[:,None],1e-14)
        # Facing patches only, including oblique samples. Separation derivative is along the joining line.
        mask=(L<cut_mm*1e-3)&(L>1e-8)&((ns*u).sum(1)>.1)&((nt[j]*u).sum(1)<-.1)
        loc=np.flatnonzero(mask);j=j[loc];q=q[loc]
        if not len(j):continue
        edges=tar.points[tf[j]];a=edges[:,1]-edges[:,0];b=edges[:,2]-edges[:,0];v=q-edges[:,0]
        def dot(x,y):return np.einsum('ij,ij->i',x,y)
        aa=dot(a,a);bb=dot(b,b);ab=dot(a,b);av=dot(a,v);bv=dot(b,v);det=aa*bb-ab**2
        x=(bb*av-ab*bv)/det;y=(aa*bv-ab*av)/det;w=np.c_[1-x-y,x,y]
        assert np.max(abs(np.einsum('ij,ijk->ik',w,edges)-q))<1e-9 and w.min()>-1e-5 and w.max()<1.00001
        rows.append((ni[tri[loc]],np.broadcast_to(shape,(len(j),3)),tids[tf[j]],w,u[loc],1000*L[loc],p[loc],q))
    assert rows
    return tuple(np.concatenate(blk) for blk in zip(*rows,strict=True))

def run(branch,campaign):
    case=branch+'_basis';proof=read(ROOT/'validation/global'/f'{case}.json');assert proof['campaign']==campaign
    d=ROOT/'.runtime/archive'/campaign/case;rst=d/'file.rst';verified(rst,proof['rst_sha256'])
    ledger=read(ROOT/'.runtime/receipts'/campaign/case/'archived.json');log=d/'solve.out'
    verified(log,next(row['sha256'] for row in ledger['files'] if row['name']=='solve.out'))
    r=read_rst(rst);freq=r.time_values;fields=field_files(case,campaign,proof['rst_sha256'],len(freq))
    from seeded_motion import integrate,FS
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cov={};histories={}
    for axis in 'XYZ':
        f=ROOT/f'.runtime/inputs/bare_psd_{axis}/model.inp';t=f.read_text()
        ref=read(ROOT/'validation/independent_psd'/f'{case}.json');assert ref['base_cases'][axis]['spectra_source_sha256']==digest(f)
        def knots(card):return np.array([float(v) for v in re.search('^'+card+r',1,,?([^\n!]+)',t,re.I|re.M)[1].split(',')])
        z=float(re.search(r'^\s*dmprat,([\d.Ee+-]+)',t,re.M|re.I)[1]);assert z==.02
        gamma=participation(log.read_text(errors='replace'),axis)
        cov[axis]=moments(freq,gamma,knots('psdfrq'),knots('psdval'),z,.125)[0]
        t,q,_=integrate(freq,gamma,axis,np.arange(9*FS+1));histories[axis]=q
    out={};pla=surface(r,[850])
    for body,mats in [('cells',[176,187,191]),('nickel',[174,179,180,186,189,193]),
                      ('other_fastener_targets',sorted(set(FACE_MATERIALS)-{176,187,191,174,179,180,186,189,193}))]:
        other=surface(r,mats);allrows=[pairs(pla,other,1.2),pairs(other,pla,1.2)]
        x,wx,y,wy,n,gap,from_xyz,to_xyz=(np.concatenate(b) for b in zip(*allrows,strict=True))
        b=np.empty((len(x),len(freq)))
        surf_ids=np.unique(np.r_[pla[2],other[2]]);phi=np.empty((len(surf_ids),3,len(freq)))
        for k in range(len(freq)):
            stem=fields[k+1];ids=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
            sort=np.argsort(ids);i=sort[np.searchsorted(ids[sort],x)];j=sort[np.searchsorted(ids[sort],y)]
            assert np.array_equal(ids[i],x) and np.array_equal(ids[j],y)
            sl=sort[np.searchsorted(ids[sort],surf_ids)];assert np.array_equal(ids[sl],surf_ids);phi[:,:,k]=u[sl]
            delta=np.einsum('ij,ijk->ik',wy,u[j])-np.einsum('ij,ijk->ik',wx,u[i])
            b[:,k]=np.einsum('ij,ij->i',n,delta)
        stats={}
        # Actual triangulated skins supply a geometric cross-check of the gap projection.
        def skins(q):
            change=np.einsum('ijk,k->ij',phi,q)
            a=pla[0].copy();z=other[0].copy()
            a.points=pla[0].points+change[np.searchsorted(surf_ids,pla[2])]
            z.points=other[0].points+change[np.searchsorted(surf_ids,other[2])]
            return a,z
        def intersections(q):
            a,z=skins(q)
            assert a.n_open_edges==0
            _,count=a.collision(z,contact_mode=0,box_tolerance=0.,cell_tolerance=0.)
            # Second geometric test: signed nearest-surface distance of original target vertices to the closed PLA skin.
            sd=z.compute_implicit_distance(a).point_data['implicit_distance']
            return int(count),int(np.sum(sd< -1e-6)),float(max(0.,-sd.min())*1000)
        locked,inside,depth=intersections(np.zeros(len(freq)));assert locked==inside==0 and depth<.001,(body,locked,inside,depth)
        for ax,c in cov.items():
            s=1e3*np.sqrt(np.maximum(0,np.einsum('ij,ij->i',b@c,b)))
            ix=int(np.argmax(s/gap));stats[ax]=dict(max_RMS_over_locked_gap=float(s[ix]/gap[ix]),
                RMS_mm=float(s[ix]),locked_gap_mm=float(gap[ix]),from_xyz_mm=(from_xyz[ix]*1000).tolist(),to_xyz_mm=(to_xyz[ix]*1000).tolist())
            q=histories[ax];du=1000*(q@b[ix]);imin=int(np.argmin(du));sigma=float(np.sqrt(np.mean(du[FS:-1]**2)))
            assert abs(sigma/s[ix]-1)<.015,(sigma,s[ix])
            cnt,inside,depth=intersections(q[imin]);stats[ax].update(seed_screen=dict(steady_RMS_mm=sigma,most_approached_sample_s=float(t[imin]),
                signed_linear_gap_at_that_sample_mm=float(gap[ix]+du[imin]),intersecting_triangle_pairs_at_that_sample=cnt,
                target_vertices_over_one_micron_inside_PLA=inside,maximum_target_vertex_depth_in_PLA_mm=depth))
            if body=='cells' and ax=='X':
                # Show physical-scale geometry beside the signed gap history; no display amplification.
                fig,(left,right)=plt.subplots(1,2,figsize=(8.3,3.05),gridspec_kw={'width_ratios':[1.23,1]},layout='constrained')
                u=np.arange(max(0,imin-265),min(len(t),imin+266));ms=1e3*(t[u]-t[imin]);free=gap[ix]+du[u]
                left.plot(ms,free,color='#08357E');left.axhline(0,color='#7A0101',lw=.9);left.fill_between(ms,free,0,where=free<0,color='#CE8F89',alpha=.65)
                left.scatter(0,free.min(),color='#7A0101',s=15,zorder=3);left.set_xlabel('Time about the selected state [ms]');left.set_ylabel('Projected gap [mm]');left.set_title('Local gap if contact stays open',fontsize=10)
                center=(from_xyz[ix]+to_xyz[ix])*500.;a,z=skins(q[imin]);colors=['#3C78D8','#38761D']
                for mesh,col,name in zip([a,z],colors,['PLA','Cells']):
                    lines=mesh.slice(normal=[0,1,0],origin=center*1e-3);ls=lines.lines;k=0;first=True
                    while k<len(ls):
                        count=ls[k];p=lines.points[ls[k+1:k+1+count]]*1000;k+=count+1
                        if np.max(abs(p[:,0]-center[0]))>3 or np.max(abs(p[:,2]-center[2]))>3:continue
                        right.plot(p[:,0],p[:,2],color=col,lw=1.6,label=name if first else None);first=False
                    assert not first
                right.set_aspect('equal');right.set_xlim(center[0]-1.05,center[0]+1.05);right.set_ylim(center[2]-1.05,center[2]+1.05)
                right.set_xlabel('Board X [mm]');right.set_ylabel('Board Z [mm]');right.set_title(f'Deformed section at {t[imin]:.4f} s',fontsize=10)
                right.legend(loc='upper right',fontsize=8,frameon=False);left.spines[['top','right']].set_visible(False)
                fig.savefig(ROOT/'docs/figures'/f'{branch}-linear-clearance.pdf',metadata={'CreationDate':None,'ModDate':None});plt.close(fig)
        out[body]=dict(locked_intersecting_triangle_pairs=locked,samples=int(len(b)),minimum_sampled_gap_mm=float(gap.min()),directions=stats)
    rec=dict(case=case,campaign=campaign,rst_sha256=proof['rst_sha256'],scopes=out,
             method='Both directions; nearest triangle at every facet centroid and vertex within 1.2 mm, facing patches only, linearized subdivisions at quadratic midside nodes, first-order distance derivative. Signed independent nine-second seeded response; test the actual two displaced triangulated skins at the worst sampled displacement of each selected pair. Intersections indicate breakdown of a fixed-open model, not post-impact displacements, forces or probabilities.')
    write_json(ROOT/'validation/clearance_rms'/f'{case}.json',rec)
    for n,s in out.items():print(n,s['samples'],s['minimum_sampled_gap_mm'],[round(t['max_RMS_over_locked_gap'],3) for t in s['directions'].values()])
if __name__=='__main__':run(*sys.argv[1:])
