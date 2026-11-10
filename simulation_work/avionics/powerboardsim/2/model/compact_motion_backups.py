"""Share APFS blocks between verified duplicate restart backups from closed seeded-motion runs."""
import ctypes
import fcntl
import os
import shutil
import stat
import struct
import tempfile
from pathlib import Path

from archive_shared import clone_file
from audit_local import ROOT, read
from film_identity import digest, verified, write_json

CAMPAIGN = 'nov08_01'
RUNTIME = ROOT/'.runtime'
LIB = ctypes.CDLL(None, use_errno=True)
CLONE_ATTRIBUTES = 0x1108  # ATTR_CMNEXT_PRIVATESIZE, CLONEID, CLONE_REFCNT
BIRTH_TIME = 0x200        # ATTR_CMN_CRTIME


def attributes(path, common, extended):
    request = struct.pack('=HHIIIII', 5, 0, common | 0x80000000, 0, 0, 0, extended)
    buf = ctypes.create_string_buffer(96)
    if LIB.getattrlist(os.fsencode(path), request, buf, len(buf), 0x20 if extended else 0):
        raise OSError(ctypes.get_errno(), 'getattrlist failed', str(path))
    length, returned, _, _, _, ext = struct.unpack_from('=6I', buf)
    assert returned == common | 0x80000000 and ext == extended
    return buf.raw[24:length]


def clone_attributes(path):
    return struct.unpack('=QQI', attributes(path, 0, CLONE_ATTRIBUTES))


def copy_metadata(source, clone, saved):
    # COPYFILE_METADATA copies the archived mode, owner, ACLs and extended attributes.
    if LIB.copyfile(os.fsencode(source), os.fsencode(clone), None, 7):
        raise OSError(ctypes.get_errno(), 'copyfile metadata failed', str(source))
    os.utime(clone, ns=(saved.st_atime_ns, saved.st_mtime_ns))
    birth = attributes(source, BIRTH_TIME, 0)
    request = struct.pack('=HHIIIII', 5, 0, BIRTH_TIME, 0, 0, 0, 0)
    if LIB.setattrlist(os.fsencode(clone), request, birth, len(birth), 0):
        raise OSError(ctypes.get_errno(), 'setattrlist creation time failed', str(clone))
    assert attributes(clone, BIRTH_TIME, 0) == birth
    copied = clone.stat()
    for field in ('st_uid','st_gid','st_mode','st_flags','st_mtime_ns','st_size'):
        assert getattr(copied,field) == getattr(saved,field)


def identity(path):
    s = path.lstat()
    assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def backup(source, target, expected, size, stage):
    parent_id = identity(source)
    target_id = identity(target)
    assert parent_id[0] == target_id[0] and parent_id[1] != target_id[1]
    assert parent_id[2] == target_id[2] == size and size > 0
    verified(source, expected)
    private, group, count = clone_attributes(target)
    _, parent_group, _ = clone_attributes(source)
    if group == parent_group and private == 0:
        verified(target, expected)
        return None
    if count != 1 or private != target.stat().st_blocks * 512:
        raise ValueError(f'Unexpected sharing of {target}')
    saved = target.stat()
    assert saved.st_flags == 0 and digest(target) == expected
    # No path in an archived family is changed until a third copy has passed
    # a full hash comparison. Atomic replacement leaves the parent untouched.
    with tempfile.TemporaryDirectory(dir=stage) as temp:
        candidate = Path(temp)/target.name
        clone_file(source, candidate)
        assert digest(candidate) == expected
        copy_metadata(target, candidate, saved)
        assert digest(candidate) == expected and candidate.stat().st_ino not in (parent_id[1], target_id[1])
        assert clone_attributes(candidate)[:2] == (0, parent_group)
        assert identity(target) == target_id and identity(source) == parent_id
        os.replace(candidate, target)
    assert clone_attributes(target)[:2] == (0, parent_group) and digest(target) == expected
    return dict(bytes=size, private_bytes_before=private, private_bytes_after=0, sha256=expected,
                backup_inode_before=target_id[1], backup_inode_after=target.stat().st_ino,
                parent_inode=parent_id[1], clone_group=parent_group)


