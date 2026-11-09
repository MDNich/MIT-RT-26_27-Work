"""Verify film sources against their native receipts; reuse a hash only for the same unchanged archive file."""
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def verified(path,expected):
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise ValueError('Invalid source hash')
    stat=path.stat()
    key=[str(path.resolve()),stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]
    token=hashlib.sha256(str(path.resolve()).encode()).hexdigest()
    memo=ROOT/'.runtime/film_hashes'/(token+'.json')
    if memo.exists() and json.loads(memo.read_text())=={'key':key,'sha256':expected}:return expected
    actual=digest(path)
    if actual!=expected:raise ValueError(f'Archive hash mismatch: {path.name}')
    end=path.stat()
    if (stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)!=(end.st_size,end.st_mtime_ns,end.st_ctime_ns):raise ValueError('Input changed during hash')
    write_json(memo,dict(key=key,sha256=actual))
    return actual


def already_rendered(dest,fields):
    meta=dest.with_suffix('.json')
    if not dest.exists() and not meta.exists():return False
    if not (dest.is_file() and meta.is_file()):raise RuntimeError(f'Incomplete output; inspect before any overwrite: {dest}')
    info=json.loads(meta.read_text())
    if any(info.get(key)!=value for key,value in fields.items()):raise ValueError(f'Film metadata no longer matches its inputs: {dest}')
    verified(dest,info.get('sha256') or info['video_sha256'])
    return True
