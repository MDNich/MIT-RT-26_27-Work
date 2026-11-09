"""Give PFACT a separate writable modal family for each native spectrum solve."""
import ctypes
import fcntl
import os
import re
import sys

from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from stage_local_jobs import seal
from stage_remote_psd import stage_library,win

def case_name(branch,axis):
    assert axis in ('X','Y','Z')
    return f'{branch}_psd_{axis}_private1'

def stage(branch,campaign,axis):
    case=case_name(branch,axis)
    parent,proof,pristine,manifest,files,total=stage_library(branch,campaign)
    rt=ROOT/'.runtime'
    receipt=rt/'receipts'/campaign/case
    folder=rt/'inputs'/case
    pub=ROOT/'validation/private_psd_inputs'/f'{case}.json'
    if (receipt/'dispatch.json').exists():
        assert read(pub)['spec_sha256']==digest(folder/'private_psd.json')
        return
    lib=rt/'private_modal'/campaign/case
    lib.mkdir(parents=True,exist_ok=True);folder.mkdir(exist_ok=True)
    with (lib.parent/(case+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        clone=ctypes.CDLL(None,use_errno=True).clonefile
        clone.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
        for name,expected in files.items():
            src=pristine/name;dst=lib/name
            if not dst.exists():
                verified(src,expected)
                if clone(os.fsencode(src),os.fsencode(dst),0):raise OSError(ctypes.get_errno(),'APFS clone failed')
                dst.chmod(0o600)
            assert src.stat().st_ino!=dst.stat().st_ino and src.stat().st_mode&0o222==0 and dst.stat().st_mode&0o200
            verified(dst,expected)
        seed=ROOT/f'.runtime/inputs/bare_psd_{axis}/model.inp'
        data=seed.read_bytes();marks=list(re.finditer(rb'(?im)^antype,spectr(\r?\n)',data))
        assert len(marks)==1 and b'moddir,' not in data.lower()
        at=marks[0].end();eol=marks[0][1]
        path=win(lib);assert len(path)<248
        deck=data[:at]+f"MODDIR,ON,'{path}',file".encode()+eol+b'MODDIR,LIST'+eol+data[at:]
        expected=seal(folder/'model.inp',deck)
        spec=dict(case=case,campaign=campaign,parent=parent,parent_rst_sha256=proof['rst_sha256'],parent_db_sha256=files['file.db'],
                  modal_dir=path,parent_manifest_sha256=digest(manifest),input_sha256=expected,source_psd_sha256=digest(seed))
        sp=folder/'private_psd.json'
        if sp.exists():assert read(sp)==spec
        else:write_json(sp,spec)
        record=dict(**spec,spec_sha256=digest(sp),logical_parent_bytes=total,number_of_parent_files=len(files))
        if pub.exists():assert read(pub)==record
        else:write_json(pub,record)

def verify(case,campaign):
    rt=ROOT/'.runtime';d=rt/'archive'/campaign/case
    p=read(ROOT/'validation/private_psd_inputs'/f'{case}.json')
    s=read(d/'private_psd.json')
    assert s['case']==case and s['campaign']==campaign and p['spec_sha256']==digest(d/'private_psd.json')
    assert s['input_sha256']==digest(d/'model.inp') and p['parent_rst_sha256']==s['parent_rst_sha256']
    root=rt/'modal_library'/campaign
    m=root/(s['parent']+'.json');assert digest(m)==s['parent_manifest_sha256']
    hashes=read(m)['files'];scratch=rt/'private_modal'/campaign/case
    assert win(scratch)==s['modal_dir'] and s['modal_dir'].lower() in (d/'solve.out').read_text(errors='replace').lower()
    changes={}
    for name,h in hashes.items():
        src=root/s['parent']/name
        verified(src,h)
        dst=scratch/name
        if not dst.exists():
            changes[name]='removed from private copy'
            continue
        assert dst.stat().st_ino!=src.stat().st_ino
        updated=digest(dst)
        if updated!=h:changes[name]=updated
    return dict(unchanged_reference_files=len(hashes),private_files_changed=changes,
                private_files_added=sorted(p.name for p in scratch.iterdir() if p.name not in hashes),
                parent_rst_sha256=s['parent_rst_sha256'],input_sha256=s['input_sha256'])
if __name__=='__main__':stage(*sys.argv[1:])