def run():
    receipt_root = RUNTIME/'receipts'/CAMPAIGN
    archive = RUNTIME/'archive'/CAMPAIGN
    staging = RUNTIME/'qa/snug125/storage'
    staging.mkdir(parents=True, exist_ok=True)
    journal = staging/'verified_motion_backup_clones.json'
    with (staging/'consolidate.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        records = read(journal) if journal.exists() else {}
        for branch in ('bare','stand3_nylon','stand3_aluminium'):
            parent = branch+'_enforced'
            parent_proof = read(ROOT/'validation/motion'/f'{parent}.json')
            parent_receipt = receipt_root/parent
            assert (parent_receipt/'released.txt').is_file()
            parent_ledger = read(parent_receipt/'archived.json')
            assert parent_ledger['case'] == parent_proof['case'] == parent
            assert parent_ledger['campaign'] == parent_proof['campaign'] == CAMPAIGN
            originals = {r['name']:r for r in parent_ledger['files']}
            for axis in 'XYZ':
                case = branch+'_motion_'+axis
                receipt = receipt_root/case
                status = read(receipt/'status.json')
                assert status['phase'] == 'solver_complete' and status['exit'] == 0 and status['parent'] == parent
                assert status['case'] == case and status['motion_kind'] == 'transient' and (receipt/'released.txt').is_file()
                ledger = read(receipt/'archived.json')
                evidence = read(ROOT/'validation/motion'/f'{case}.json')
                assert evidence['case'] == ledger['case'] == case and evidence['campaign'] == ledger['campaign'] == CAMPAIGN
                assert evidence['basis_rst_sha256'] == parent_proof['basis_rst_sha256']
                files = {r['name']:r for r in ledger['files']}
                assert files['file.mcf']['sha256'] == evidence['mcf_sha256']
                for name in ('file.full','file.mode'):
                    assert parent_proof['smp_parent_sha256'][name] == files[name]['sha256'] and originals[name] == files[name]
                    assert shutil.disk_usage(ROOT).free > 400_000_000_000
                    key = case+'/'+name
                    target,source=archive/case/name,archive/parent/name
                    prior=records.get(key)
                    private,group,_=clone_attributes(target)
                    parent_group=clone_attributes(source)[1]
                    if prior is None and group!=parent_group:
                        prior=dict(parent=parent,bytes=files[name]['bytes'],sha256=files[name]['sha256'],
                                   backup_inode_before=target.stat().st_ino,parent_inode=source.stat().st_ino,
                                   private_bytes_before=private)
                        records[key]=prior
                        write_json(journal,records)
                    if prior:
                        assert prior['parent_inode']==source.stat().st_ino and prior['sha256']==files[name]['sha256']
                        if 'backup_inode_after' in prior:
                            assert prior['backup_inode_after']==target.stat().st_ino and (private,group)==(0,parent_group)
                        elif group!=parent_group:
                            assert prior['backup_inode_before']==target.stat().st_ino and prior['private_bytes_before']==private
                    row=backup(source,target,files[name]['sha256'],files[name]['bytes'],staging)
                    if prior and 'backup_inode_after' not in prior:
                        # Also recovers a completed replacement if the process exited before journaling it.
                        assert clone_attributes(target)[:2]==(0,parent_group) and target.stat().st_ino!=prior['backup_inode_before']
                        prior.update(backup_inode_after=target.stat().st_ino,clone_group=parent_group,private_bytes_after=0)
                        write_json(journal,records)
                    if row:
                        print(key,row['private_bytes_before'],flush=True)
    return records


if __name__ == '__main__':
    rows = run()
    print('Recorded duplicate private allocation removed:', sum(row['private_bytes_before'] for row in rows.values()))
