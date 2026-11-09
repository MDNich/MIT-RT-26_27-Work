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


def publish_baseline(source,destination,identity):
    """Install the verified baseline generation. A later common colour scale may replace the standalone scale."""
    import shutil
    info=json.loads(source.with_suffix('.json').read_text())
    verified(source,info['sha256'])
    sidecar=destination.with_suffix('.json')
    if sidecar.exists():
        previous=json.loads(sidecar.read_text())
        if any(previous.get(k)!=info.get(k) for k in identity):
            raise ValueError(f'Existing baseline has different physical inputs: {destination}')
        if previous['sha256']!=info['sha256'] and destination.is_file() and digest(destination)==previous['sha256']:
            stored=ROOT/'.runtime/films/baseline_history'/previous['sha256']
            stored.mkdir(parents=True,exist_ok=True)
            backup=stored/destination.name
            if not backup.exists():shutil.copy2(destination,backup)
            verified(backup,previous['sha256']);write_json(stored/'metadata.json',previous)
        elif destination.is_file() and digest(destination)!=info['sha256']:
            raise ValueError(f'Baseline content disagrees with both generation records: {destination}')
    elif destination.exists():
        verified(destination,info['sha256'])
    destination.parent.mkdir(parents=True,exist_ok=True)
    if not destination.exists() or digest(destination)!=info['sha256']:
        temp=destination.with_suffix('.new.mp4')
        shutil.copy2(source,temp);verified(temp,info['sha256']);temp.replace(destination)
    write_json(sidecar,info)

def already_rendered(dest,fields):
    meta=dest.with_suffix('.json')
    if not dest.exists() and not meta.exists():return False
    if not (dest.is_file() and meta.is_file()):raise RuntimeError(f'Incomplete output; inspect before any overwrite: {dest}')
    info=json.loads(meta.read_text())
    if any(info.get(key)!=value for key,value in fields.items()):raise ValueError(f'Film metadata no longer matches its inputs: {dest}')
    verified(dest,info.get('sha256') or info['video_sha256'])
    return True
