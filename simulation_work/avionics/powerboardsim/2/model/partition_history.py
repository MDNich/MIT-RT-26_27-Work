"""Audit printed-material fields, compressed contact faces and fixture forces in saved native partitions."""
import argparse
import re
from pathlib import Path

import numpy as np
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS
from scipy.spatial import cKDTree

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from global_contact import pair_summary
from installation_material import PLA
from native_rst import read_rst


def material_law(deck):
    def prop(name):
        return float(re.search('(?im)^mp,'+name+',850,([^,\r\n]+)',deck)[1])
    ex,ey,ez = [prop(n)*1e-6 for n in ('EX','EY','EZ')]
    comp=np.diag([1/ex,1/ey,1/ez])
    for i,j,nu,mod in [(0,1,'PRXY',ex),(0,2,'PRXZ',ex),(1,2,'PRYZ',ey)]:
        comp[i,j]=comp[j,i]=-prop(nu)/mod
    return comp,np.array([prop(n)*1e-6 for n in ('GXY','GYZ','GXZ')])


class Partition:
    def __init__(self, path, types):
        self.rst=r=read_rst(path)
        assert np.array_equal(r.mesh.enum,r._eeqv)
        g=r.grid.cell_data
        self.items={}
        row_order=np.argsort(r.mesh.enum)
        mesh=r.mesh.elem
        for key,(etype,real) in types.items():
            keep=g['ansys_etype']==etype
            if real is not None:keep &= g['ansys_real_constant']==real
            enum=np.sort(g['ansys_elem_num'][keep])
            if not len(enum):continue
            ix=row_order[np.searchsorted(r.mesh.enum[row_order],enum)]
            assert np.array_equal(r.mesh.enum[ix],enum)
            # Corner count as stored on the native element result header, including
            # duplicated corners of degenerate contact quads.
            n=r._nodstr[r.mesh._ans_etype[ix]]
            labels=np.stack([mesh[i][10:10+count] for i,count in zip(ix,n,strict=True)])
            self.items[key]=enum,ix,labels
        self.fixed=np.sort(r.mesh.node_components['_FIXEDSU'])

    def fields(self,k):
        if not self.items:return {}
        r=self.rst
        ptr,_,offset=r._element_solution_header(k)
        out={}
        for key,(enum,ix,labels) in self.items.items():
            fields=('ENS','EEL') if key=='PLA' else (('ENS',) if key=='screws' else ('ECT',))
            values={}
            for field in fields:
                values[field]=r._cfile.read_element_data(ptr[ix],ELEMENT_INDEX_TABLE_KEYS.index(field),offset)
            out[key]=enum,labels,values
        return out


def bearing_distances(parts, deck):
    coupled=np.unique([int(n) for n in re.findall(r'(?im)^CERIG,95000[1357],(\d+),UXYZ',deck)])
    assert len(coupled)>12
    ids=np.unique(np.r_[coupled,np.concatenate([p.items['PLA'][2].ravel() for p in parts if 'PLA' in p.items])])
    xyz=np.full((len(ids),3),np.nan)
    for p in parts:
        _,here,there=np.intersect1d(p.rst.mesh.nnum,ids,return_indices=True)
        present=np.isfinite(xyz[there,0])
        assert np.array_equal(p.rst.mesh.nodes[here[present]],xyz[there[present]])
        xyz[there]=p.rst.mesh.nodes[here]
    assert np.isfinite(xyz).all()
    tree=cKDTree(1000*xyz[np.searchsorted(ids,coupled)])
    return ids,tree.query(1000*xyz)[0]


