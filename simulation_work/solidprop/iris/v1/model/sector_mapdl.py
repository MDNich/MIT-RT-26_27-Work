"""In-process MAPDL thermal backend. Importing this module cannot start a solver."""
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import traceback
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from sector_exposure import balances, integrate, write_json
from sector_wall import banded, dual, volume


def topology(block, geometry):
    nt, ny = geometry['angular_divisions'], geometry['axial_divisions']
    theta = math.radians(geometry['angle_deg'])/nt
    dy = geometry['length_m']/ny
    # Shape-function weights around one ring. End nodes belong to half as many bricks.
    wtheta = np.ones(nt+1)
    waxial = np.ones(ny+1)
    wtheta[[0,-1]] = waxial[[0,-1]] = .5
    weights = np.outer(wtheta,waxial).ravel()/(nt*ny)
    scale = nt*math.sin(theta)*geometry['length_m']
    if not math.isclose(block.facet, math.cos(theta/2), abs_tol=1e-14):
        raise ValueError('Inconsistent facet geometry')
    return nt, ny, theta, dy, weights, scale


def commands(block, geometry, sequence):
    nt, ny, theta, dy, weights, scale = topology(block, geometry)
    width = len(weights)
    r = block.radii
    nr = len(r)-1
    count = nr*nt*ny
    extra = block.capacity-volume(dual(r))
    if np.min(extra)<=0:
        raise ValueError('Specified thermal mass is below preliminary unit volumetric capacity')
    lines = ['/NOPR','/PREP7']
    if sequence>1:
        lines += ['ALLSEL,ALL','FDELE,ALL,ALL','EDELE,ALL','NDELE,ALL']
    else:
        lines += ['ET,1,SOLID278','KEYOPT,1,13,1','KEYOPT,1,15,1','ET,2,MASS71','KEYOPT,2,3,1']
    def nid(i,j,k):
        return 1+i*width+j*(ny+1)+k
    for i, radius in enumerate(r):
        for j in range(nt+1):
            angle=(j-.5*nt)*theta
            for k in range(ny+1):
                node=nid(i,j,k)
                lines.append(f'N,{node},{radius*math.sin(angle):.16g},{k*dy:.16g},{radius*math.cos(angle):.16g}')
    lines += ['TYPE,1','REAL,1']
    for i, conductivity in enumerate(block.k):
        mat = i+1
        lines += [f'MP,KXX,{mat},{conductivity:.16g}',f'MP,DENS,{mat},1',f'MP,C,{mat},1',f'MAT,{mat}']
        for j in range(nt):
            for k in range(ny):
                corners = [nid(i,j,k),nid(i+1,j,k),nid(i+1,j+1,k),nid(i,j+1,k)]
                points = corners+[a+1 for a in corners]
                lines.append('EN,'+','.join(map(str,[1+(i*nt+j)*ny+k,*points])))
    lines += ['TYPE,2','MAT,1']
    for i, cap in enumerate(extra):
        for ring_id, weight in enumerate(weights):
            node=1+i*width+ring_id
            lines += [f'R,{node},{cap*scale*weight:.16g}',f'REAL,{node}',f'EN,{count+node},{node}']
    lines += ['FINISH','/SOLU','ANTYPE,TRANS,NEW','TRNOPT,FULL','TINTP,,,,1','KBC,1','AUTOTS,OFF',
              'NSUBST,1,1,1',f'TIME,{block.dt:.16g}']
    for i, initial in enumerate(block.initial):
        for ring_id, weight in enumerate(weights):
            node=1+i*width+ring_id
            lines.append(f'IC,{node},TEMP,{initial:.16g}')
            if block.load[i]:
                lines.append(f'F,{node},HEAT,{block.load[i]*scale*weight:.16g}')
    for i, face, conv, radius in [(0,5,block.hot_h,r[0]),(nr-1,3,block.outer_h,r[-1])]:
        # Bulk-temperature terms are already in nodal load. This adds the
        # matching film matrix once, against a zero-Celsius reference.
        for e in range(1+i*nt*ny,1+(i+1)*nt*ny):
            lines += [f'SFE,{e},{face},CONV,0,{conv*block.facet/radius:.16g}',f'SFE,{e},{face},CONV,2,0']
    lines += ['OUTRES,ALL,LAST','SOLVE','FINISH','/POST1','SET,LAST','*GET,IRST,ACTIVE,0,SET,TIME',
              '*CFOPEN,sector_field,txt',f'IRSEQ={sequence}','*VWRITE,IRSEQ,IRST','(F12.0,1X,E25.16)',
              f'*DO,IRNODE,1,{width*len(r)}','*GET,IRTEMP,NODE,IRNODE,TEMP','*VWRITE,IRNODE,IRTEMP',
              '(F12.0,1X,E25.16)','*ENDDO','*CFCLOSE','FINISH','/GOPR']
    return '\n'.join(lines)+'\n'


