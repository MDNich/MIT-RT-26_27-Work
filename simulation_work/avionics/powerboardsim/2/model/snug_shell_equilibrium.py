"""Replay parent displacements on the intact three-pocket shell and every original target body."""
import argparse
import re

import numpy as np

from audit_local import ROOT,read
from basis_comparison import field_files
from case_stress import source
from contact_patch import nodal_field
from contact_transient import tables
from dpf_readback import export
from extend_board import FACE_MATERIALS,component
from film_identity import digest,verified,write_json
from motion_surface import displacement_basis
from seeded_motion import FRAMES,FS,integrate,participation
from stage_local_jobs import seal
from stage_snug_fit import AUDIT,INPUTS,STEP,STEP_HASH


def solid_parts(rst):
    grid=rst.grid.cell_data
    enum=rst.mesh.enum
    order=np.argsort(enum)
    parts={}
    for material in [*FACE_MATERIALS,850]:
        pick=(grid['ansys_material_type']==material)&np.isin(grid['ansys_elem_type_num'],[186,187])
        et,=np.unique(grid['ansys_elem_type_num'][pick])
        es=np.sort(grid['ansys_elem_num'][pick])
        ix=order[np.searchsorted(enum[order],es)]
        assert np.array_equal(enum[ix],es)
        conn=np.stack([rst.mesh.elem[i][10:] for i in ix])
        assert conn.shape==(len(es),20 if et==186 else 10) and conn.min()>0
        parts[material]=(int(et),es,conn,np.unique(conn))
    return parts


def base_model(rst,parts,deck,nodes):
    where=np.searchsorted(rst.mesh.nnum,nodes)
    assert np.array_equal(rst.mesh.nnum[where],nodes)
    lines=['/batch','/prep7','csys,0','esys,0','/nopr']
    lines.extend(f'n,{n},{x:.16g},{y:.16g},{z:.16g}' for n,(x,y,z) in zip(nodes,rst.mesh.nodes[where],strict=True))
    for material,(et,es,conn,_) in parts.items():
        lines.extend([f'et,{material},{et}',f'mat,{material}',f'type,{material}','esys,0'])
        option=re.findall(rf'(?im)^keyo(?:pt)?,{material},[^!\n]+',deck)
        lines.extend(line.strip() for line in option)
        keys=['EX','NUXY','DENS'] if material!=850 else ['EX','EY','EZ','PRXY','PRYZ','PRXZ','GXY','GYZ','GXZ','DENS']
        for key in keys:
            value,=re.findall(rf'(?im)^MP,{key},{material},([^,\s]+)',deck)
            lines.append(f'mp,{key},{material},{value}')
        # COMPACT follows the current material, element type and element coordinate system.
        width=conn.shape[1]+1
        lines.extend([f'eblock,{width},compact,,{len(es)}',f'({width}i9)'])
        lines.extend(''.join(f'{x:9d}' for x in entry) for entry in np.column_stack((es,conn)))
        lines.append('-1')
    lines+=['allsel,all','esel,s,type,,850','cm,CASEPLA,elem','allsel,all']
    return lines


