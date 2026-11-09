"""Stage native PSD with a read-only modal-file directory, keeping Windows scratch free for new results."""
import ctypes,fcntl,hashlib,os,re,shutil,sys
from pathlib import Path
from audit_local import ROOT,read
from film_identity import verified,write_json,digest
from stage_local_jobs import seal
FILES=re.compile(r'^file\d*\.(db|mode|mlv|full|esav|emat|rst|dsp)$',re.I)

def stage_library(branch,campaign):
    assert branch=='stand3_nylon_mesh2' or re.fullmatch(r'(stand3|flush)_(nylon|aluminium)(?:_surf1)?|snug125_(nylon|aluminium)',branch)
    case=branch+'_basis';r=ROOT/'.runtime/receipts'/campaign/case
    assert (r/'released.txt').is_file()
    ledger=read(r/'archived.json');proof=read(ROOT/'validation/global'/f'{case}.json')
    assert case==proof['case']==ledger['case'] and campaign==proof['campaign']==ledger['campaign']
    source=ROOT/'.runtime/archive'/campaign/case
    lib=ROOT/'.runtime/modal_library'/campaign/case;lib.mkdir(parents=True,exist_ok=True)
    lock=(lib.parent/(case+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    files={x['name']:x['sha256'] for x in ledger['files'] if FILES.fullmatch(x['name'])}
    assert {'file.db','file.mode','file.mlv','file.rst'}.issubset(files) and proof['rst_sha256']==files['file.rst']
    total=0
    libc=ctypes.CDLL(None,use_errno=True);clone=libc.clonefile;clone.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
    for name,h in files.items():
        src=source/name;path=lib/name
        if not path.exists():
            if shutil.disk_usage(ROOT).free<425_000_000_000:raise RuntimeError('Host headroom insufficient')
            verified(src,h)
            # An APFS clone is an independent inode. Refuse fallback to a hard link or a shared mutable file.
            if clone(os.fsencode(src),os.fsencode(path),0):raise OSError(ctypes.get_errno(),'APFS clone failed')
            path.chmod(0o444)
        assert src.stat().st_ino!=path.stat().st_ino and path.stat().st_mode&0o222==0
        verified(path,h);total+=path.stat().st_size
    assert set(p.name for p in lib.iterdir())==set(files)
    manifest=lib.parent/(case+'.json');info=dict(case=case,campaign=campaign,bytes=total,files=files)
    if manifest.exists():assert read(manifest)==info
    else:write_json(manifest,info)
    return case,proof,lib,manifest,files,total

def win(p):return chr(92)*2+'Mac'+chr(92)+'Home'+chr(92)+str(p.relative_to('/Users/mdn')).replace('/',chr(92))

def stage(branch,campaign):
    case,proof,lib,manifest,files,total=stage_library(branch,campaign)
    assert len(win(lib))<248 and "'" not in win(lib)
    records={}
    for ax in 'XYZ':
        k=branch+'_psd_'+ax;base=ROOT/f'.runtime/inputs/bare_psd_{ax}/model.inp';raw=base.read_bytes()
        marks=list(re.finditer(rb'(?im)^antype,spectr(\r?\n)',raw));assert len(marks)==1 and b'moddir,' not in raw.lower()
        pos=marks[0].end();eol=marks[0][1]
        deck=raw[:pos]+("MODDIR,ON,'"+win(lib)+"',file").encode()+eol+b'MODDIR,LIST'+eol+raw[pos:]
        dst=ROOT/'.runtime/inputs'/k;dst.mkdir(exist_ok=True)
        assert not (ROOT/'.runtime/receipts'/campaign/k/'dispatch.json').exists() or (dst/'model.inp').exists()
        sha=seal(dst/'model.inp',deck)
        spec=dict(case=k,campaign=campaign,parent=case,parent_rst_sha256=proof['rst_sha256'],input_sha256=sha,
                  modal_dir=win(lib),library_manifest_sha256=digest(manifest),parent_db_sha256=files['file.db'])
        if (dst/'remote_psd.json').exists():assert read(dst/'remote_psd.json')==spec
        else:write_json(dst/'remote_psd.json',spec)
        records[k]=dict(model_sha256=sha,spec_sha256=digest(dst/'remote_psd.json'),source_psd_deck_sha256=digest(base))
    write_json(ROOT/'validation/remote_psd_inputs'/f'{branch}.json',dict(parent=case,campaign=campaign,logical_modal_bytes=total,
        library_files=len(files),library_manifest_sha256=digest(manifest),cases=records,
        scope='Physical PSD instructions unchanged; remote modal read-only access inserted. Acceptance requires a native PSD solve, unchanged parent library, and set/field/units audit.'))
    return records

def verify(case,campaign):
    branch,axis=case.rsplit('_psd_',1);assert axis in ('X','Y','Z')
    d=ROOT/'.runtime/archive'/campaign/case;spec=read(d/'remote_psd.json')
    pub=read(ROOT/'validation/remote_psd_inputs'/f'{branch}.json')
    assert spec['case']==case and spec['campaign']==campaign and spec['parent']==pub['parent']==branch+'_basis'
    assert digest(d/'model.inp')==spec['input_sha256']==pub['cases'][case]['model_sha256']
    assert digest(d/'remote_psd.json')==pub['cases'][case]['spec_sha256']
    lib=ROOT/'.runtime/modal_library'/campaign/spec['parent'];m=lib.parent/(spec['parent']+'.json')
    assert digest(m)==spec['library_manifest_sha256']==pub['library_manifest_sha256']
    for n,h in read(m)['files'].items():verified(lib/n,h)
    listing=(d/'solve.out').read_text(errors='replace')
    assert re.search(r'MODDIR|REMOTE MODAL',listing,re.I)
    return dict(parent=spec['parent'],parent_rst_sha256=spec['parent_rst_sha256'],library_manifest_sha256=digest(m),
                parent_files_verified_after_solve=len(read(m)['files']))

if __name__=='__main__':stage(*sys.argv[1:])
