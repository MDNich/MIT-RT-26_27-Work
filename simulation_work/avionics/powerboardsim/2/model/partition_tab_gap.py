"""Recover the deformed tab/board surfaces and the relative screw travel from a sealed distributed checkpoint."""
import argparse
import fcntl
import subprocess
import sys
from pathlib import Path

import numpy as np

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from installed_tab_gap import gap_on_overlap,patch_volumes,plane_controls,triangles
from native_rst import read_rst
from stage_remote_psd import win


def export(folder, manifest, ids, sets, key):
    directory=ROOT/'.runtime/post'/manifest['campaign']/manifest['case']/'partition_DPF'/key
    directory.mkdir(parents=True,exist_ok=True)
    lock=(directory/'lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX)
    domains=[f'file{i}.rst' for i in range(manifest['cores'])]
    for name in domains:
        verified(folder/name,manifest['files'][name]['SHA256'])
    q=dict(domains=domains,nodes=ids.tolist(),sets=sets,source_sha256=digest(folder/'receipts.json'))
    request=directory/'request.json'
    if request.is_file():assert read(request)==q
    else:write_json(request,q)
    if not (directory/'done.json').is_file():
        if (directory/'dispatch.json').is_file():raise RuntimeError('Inspect the existing DPF export before retrying')
        script=ROOT/'model/dpf_tab_points.py'
        ipy=r'C:\Program Files\ANSYS Inc\v261\commonfiles\IronPython\ipy64.exe'
        ps="& '{}' '{}' '{}' '{}'\nexit $LASTEXITCODE".format(ipy,win(script),win(folder),win(directory))
        write_json(directory/'dispatch.json',dict(request_sha256=digest(request),script_sha256=digest(script)))
        r=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout','900'],
                         input=ps,text=True,capture_output=True)
        (directory/'export.log').write_text(r.stdout+r.stderr)
        if r.returncode or not (directory/'done.json').is_file():raise RuntimeError((r.stdout+r.stderr)[-1500:])
    done=read(directory/'done.json')
    assert done['unit']=='m' and done['nodes']==len(ids) and done['sets']==sets and done['source_sha256']==q['source_sha256']
    field=np.fromfile(directory/'displacements.bin','<f8').reshape(len(sets),len(ids),3)
    assert np.isfinite(field).all()
    return field,digest(directory/'displacements.bin')


def check_geometry(ref, domains, folder, manifest):
    skin_ids=np.unique(np.concatenate([domain.point_data['ansys_node_num'] for domain in domains]))
    ref_rows=np.searchsorted(ref.mesh.nnum,skin_ids)
    assert np.array_equal(ref.mesh.nnum[ref_rows],skin_ids)
    # The raised archive supplies connectivity only. Compare all selected solid parents and
    # face nodes with the actual distributed fixture before using them for interpolation.
    elements=np.unique(np.concatenate([domain.cell_data['ansys_elem_num'] for domain in domains]))
    def topology(r):
        mask=np.flatnonzero(np.isin(r.mesh.enum,elements))
        raw=r.mesh.elem
        return {int(r.mesh.enum[i]):raw[i][10:].tolist() for i in mask}
    target=topology(ref); seen=set()
    found=np.zeros(len(skin_ids),dtype=bool)
    for i in range(manifest['cores']):
        raw=read_rst(folder/f'file{i}.rst')
        actual=topology(raw)
        assert not (set(actual)&seen)
        assert all(v==target[k] for k,v in actual.items())
        seen.update(actual)
        shared,here,there=np.intersect1d(raw.mesh.nnum,skin_ids,return_indices=True)
        assert np.array_equal(raw.mesh.nodes[here],ref.mesh.nodes[ref_rows[there]])
        found[there]=True
    assert seen==set(elements) and found.all()
    return skin_ids, len(elements)


def run(folder):
    folder=folder.resolve()
    manifest=read(folder/'receipts.json')
    case,camp=manifest['case'],manifest['campaign']
    assert folder.parent.name==case and folder.parent.parent.name==camp
    refcase='stand3_nylon_static' if 'nylon' in case else 'stand3_aluminium_static'
    proof=read(ROOT/'validation/global'/(refcase+'.json'))
    refpath=ROOT/'.runtime/archive'/camp/refcase/'file.rst'
    verified(refpath,proof['rst_sha256'])
    ref=read_rst(refpath)
    initial=read(ROOT/'validation/board_surface_initial.json')
    facefile=ROOT/'.runtime/board_surface_initial_v1/seat_faces.csv'
    verified(facefile,initial['faces_sha256'])
    plane_controls()
    inventory=table(facefile)
    sides=[patch_volumes(ref,inventory,mat,typ,z) for mat,typ,z in
           [(850,858,-3.55118),(208,857,-.55118)]]
    skin_ids, parent_count=check_geometry(ref,[domain for side in sides for domain in side.values()],folder,manifest)
    raw=read_rst(folder/'file0.rst',read_mesh=False)
    points=np.unique(np.r_[skin_ids,range(960101,960105),range(960111,960115),range(950002,950010,2)])
    sets=list(range(1,manifest['sets']+1))
    fields,sha=export(folder,manifest,points,sets,folder.name)
    times=raw.time_values
    gaps={}
    worst_diff=0.
    for k,u in enumerate(fields):
        travel=u[np.searchsorted(points,np.arange(960111,960115)),2]*1000
        relative=(u[np.searchsorted(points,np.arange(950002,950010,2)),2]
                  -u[np.searchsorted(points,np.arange(960101,960105)),2])*1000
        expected=3*np.clip(times[k]-2,0,1)
        assert np.allclose(travel,expected,rtol=0,atol=2e-7) and np.allclose(relative,expected,rtol=0,atol=2e-7)
        worst_diff=max(worst_diff,float(abs(relative-travel).max()))
        if k!=len(fields)-1 and expected<1.5:continue
        levels={}
        for subdiv in (1,2):
            levels[subdiv]={}
            for pair in range(880,884):
                patches=[triangles(side[pair],ref,z,subdiv,(points,u)) for side,z in zip(sides,(-3.55118,-.55118),strict=True)]
                levels[subdiv][pair]=gap_on_overlap(*patches,seating_area=True)
        gaps[k+1]=dict(travel_mm=float(expected),levels=levels)
    dest=ROOT/'validation/partition_checks'/case/(folder.name+'_gap.json')
    write_json(dest,dict(case=case,campaign=camp,checkpoint_sha256=digest(folder/'receipts.json'),DPF_sha256=sha,
        geometry_reference_sha256=proof['rst_sha256'],native_face_inventory_sha256=initial['faces_sha256'],
        checked_skin_parent_elements=parent_count,checked_skin_parent_nodes=len(skin_ids),sets=sets,
        largest_head_minus_board_vs_command_error_mm=worst_diff,gaps=gaps))
    print(case,folder.name, {p:round(v['minimum_gap_mm'],5) for p,v in levels[2].items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('snapshot',type=Path)
    run(p.parse_args().snapshot)