def parse_field(raw, block, geometry, seq):
    data=np.loadtxt(BytesIO(raw))
    _,_,_,_,weights,_=topology(block,geometry)
    if data.shape!=(1+len(block.radii)*len(weights),2) or not np.isfinite(data).all():
        raise ValueError('Incomplete native field')
    if data[0,0]!=seq or not math.isclose(data[0,1],block.dt,rel_tol=2e-12,abs_tol=1e-13):
        raise ValueError('Wrong native field index or SET time')
    if not np.array_equal(data[1:,0], np.arange(1,len(data))):
        raise ValueError('Wrong native node ordering')
    field=data[1:,1].reshape(len(block.radii),len(weights))
    if np.max(np.ptp(field,axis=1))>1e-3:
        raise ValueError('Angular/axial variation exceeds the radial transfer tolerance')
    return field@weights


class MapdlBackend:
    def __init__(self, mapdl, geom, output):
        self.mapdl=mapdl
        self.geom=geom
        self.archive=output
        self.seq=0

    def __call__(self,block):
        self.seq+=1
        macro=Path('sector_step.inp')
        macro.write_text(commands(block,self.geom,self.seq),encoding='ascii')
        field=Path('sector_field.txt')
        field.unlink(missing_ok=True)
        # The initialized mapdl object is supplied by *PYTHON in this running
        # process. Do not instantiate PyMAPDL, spawn a service or create a solver.
        self.mapdl.input('sector_step','inp')
        raw=field.read_bytes()
        temp=parse_field(raw,block,self.geom,self.seq)
        if max(abs(temp-banded(block)))>2e-6:
            raise ValueError('Native free field differs from the reference linear system')
        self.archive.writestr(f'{self.seq:06d}.txt',raw)
        return temp


def execute(mapdl, settings, package_sha, share):
    run = Path.cwd()
    job = settings['job']
    if run.name!='sector_'+job or run.parent!=Path('C:/IrisStudy/runs'):
        raise RuntimeError('Wrong native working directory')
    mac = Path(share)/'ansystmp'
    mirror = mac/'runs'/run.name
    intent=json.loads((mirror/'intent.json').read_text())
    if intent['case']!=job or hashlib.sha256(Path(job+'.inp').read_bytes()).hexdigest()!=intent['deck_sha256']:
        raise RuntimeError('Local deck differs from host intent')
    def guard():
        guard_state=json.loads((mac/'host_storage_status.json').read_text())
        if ((mac/'STOP_WORK.json').exists() or (mirror/'PAUSE_REQUESTED').exists()
            or not guard_state['allowed'] or time.time()-guard_state['checked_epoch']>45
            or guard_state['mac_free_bytes']<400_000_000_000 or shutil.disk_usage(run).free<10_000_000_000):
            raise RuntimeError('Storage or operator stop')
    def snapshot(record):
        cp=dict(job=job,controller_sha256=package_sha,nonce=intent['nonce'],native_blocks=backend.seq,record=record)
        write_json(mirror/'sector_checkpoint.json',cp)
    try:
        guard()
        with ZipFile('sector_fields.zip','x',compression=ZIP_DEFLATED,compresslevel=1) as archive:
            backend=MapdlBackend(mapdl,settings['configuration']['geometry'],archive)
            record=integrate(settings,backend,guard,snapshot)
        write_json('sector_terminal.json',dict(job=job,nonce=intent['nonce'],settings=settings,
                   controller_sha256=package_sha,record=record,native_blocks=backend.seq,
                   balances=balances(settings,record)))
    except Exception:
        write_json(mirror/'sector_failure.json',dict(job=job,nonce=intent['nonce'],error=traceback.format_exc()))
        raise
