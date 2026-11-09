"""Archive a completed Mac-backed MAPDL job as independently hashed APFS clones."""
import ctypes
import fcntl
import os

from film_identity import ROOT,digest,write_json
from audit_local import read
from stage_remote_psd import win


def copy_family(source,destination):
    destination.mkdir(parents=True,exist_ok=True)
    clone=ctypes.CDLL(None,use_errno=True).clonefile
    clone.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
    records=[]
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.is_symlink():raise ValueError(f'Unexpected scratch entry {path}')
        before=path.stat()
        sha=digest(path)
        target=destination/path.name
        if not target.exists():
            if clone(os.fsencode(path),os.fsencode(target),0):raise OSError(ctypes.get_errno(),'APFS archive clone failed')
        after=path.stat();snapshot=target.stat()
        assert (before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns)
        assert snapshot.st_ino!=after.st_ino and snapshot.st_size==after.st_size and digest(target)==sha
        records.append(dict(name=path.name,bytes=after.st_size,sha256=sha))
    assert {p.name for p in destination.iterdir()}=={r['name'] for r in records}
    return records


def archive(case,campaign):
    rt=ROOT/'.runtime';receipt=rt/'receipts'/campaign/case
    state=read(receipt/'status.json')
    source=rt/'shared_native'/campaign/case
    assert state['case']==case and state['phase']=='solver_complete' and state['shared_scratch']
    assert state['work'].casefold()==win(source).casefold()
    assert not list(receipt.glob('archive_request*.json')) and not (receipt/'archive.lock').exists()
    with (receipt/'host_archive.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        records=copy_family(source,rt/'archive'/campaign/case)
        hashes={r['name']:r['sha256'] for r in records}
        assert hashes['model.inp']==state['input_sha256'].lower() and 'file.rst' in hashes and 'solve.out' in hashes
        if (receipt/'archived.json').exists():assert read(receipt/'archived.json')['files']==records
        else:
            write_json(receipt/'archived.json',dict(case=case,campaign=campaign,source=state['work'],
                method='Independent APFS clone per file, both full SHA-256 hashes checked',files=records))
        (receipt/'released.txt').write_text('Shared solve closed; independently checked archive and original retained.\n')
