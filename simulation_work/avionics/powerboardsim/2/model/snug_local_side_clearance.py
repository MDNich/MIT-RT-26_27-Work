"""Check the local pull contact selections and the first rigid translation into the installed CAD case."""
import hashlib
import math
import re

import gmsh
import numpy as np

from audit_local import ROOT,read
from case_drawdown_geometry import first_touch
from case_fit import old, PCB_BOTTOM, PCB_CENTER
from extend_board import NODE
from film_identity import digest,verified,write_json
from stage_snug_fit import AUDIT,INPUTS,MESH,SPACING,STEP,STEP_HASH


def check_block(text,mesh,skin,pilot):
    sections=text.split('TSHAP,PILO\nE,')
    assert len(sections)==3
    groups={}
    for group,real,bodies,tags,offset,control in zip(sections[1:],(861,862),([4],[15,19,1,6,9,10,11,20]),
            ([10,11,12,13],[*range(5,46),50,51,52,53]),(1600000,1800000),(pilot,959001),strict=True):
        lines=group.splitlines()
        assert lines[0]==str(control)
        start=lines.index('TSHAP,TRIA');end=lines.index('TSHAP',start+1)
        t=np.asarray([list(map(int,line.split(',')[1:])) for line in lines[start+1:end]])
        target=np.vstack([skin[str(body)] for body in bodies])
        assert np.array_equal(t-offset,target)
        coords=np.array([[float(x) for x in line.split(',')[1:]] for line in lines[1:start]])
        ids=coords[:,0].astype(int)-offset
        assert np.array_equal(ids,np.unique(target)) and np.max(abs(coords[:,1:]-skin['points'][ids]))<1e-6
        mark=next(i for i,line in enumerate(lines[end:],end) if line.startswith('CMBLOCK,CASE_PATCH,NODE,'))
        count=int(lines[mark].split(',')[-1])
        actual=np.fromstring(' '.join(lines[mark+2:mark+2+(count+7)//8]),sep=' ',dtype=int)
        expected=np.unique(np.concatenate([mesh[str(tag)].ravel() for tag in tags]))+NODE
        assert len(actual)==count and np.array_equal(actual,expected)
        assert f'CMSEL,S,CASE_PATCH,NODE\nTYPE,862\nREAL,{real}\nMAT,862\nESURF' in group
        groups[str(real)]=dict(pilot=control,hardware_STEP_bodies=bodies,case_STEP_faces=tags,
                               target_triangles=len(t),target_nodes=len(ids),selected_PLA_nodes=count)
    return groups


def rigid_paths():
    verified(STEP,STEP_HASH)
    hardware_hash=read(ROOT/'validation/rigid_case_drawdown.json')['hardware_STEP_sha256']
    verified(old,hardware_hash)
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0)
        occ=gmsh.model.occ
        cap,=occ.importShapes(str(STEP))
        occ.synchronize()
        faces=gmsh.model.getBoundary([cap],oriented=False)
        assert {tag for dim,tag in faces}==set(range(1,54))
        centroids=np.array([occ.getCenterOfMass(*f) for f in faces])
        occ.rotate([cap],0,0,0,1,0,0,-math.pi/2)
        occ.translate([cap],*PCB_CENTER,PCB_BOTTOM-10-SPACING)
        solids=occ.importShapes(str(old));left=solids[3]
        cells=sorted([s for s in solids if 25000<occ.getMass(*s)<25400],key=lambda s:occ.getCenterOfMass(*s)[0])
        assert len(cells)==3 and cells[0]==left
        occ.synchronize()
        assert gmsh.model.getBoundary([cap],oriented=False)==faces
        expected=centroids[:,[0,2,1]]*[1,1,-1]+[*PCB_CENTER,PCB_BOTTOM-10-SPACING]
        assert np.max(abs(expected-np.array([occ.getCenterOfMass(*f) for f in faces])))<1e-7
        initial=occ.getDistance(*left,*cap)[0]
        archived=read(ROOT/'validation/alternate_case_fit.json')['Balius_native']['shortest_gaps_mm']['1.25']['4']
        assert abs(initial-archived)<1e-7
        excluded=min(occ.getDistance(*left,*face)[0] for face in faces if face[1] not in (10,11,12,13))
        pos=0.
        def gap(x):
            nonlocal pos
            if x!=pos:occ.translate([left],x-pos,0,0)
            pos=x
            return float(occ.getDistance(*left,*cap)[0])
        records={}
        for name,sign in [('positive_X',1),('negative_X',-1)]:
            gap(0.)
            lo,hi=first_touch(lambda x:gap(sign*x),stroke=.5,resolution=.00005)
            assert 0<lo<hi<=.5 and hi-lo<=.00005
            clear=gap(sign*lo);closed=gap(sign*hi)
            assert clear>1e-6 and closed<=1e-6 and excluded-hi>0
            owners={str(tag):float(occ.getDistance(*left,2,tag)[0]) for tag in (10,11,12,13)}
            assert min(owners.values())<=1e-6
            records[name]=dict(absolute_travel_clear_touch_mm=[lo,hi],signed_travel_clear_touch_mm=[sign*lo,sign*hi],
                               gaps_at_bracket_mm=[clear,closed],selected_face_gaps_at_touch_mm=owners,
                               lower_bound_to_excluded_faces_over_clearance_travel_mm=excluded-hi)
    finally:
        gmsh.finalize()
    return dict(case_STEP_sha256=STEP_HASH,hardware_STEP_sha256=hardware_hash,tab_spacing_mm=SPACING,
                initial_left_cell_gap_mm=initial,rigid_translation=records)


def run():
    series={**read(AUDIT/'local_inputs.json'),**read(AUDIT/'local_sensitivity_inputs.json')}
    groups={}
    cases={}
    registered_sha=None
    error=None
    mesh_path=MESH/'case_2.npz';target_path=MESH/'fixture_targets_0005.npz'
    mesh_sha=digest(mesh_path);target_sha=digest(target_path)
    with np.load(mesh_path) as mesh,np.load(target_path) as skin:
        for case,spec in series.items():
            assert spec['mesh_sha256']==mesh_sha and spec['target_sha256']==target_sha
            folder=INPUTS/case
            verified(folder/'local_job.json',spec['spec_sha256']);job=read(folder/'local_job.json')
            assert job['step_sha256']==STEP_HASH and job['tab_standoff_mm']==SPACING
            verified(folder/'model.inp',spec['input_sha256']);assert job['files']['model.inp']==spec['input_sha256']
            full=(folder/'model.inp').read_text()
            coord,=re.findall(r'^MP,DENS,850,1.17E-9\nTYPE,850\nMAT,850\nREAL,1\n(.*?)^EN,1200001,',full,re.M|re.S)
            coord_sha=hashlib.sha256(coord.encode()).hexdigest()
            if registered_sha is None:
                x=mesh['points']
                expected=np.column_stack((PCB_CENTER[0]+x[:,0],PCB_CENTER[1]+x[:,2],PCB_BOTTOM-10-SPACING-x[:,1]))
                nodes=np.asarray([list(map(float,line.split(',')[1:])) for line in coord.splitlines()])
                assert np.array_equal(nodes[:,0],NODE+np.arange(len(x)))
                error=float(np.max(abs(nodes[:,1:]-expected)))
                assert error<1e-7
                registered_sha=coord_sha
            assert coord_sha==registered_sha
            block,=re.findall(r'ET,861,TARGE170\n(.*?)RMODIF,861,6,-1\n',full,re.S)
            pilot=read(ROOT/'.runtime/local_inputs'/spec['source']/'mesh.json')['pilot']
            sha=hashlib.sha256(block.encode()).hexdigest()
            if sha not in groups:groups[sha]=check_block(block,mesh,skin,pilot)
            assert groups[sha]['861']['pilot']==pilot
            cases[case]=dict(input_sha256=spec['input_sha256'],contact_block_sha256=sha)
    result=rigid_paths()
    write_json(AUDIT/'local_rigid_side_clearance.json',dict(**result,case_mesh_sha256=mesh_sha,
               target_mesh_sha256=target_sha,registered_coordinates_sha256=registered_sha,
               maximum_case_coordinate_error_mm=error,cases=cases,contact_blocks=groups,
               scope='Rigid CAD translation of the left cell along PCB X with the registered case fixed. '
                     'The native fixture can rotate and deflect under nickel and clamp loads. '
                     'Its solved force onset must be determined separately from the native results.'))


if __name__=='__main__':run()