def boundary_history(variant,campaign):
    record=read(AUDIT/'global_inputs.json')[variant+'_static']
    verified(STEP,record['step_sha256']);assert record['step_sha256']==STEP_HASH and record['tab_spacing_mm']==1.25
    static,d,rst=source(variant+'_static',campaign)
    modal,folder,modes=source(variant+'_basis',campaign)
    parent=d/'model.inp';verified(parent,record['input_sha256']);deck=parent.read_text()
    parts=solid_parts(rst)
    hardware=np.concatenate([parts[m][3] for m in FACE_MATERIALS])
    shell=parts[850][3]
    assert len(hardware)==len(np.unique(hardware)) and not np.intersect1d(hardware,shell).size
    pairs=re.findall(r'(?im)^CERIG,(95000[1357]),(\d+),UXYZ\s*$',deck)
    assert {int(p) for p,n in pairs}=={950001,950003,950005,950007}
    bearing=np.array(sorted({int(n) for p,n in pairs}))
    assert np.all(np.isin(bearing,shell)) and len(bearing)==sum(p['bearing_nodes'][1] for p in record['supports'])
    nodes=np.union1d(hardware,shell);driven=np.union1d(hardware,bearing)
    loc=np.searchsorted(nodes,driven)
    fields=export(static['case'],campaign,list(range(1,rst.nsets+1)))
    saved=np.stack([nodal_field(fields/f'set_{k:04d}',nodes) for k in range(1,rst.nsets+1)])
    a=np.searchsorted(rst.mesh.nnum,nodes);b=np.searchsorted(modes.mesh.nnum,nodes)
    assert np.array_equal(modes.mesh.nnum[b],nodes)
    assert np.max(abs(rst.mesh.nodes[a]+saved[-1]-modes.mesh.nodes[b]))<1.e-9
    locator=AUDIT/(variant+'_replay_window.json')
    choices=read(locator)
    assert choices['basis_sha256']==modal['rst_sha256'] and choices['campaign']==campaign
    samples=np.r_[choices['choice']['samples'],FRAMES[352]].astype(int)
    source_motion=read(ROOT/'validation/independent_motion'/(variant+'_motion_Z.json'))
    listing=folder/'solve.out';verified(listing,source_motion['modal_listing_sha256'])
    assert source_motion['basis_rst_sha256']==modal['rst_sha256']
    times,q,_=integrate(modes.time_values,participation(listing.read_text(errors='replace'),'Z'),'Z',samples)
    assert np.array_equal(times,samples/FS)
    shapes=displacement_basis(modes,nodes,field_files(modal['case'],campaign,modal['rst_sha256'],modes.nsets))
    moved=saved[-1]+(q@shapes.reshape(modes.nsets,-1)).reshape(len(q),len(nodes),3)
    u=np.concatenate((np.zeros_like(saved[:1]),saved,moved,saved[-1:]),axis=0)
    t=np.r_[0.,rst.time_values,[2.25,2.5,2.75,3.]]
    assert len(t)==len(u)==13 and np.all(np.diff(t)>0)
    root=ROOT/'.runtime/shell_fixture'/campaign/variant
    root.mkdir(parents=True,exist_ok=True);cache=root/'parent_fields.npz'
    if not cache.exists():
        tmp=cache.with_suffix('.new.npz')
        np.savez_compressed(tmp,nodes=nodes,driven=driven,bearing=bearing,t=t,u=u)
        tmp.replace(cache)
    with np.load(cache) as f:
        for key,data in [('nodes',nodes),('driven',driven),('bearing',bearing),('t',t),('u',u)]:
            assert np.array_equal(f[key],data)
    mat_to_body={r['native_material']:r['STEP_body'] for r in read(ROOT/'validation/rigid_case_drawdown.json')['records']}
    assert all(m in mat_to_body for m in FACE_MATERIALS)
    metadata=dict(variant=variant,campaign=campaign,step_sha256=STEP_HASH,spacing_mm=1.25,
        static_case=static['case'],static_rst_sha256=static['rst_sha256'],static_deck_sha256=record['input_sha256'],
        basis_case=modal['case'],basis_rst_sha256=modal['rst_sha256'],drive_field_sha256=digest(cache),
        replay_window_sha256=digest(locator),number_of_nodes=len(nodes),driven_nodes=len(driven),
        bearing_nodes=len(bearing),hardware_nodes=len(hardware),PLA_nodes=len(shell),
        solids={m:len(group[1]) for m,group in parts.items()},body_ids={m:mat_to_body[m] for m in FACE_MATERIALS},
        preload_times=rst.time_values.tolist(),load_stations=t[1:].tolist(),base_Z_samples=samples.tolist(),
        time_s_in_global_history=times.tolist(),separate_return_to_lock=True)
    target_mat,=np.unique(rst.grid.cell_data['ansys_material_type'][rst.grid.cell_data['ansys_etype']==852])
    assert target_mat==851
    target_attributes=[]
    for key in ['EX','PRXY','DENS']:
        value,=re.findall(rf'(?im)^MP,{key},{target_mat},([^,\s]+)',deck)
        target_attributes.append(f'mp,{key},{target_mat},{value}')
    target_attributes.append(f'mat,{target_mat}')
    metadata['target_material_id']=int(target_mat)
    return metadata,parts,base_model(rst,parts,deck,nodes),target_attributes,driven,t,u[:,loc]


