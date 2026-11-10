"""Track the actual PCB-facing tab surfaces against the local fixture's nominal board plane (N, mm)."""
import numpy as np
from ansys.mapdl import reader
from film_identity import ROOT,write_json
from local_equilibrium import positions
from extend_board import NODE

Z_BOARD=-.55118
FACES=(33,29,25,37)
SIGNS=((-1,-1),(-1,1),(1,-1),(1,1))

def read_point_file(path,out,sha,sets,points):
    """Read selected native translations from a verified stationary RST; return millimetres."""
    import fcntl,json,subprocess,sys
    from film_identity import digest,verified
    path=path.resolve();out=out.resolve()
    verified(path,sha)
    assert len(points)==len(set(points)) and sorted(sets)==list(sets) and len(sets)==len(set(sets))
    q=dict(nodes=points,sets=sets,source_sha256=sha)
    out.mkdir(parents=True,exist_ok=True)
    lock=(out/'request.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    req=out/'request.json'
    if req.exists():assert json.loads(req.read_text())==q
    else:write_json(req,q)
    if not (out/'done.json').exists():
        if (out/'dispatch.json').exists():raise RuntimeError('Uncertain existing DPF readback; inspect its guest process before retry')
        def win(p):return chr(92)*2+'Mac'+chr(92)+'Home'+chr(92)+str(p.relative_to('/Users/mdn')).replace('/',chr(92))
        ipy=r'C:\Program Files\ANSYS Inc\v261\commonfiles\IronPython\ipy64.exe'
        command="& '{}' '{}' '{}' '{}'\nexit $LASTEXITCODE".format(ipy,win(ROOT/'model/dpf_tab_points.py'),win(path),win(out))
        write_json(out/'dispatch.json',dict(source_sha256=sha,reader_sha256=digest(ROOT/'model/dpf_tab_points.py')))
        run=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout','3600'],input=command,text=True,capture_output=True)
        (out/'export.log').write_text(run.stdout+run.stderr)
        if run.returncode or 'DPF_TAB_POINTS_DONE' not in run.stdout:raise RuntimeError((run.stdout+run.stderr)[-2500:])
    audit=json.loads((out/'done.json').read_text())
    assert audit['source_sha256']==sha and audit['sets']==sets and audit['nodes']==len(points)
    fields=np.fromfile(out/'displacements.bin','<f8').reshape(len(sets),len(points),3)*{'m':1000.,'mm':1.}[audit['unit'].lower()]
    assert np.isfinite(fields).all()
    return fields,audit


def point_fields(raw,sets,points,*,field_directory='tab_points_v1'):
    import json
    from pathlib import Path
    from film_identity import verified,digest
    from local_equilibrium import movement_table
    path=Path(raw.filename).resolve();folder=path.parent
    assert path.name in ('pull.rst','tear.rst') and folder.parent.parent==ROOT/'.runtime/archive'
    case,campaign=folder.name,folder.parent.name
    meta=json.loads((ROOT/'.runtime/receipts'/campaign/case/'archived.json').read_text(encoding='utf-8-sig'))
    sha=next(f['sha256'] for f in meta['files'] if f['name']==path.name)
    assert (case,campaign)==(meta['case'],meta['campaign']);verified(path,sha)
    native=movement_table(folder/'moving_supports.csv')
    points=sorted(set(map(int,points))|{int(n) for k,n in native});sets=list(map(int,sets))
    assert field_directory in ('tab_points_v1','first_loaded_corners_v1','pull_case_energy','pull_pose','edge_cell_poses','tab_bearing_motion')
    out=ROOT/'.runtime/post'/campaign/case/field_directory
    fields,audit=read_point_file(path,out,sha,sets,points)
    ref=np.array([v for (k,n),v in native.items() if k in sets]);ix={n:i for i,n in enumerate(points)};sidx={k:i for i,k in enumerate(sets)}
    recovered=np.array([fields[sidx[k],ix[n]] for k,n in native if k in sidx])
    assert abs(ref).max()>1e-8 and np.allclose(ref,recovered,rtol=5e-6,atol=1e-7), (abs(ref-recovered).max(),abs(ref).max(),abs(recovered).max())
    control=dict(rst_sha256=sha,export_sha256=digest(out/'displacements.bin'),input_node_count=len(points),sets=len(sets),
                 DPF_unit=audit['unit'],POST1_reference_rows=len(ref),max_pilot_component_error_mm=float(abs(ref-recovered).max()))
    write_json(out/'pilot_audit.json',control)
    return np.array(points),fields


def trace(raw,sets,initial_gap=3.):
    mesh=np.load(ROOT/'.runtime/mesh/case_3.npz');p=mesh['points']
    nums=raw.mesh.nnum;coords=raw.mesh.nodes;patches=[]
    for tag,(sx,sy) in zip(FACES,SIGNS,strict=True):
        ids=np.unique(mesh[str(tag)])
        # Inspect the four near-hole bearing regions. Exclude the PCB bore rather than
        # treating its empty centre as a support. The nominal plane is rigid in this fixture.
        expected=np.column_stack((34.6075+p[ids,0],60.3885+p[ids,2],Z_BOARD-10-initial_gap-p[ids,1]))
        board_xy=np.array([34.6075+sx*31.4325,60.3885+sy*57.2135])
        rad=np.linalg.norm(expected[:,:2]-board_xy,axis=1)
        keep=(rad>=2.1)&(rad<=3.75)&(expected[:,0]>=0)&(expected[:,0]<=69.215)&(expected[:,1]>=0)&(expected[:,1]<=120.777)
        ids=ids[keep]+NODE;expected=expected[keep]
        assert len(ids)>10 and np.allclose(expected[:,2],Z_BOARD-initial_gap,rtol=0,atol=1e-7)
        assert np.allclose(coords[positions(nums,ids)],expected,rtol=0,atol=1e-7)
        patches.append(ids)
    sets=list(sets);ids,all_u=point_fields(raw,sets,np.concatenate(patches));hist=[]
    for j,k in enumerate(sets):
        u=all_u[j];values=[]
        for patch in patches:
            uz=u[positions(ids,patch),2].astype(float)
            assert np.isfinite(uz).all()
            gap=initial_gap-uz
            values.append(dict(samples=len(gap),min_mm=float(gap.min()),median_mm=float(np.median(gap)),max_mm=float(gap.max())))
        hist.append(dict(native_set=int(k),time=float(raw.time_values[k-1]),tabs=values))
    return hist


def control():
    from audit_local import read
    key='stand3_nylon_lateral_friction_locked_pin1';proof=read(ROOT/'validation/local'/f'{key}.json')
    raw=reader.read_binary(str(ROOT/'.runtime/archive'/proof['campaign']/key/'pull.rst'))
    data=trace(raw,range(1,raw.nsets+1))
    def extrema(row):return [min(x['min_mm'] for x in row['tabs']),max(x['max_mm'] for x in row['tabs'])]
    initial=extrema(data[0]);assert np.allclose(initial,[3.,3.],rtol=0,atol=.0001)
    assert all(min(extrema(row))>2.5 for row in data)
    write_json(ROOT/'validation/tab_plane_reader.json',dict(control_case=key,rst_sha256=proof['rst_sha256'],states=len(data),
        pilot_check=read(ROOT/'.runtime/post'/proof['campaign']/key/'tab_points_v1/pilot_audit.json'),
        faces=list(FACES),first_loaded_state_gap_range_mm=initial,endpoint=data[-1],endpoint_gap_range_mm=extrema(data[-1]),
        scope='Fixed local PCB datum at z=-0.55118 mm; actual deformed PLA tab nodes within the nominal bearing region. Positive means clearance, negative means crossing. This does not measure contact pressure.'))

if __name__=='__main__':control()
