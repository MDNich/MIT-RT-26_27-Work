"""Strict replay of a completed native field archive in Windows CPython; never launches MAPDL."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import time
from zipfile import ZipFile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def distance(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        return max((distance(a[k],b[k]) for k in a),default=0.)
    if isinstance(a,list):
        assert len(a)==len(b)
        return max((distance(i,j) for i,j in zip(a,b)),default=0.)
    return abs(a-b)/max(1.,abs(a),abs(b))


def main(job):
    assert job in ('wall2sa','wall2sc','wall2ba','wall2bc')
    package=ROOT/'configs/native_verification/whole_sector_r2'
    archive=package/'controller.zip'
    manifest=read(package/'manifest.json')
    assert sha256(archive.read_bytes()).hexdigest()==manifest['controller.zip']
    sys.path.insert(0,str(archive))
    from sector_exposure import integrate
    from sector_wall import banded
    from sector_mapdl import parse_field
    assert all(str(archive) in sys.modules[m].__file__ for m in ('sector_exposure','sector_mapdl','sector_wall'))
    run=Path('C:/IrisStudy/runs')/('sector_'+job)
    mirror=ROOT/'ansystmp/runs'/run.name
    cfg=package/(job+'_settings.json')
    assert sha256(cfg.read_bytes()).hexdigest()==manifest[cfg.name]
    settings=read(cfg)
    raw=run/'sector_fields.zip'
    before=0.
    def guard():
        nonlocal before
        if time.monotonic()-before < 2.:
            return
        s=read(ROOT/'ansystmp/host_storage_status.json')
        if ((ROOT/'ansystmp/STOP_WORK.json').exists() or not s['allowed'] or time.time()-s['checked_epoch']>45
            or s['mac_free_bytes']<400_000_000_000 or shutil.disk_usage(run).free<10_000_000_000):
            raise RuntimeError('Storage guard')
        before=time.monotonic()
    guard()
    count=0
    worst=0.
    with ZipFile(raw) as fields:
        def step(block):
            nonlocal count,worst
            count+=1
            value=parse_field(fields.read(f'{count:06d}.txt'), block, settings['configuration']['geometry'],count)
            error=float(max(abs(value-banded(block))))
            if error>2e-6:
                raise ValueError(f'Field {count} exceeds the nodal temperature tolerance')
            worst=max(worst,error)
            return value
        record=integrate(settings,step,guard)
        assert count==len(fields.namelist())
    terminal=run/'sector_terminal.json'
    differences=[distance(read(p)['record'],record) for p in (terminal,mirror/'sector_checkpoint.json')]
    assert max(differences)<1e-7
    print(json.dumps(dict(job=job,native_blocks=count,field_sha256=sha256(raw.read_bytes()).hexdigest(),
        terminal_sha256=sha256(terminal.read_bytes()).hexdigest(),settings_sha256=manifest[cfg.name],
        source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),controller_sha256=manifest['controller.zip'],
        replay_difference=max(differences),max_field_error_K=worst,record=record)))


if __name__=='__main__':
    main(sys.argv[1])