def contact_cards(target_attributes):
    lines=['et,852,targe170','et,853,conta174','keyopt,853,9,2','keyopt,853,12,0','mp,mu,853,0',
           'r,853','rmodif,853,6,-.0006','real,853','type,852']
    lines.extend(target_attributes)
    for i,m in enumerate(FACE_MATERIALS):
        lines.append(f'esel,{"s" if i==0 else "a"},mat,,{m}')
    lines+=['esel,r,ename,,185,187','nsle,s','esurf','allsel,all','esel,s,type,,850','nsle,s',
            'type,853','real,853','mat,853','esurf','allsel,all','esel,s,type,,853','cm,CASECONTACT,elem',
            '*get,ncap,elem,0,count','*if,ncap,ne,16596,then','*msg,fatal','Wrong shell-face count.','*endif',
            'esel,s,type,,852','*get,ntar,elem,0,count','*if,ntar,ne,9466,then','*msg,fatal',
            'Wrong hardware-face count.','*endif','allsel,all']
    return lines


def stage(variant,campaign):
    metadata,parts,base,target_attributes,driven,t,u=boundary_history(variant,campaign)
    cases={}
    for kind in ('free','contact'):
        case=f'shell_{variant}_{kind}_v2'
        folder=INPUTS/case;folder.mkdir(parents=True,exist_ok=True)
        # Identity time coefficients give the exact archived displacement at each station.
        commands,files=tables(folder,driven,t,np.eye(len(t)),u.transpose(1,2,0),np.zeros(len(t)))
        lines=base.copy()
        if kind=='contact':lines+=contact_cards(target_attributes)
        component(lines,'PBPORTS',driven)
        lines+=['allsel,all',*commands,'finish','/solu','antype,static','nlgeom,on','nropt,full',
                'kbc,0','autots,on','neqit,60','cnvtol,f,,1e-5,2,.01','outres,all,none',
                'outres,nsol,last','outres,rsol,last','outres,strs,last,CASEPLA']
        if kind=='contact':
            lines+=['cncheck,detail,853,853','outres,cont,last,CASECONTACT','outres,misc,last,CASECONTACT']
        lines+=['d,PBPORTS,ux,%cutx%','d,PBPORTS,uy,%cuty%','d,PBPORTS,uz,%cutz%','/gopr']
        for time in t[1:]:
            lines+=[f'time,{time:.14g}','nsubst,2,200,1','solve']
        lines+=['finish','/post1','set,last','/com,PB_SHELL_PATH_COMPLETE','finish','/exit,nosave']
        files['model.inp']=seal(folder/'model.inp',('\n'.join(lines)+'\n').encode())
        cases[case]=dict(**metadata,case=case,contact=(kind=='contact'),files=files,
            scope='Complete registered PLA shell. Relative hardware and PLA bearing-node displacements are imposed '
                  'at the eight parent preload equilibria, three base-Z waveform snapshots and return to lock. '
                  'The case interior re-equilibrates and all 15 original contact targets are present. '
                  'Static snapshot loading excludes transient inertia and feedback into the board.')
    write_json(AUDIT/(variant+'_shell_inputs_v2.json'),cases)
    print(variant,metadata['number_of_nodes'],len(driven),'prescribed,',len(parts)-1,'target bodies')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=('snug125_nylon','snug125_aluminium'))
    p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();stage(a.variant,a.campaign)