def reductions(k,t,fields,law,bearing):
    solids=[f['PLA'] for f in fields if 'PLA' in f]
    elements=np.concatenate([p[0] for p in solids])
    nodes=np.concatenate([p[1] for p in solids])
    assert nodes.shape==(16108,4) and len(np.unique(elements))==len(elements)==16108
    stress=np.concatenate([np.stack(p[2]['ENS']) for p in solids]).reshape(-1,6).astype(float)*1e-6
    strain=np.concatenate([np.stack(p[2]['EEL']) for p in solids]).reshape(-1,7)
    comp,shear=law
    predicted=np.column_stack((stress[:,:3]@comp,stress[:,3:]/shear))
    err=float(np.max(abs(predicted-strain[:,:6]))/max(1e-6,abs(strain[:,:6]).max()))
    assert np.isfinite(stress).all() and err <.001
    x,y,z,xy=stress[:,:4].T
    measures={}
    lookup,distance=bearing
    flat=nodes.ravel()
    index=np.searchsorted(lookup,flat)
    assert np.array_equal(lookup[index],flat)
    distances=distance[index]
    away=np.flatnonzero(distances>=2.)
    for name,v in zip(PLA,((x+y)*.5+np.hypot((x-y)*.5,xy),z,strain[:,2]),strict=True):
        idx=int(v.argmax())
        j=away[np.argmax(v[away])]
        measures[name]=dict(peak=float(v[idx]),element=int(elements[idx//4]),node=int(flat[idx]),
                            distance_to_bearing_mm=float(distances[idx]),peak_over_2mm_away=float(v[j]),
                            distant_node=int(flat[j]),distant_peak_distance_mm=float(distances[j]),
                            elements_all_four_above=int(np.count_nonzero((v.reshape(-1,4)>=PLA[name]).all(1))))
    beams=[p['screws'] for p in fields if 'screws' in p]
    b_ids=np.concatenate([b[1] for b in beams])
    assert np.array_equal(np.sort(b_ids.ravel()),np.arange(950001,950009))
    axial=np.concatenate([np.stack(b[2]['ENS']) for b in beams]).reshape(4,2,25,3)[:,:,:,0]*1e-6
    assert np.allclose(axial[:,:,0],axial.mean(axis=2),atol=.001,rtol=1.e-5)
    contacts={}
    for key in sorted({i for field in fields for i in field if isinstance(i,int)}):
        parts=[d[key] for d in fields if key in d]
        enum=np.concatenate([p[0] for p in parts])
        order=np.argsort(enum)
        assert len(np.unique(enum))==len(enum)
        labels=np.concatenate([p[1] for p in parts])[order]
        values=[entry for p in parts for entry in p[2]['ECT']]
        contacts[key]=pair_summary(k,t,enum[order],enum[order],[values[i] for i in order],labels)
    return dict(material=measures,constitutive_relative_error=err,maximum_screw_fibre_tension_MPa=float(axial.max()),
                maximum_screw_direct_tension_MPa=float(axial.mean(2).max()),contact=contacts)


def forces(k,parts,bolts):
    fixed=parts[0].fixed
    assert len(fixed)==781 and all(np.array_equal(p.fixed,fixed) for p in parts)
    xyz=np.full((len(fixed),3),np.nan)
    force=np.zeros((len(fixed),3))
    bolt=np.zeros(6);actuators=np.zeros(4)
    for part in parts:
        r=part.rst
        _,inside,common=np.intersect1d(r.mesh.nnum,fixed,return_indices=True)
        present=~np.isnan(xyz[common,0])
        assert np.array_equal(xyz[common[present]],r.mesh.nodes[inside[present]])
        xyz[common]=r.mesh.nodes[inside]
        if not r._solution_header(k)['nrf']:continue
        value,node,dof=r.nodal_reaction_forces(k)
        mask=np.isin(node,fixed)
        assert np.all(np.isin(dof[mask],[1,2,3]))
        np.add.at(force,(np.searchsorted(fixed,node[mask]),dof[mask]-1),value[mask])
        for j,pilot in enumerate(bolts):
            bolt[j]+=value[(node==pilot)&(dof==1)].sum()
        for j in range(4):
            actuators[j]+=value[(node==960111+j)&(dof==3)].sum()
    assert np.isfinite(xyz).all()
    return dict(drive_N=actuators.tolist(),bolt_N=bolt.tolist(),fixed_face_net_force_N=force.sum(0).tolist(),
                fixed_face_net_moment_Nm=np.cross(xyz-xyz.mean(0),force).sum(0).tolist())


def run(folder, campaign, control):
    root=ROOT/'.runtime'
    case='stand3_nylon_static' if control else folder.parent.name
    if control:
        ledger=read(root/'receipts'/campaign/case/'archived.json')
        hashes={r['name']:r['sha256'] for r in ledger['files']}
        assert read(ROOT/'validation/global'/(case+'.json'))['rst_sha256']==verified(folder/'file.rst',hashes['file.rst'])
        names=[f'file{i}.rst' for i in range(12)]
        for name in names:verified(folder/name,hashes[name])
        deck=folder/'model.inp';verified(deck,hashes['model.inp'])
        manifest_sha=digest(root/'receipts'/campaign/case/'archived.json')
    else:
        proof=read(folder/'receipts.json')
        assert case==proof['case'] and proof['campaign']==campaign
        names=[f'file{i}.rst' for i in range(proof['cores'])]
        from partition_snapshot import check_element_tables
        for name in names:
            verified(folder/name,proof['files'][name]['SHA256'])
            check_element_tables(folder/name,read_rst(folder/name,read_mesh=False),proof['sets'])
        deck=root/'inputs'/case/'model.inp';verified(deck,proof['model_sha256'])
        manifest_sha=digest(folder/'receipts.json')
    types={'PLA':(850,None),'screws':(851,None),853:(853,853)}
    if not control:types.update({p:(858,p) for p in range(880,884)})
    parts=[Partition(folder/n,types) for n in names]
    deck_lines=deck.read_text()
    law=material_law(deck_lines)
    bearing=bearing_distances(parts,deck_lines)
    times=parts[0].rst.time_values
    step=parts[0].rst._resultheader['ls_table']
    assert all(np.array_equal(q.rst.time_values,times) and np.array_equal(q.rst._resultheader['ls_table'],step) for q in parts)
    if not control:
        complete=proof['sets']
        assert len(times)==complete+proof.get('diagnostic_sets_excluded',0)
        assert np.all(step[:complete,1]!=999999) and np.all(step[complete:,1]==999999)
        times=times[:complete]
        step=step[:complete]
    bpath=root/'archive'/campaign/'stand3_nylon_static'/'bolt_preload_audit.csv'
    ref=read(root/'receipts'/campaign/'stand3_nylon_static'/'archived.json')
    verified(bpath,next(row['sha256'] for row in ref['files'] if row['name']==bpath.name))
    bolts=table(bpath)[:6]['pilot'].astype(int)
    history=[]
    for k,t in enumerate(times):
        row=reductions(k,t,[q.fields(k) for q in parts],law,bearing)
        row.update(forces(k,parts,bolts),native_set=k+1,time=float(t),loadstep=int(step[k,0]),
                   travel_mm=float(3*np.clip(t-2.,0,1)) if not control else 0.)
        assert row['contact'][853]['n_contact']==8038
        if not control:
            assert [row['contact'][p]['n_contact'] for p in range(880,884)]==[64,66,66,66]
        history.append(row)
    dest=ROOT/'validation/partition_checks'
    if control:
        original=read(ROOT/'validation/installation_material'/(case+'.json'))['history']
        external=read(ROOT/'validation/global'/(case+'.json'))['contact_history_native_RST']
        fr=read(ROOT/'validation/board_reactions'/(case+'.json'))['history']
        for a,b,c,f in zip(history,original,external,fr,strict=True):
            for name,data in a['material'].items():
                assert np.isclose(data['peak'],b['all_'+name],rtol=1e-6)
                assert np.isclose(data['peak_over_2mm_away'],b['away_'+name],rtol=1e-6)
                assert data['elements_all_four_above']==b[name+'_elements_all_four_above']
            assert np.isclose(a['maximum_screw_fibre_tension_MPa'],max(b['four_screws']['peak_fiber_tension_MPa']),rtol=1e-6)
            assert np.allclose(a['fixed_face_net_force_N'],f['net_force_N'],atol=1e-7)
            assert np.allclose(a['fixed_face_net_moment_Nm'],f['net_moment_Nm'],atol=1e-8)
            assert a['contact'][853]==c
        assert np.allclose(history[-1]['bolt_N'],table(bpath)[-6:]['reaction_N'],rtol=1e-8)
        out=dest/'raised_partition_control.json'
    else:
        checked=dest/'raised_partition_control.json'
        assert read(checked)['case']=='stand3_nylon_static'
        out=dest/case/(folder.name+'_history.json')
        manifest_path=out.parent/(folder.name+'_sources.json')
        write_json(manifest_path,proof)
        assert digest(manifest_path)==manifest_sha
    write_json(out,dict(case=case,campaign=campaign,manifest_sha256=manifest_sha,history=history,
        control_sha256=None if control else digest(checked),scope='Saved native equilibria at the listed load step and travel. '
        'Increment time is a load parameter. The specified printed-material coupon properties are exploratory.'))
    print(case,len(history),'sets',history[-1]['drive_N'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--campaign',default='nov08_01')
    parser.add_argument('--control',action='store_true')
    args=parser.parse_args()
    run(args.directory.resolve(),args.campaign,args.control)
