"""Render the 22 paired subjects as accepted native inputs arrive. One independent host worker; no solver dispatch."""
import argparse
import csv
import datetime as dt
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image,ImageDraw
from film_identity import ROOT,verified,write_json,digest
from rms_video import VARIANTS,LABELS
from study_cases import native_case

CAMP='nov08_01'
RT=ROOT/'.runtime/films'
VIDEO=ROOT/'output/videos'
KINDS=('normalized modal motion','camera motion over fixed RMS','seeded random motion')
SLOTS=('without_case','with_case')
def read(path):return json.loads(path.read_text())
def now():return dt.datetime.now(dt.timezone.utc).isoformat()


def catalog():
    with (ROOT/'validation/video_pairs.csv').open() as f:rows=list(csv.DictReader(f))
    from seeded_video import SUBJECTS as seeded
    from modal_pair_video import SUBJECTS as modal
    assert [sum(r['kind']==k for r in rows) for k in KINDS]==[3,12,7]
    for r in rows:
        p=Path(r['file']);name=p.stem;kind=r['kind']
        assert all(Path(r[s])==Path('output/videos')/s/p for s in SLOTS)
        if kind==KINDS[0]:
            key,rank=modal[name];r.update(suffix=key,rank=rank,category='global',script='modal_pair_video.py')
        elif kind==KINDS[1]:
            ax,resp,view=(s.strip() for s in r['october_title'].split('|'))
            r.update(suffix='psd_'+ax[-1],axis=ax[-1],response=resp[-1],view=view,category='global',script='rms_video.py')
        else:
            ax,scope,comp=seeded[name]
            r.update(suffix='motion_'+ax,axis=ax,scope=scope,component=comp,category='motion',script='seeded_video.py')
    assert len({r[s] for s in SLOTS for r in rows})==44
    return rows


def proof_path(r,v):return ROOT/'validation'/r['category']/(native_case(v,r['suffix'])+'.json')


def identity(r,side,meta):
    kind=r['kind'];variants=VARIANTS[:1] if side==SLOTS[0] else VARIANTS[1:]
    if side=='with_case' and len(meta['panels'])==2:
        variants=VARIANTS[3:]
    if kind==KINDS[0] and meta.get('modal_source')=='wide native basis':
        assert side=='with_case' and r['suffix']=='modal20' and variants==VARIANTS[3:]
        sources=read(ROOT/'validation/bolted_mode_film.json')
        assert sources['campaign']==CAMP
        proofs=[read(ROOT/'validation/global'/(v+'_basis.json')) for v in variants]
        assert [p['rst_sha256'] for p in proofs]==[sources['cases'][v]['rst_sha256'] for v in variants]
    elif kind==KINDS[1] and meta.get('field_method')=='independent':
        assert side=='with_case' and variants==VARIANTS[3:]
        proofs=[read(ROOT/'validation/rms_film_fields'/(native_case(v,r['suffix'])+'.json')) for v in variants]
    elif kind==KINDS[2] and meta['coordinate_method']=='independent':
        proofs=[read(ROOT/'validation/independent_motion'/(native_case(v,r['suffix'])+'.json')) for v in variants]
        assert all(p['coordinate_method']=='independent' and p['Newmark_relative_L2']<1e-9 for p in proofs)
    else:
        proofs=[read(proof_path(r,v)) for v in variants]
    source_key='basis' if meta.get('modal_source')=='wide native basis' else r['suffix']
    assert all(t['campaign']==CAMP and t['case']==native_case(v,source_key) for v,t in zip(variants,proofs,strict=True))
    if kind==KINDS[0] and side==SLOTS[0]:
        assert meta['rank']==r['rank']
        if meta['source_rst_sha256']!=proofs[0]['rst_sha256']:
            repeat=read(ROOT/'validation/modal_shape_repeat.json')
            assert r['suffix']=='refined' and repeat['reference_rst_sha256']==meta['source_rst_sha256']
            assert repeat['candidate_rst_sha256']==proofs[0]['rst_sha256'] and repeat['modes'][r['rank']-1]['equal_rank_MAC']>.999999
    elif kind==KINDS[0]:
        assert meta['peak_display_displacement_mm']==6 and len(meta['panels'])==len(variants)
        for p,v,proof in zip(meta['panels'],variants,proofs,strict=True):
            assert p['variant']==v and p['rst_sha256']==proof['rst_sha256'] and p['rank']==r['rank']
    elif kind==KINDS[1]:
        assert (meta['base'],meta['response'],meta['view'])==(r['axis'],r['response'],r['view'])
        expected=[dict(variant=v,rst_sha256=t['rst_sha256']) for v,t in zip(variants,proofs,strict=True)]
        if meta.get('field_method')=='independent':
            for src,proof in zip(expected,proofs,strict=True):
                assert proof['axis']==r['axis'] and proof['method']=='Independent PSD integration'
                src['surface_field_sha256']=proof['surface_field_sha256']
        assert meta['sources']==expected
        assert [p['label'] for p in meta['panels']]==[LABELS[VARIANTS.index(v)] for v in variants]
    else:
        from seeded_motion import FRAMES,FS
        assert meta['base']==r['axis'] and meta['scope']==r['scope'] and meta['physical_interval_s']==(FRAMES[[0,-1]]/FS).tolist()
        assert meta['response']==('Dynamic von Mises [MPa]' if r['component']=='stress' else 'Signed U'+r['component']+' [mm]')
        assert meta['display_displacement_multiplier']==50 and meta['coordinate_method'] in ('independent','native')
        for p,v,t in zip(meta['panels'],variants,proofs,strict=True):
            assert p['name']==LABELS[VARIANTS.index(v)] and p['coordinates_sha256']==t['clip_sha256'] and p['rst_sha256']==t['basis_rst_sha256']


def decode(r,side,refresh=False):
    movie=ROOT/r[side];meta=read(movie.with_suffix('.json'));identity(r,side,meta)
    sha=verified(movie,meta.get('sha256') or meta['video_sha256'])
    stem=RT/'audit'/side/Path(r['file']).with_suffix('')
    receipt=stem.with_suffix('.json');sheet=stem.with_suffix('.jpg')
    if not refresh and receipt.is_file() and sheet.is_file():
        proof=read(receipt)
        if proof['sha256']==sha and proof['sidecar_sha256']==digest(movie.with_suffix('.json')) and proof['sheet_sha256']==digest(sheet):return proof
    frames,secs=imageio_ffmpeg.count_frames_and_secs(str(movie))
    it=imageio_ffmpeg.read_frames(str(movie));fmt=next(it);it.close()
    assert frames==int(r['frames'])==meta['frames'] and abs(secs-float(r['duration_s']))<.04
    assert (fmt['fps'],tuple(fmt['size']))==(60,(3840,2160)) and fmt['codec'].startswith('h264')
    assert 0<movie.stat().st_size<100000000
    samples=[0,45,125] if r['kind']==KINDS[0] else [0,118,359]
    vf='select='+('+'.join(f'eq(n\\,{i})' for i in samples))+',scale=768:432'
    f=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(movie),'-an','-vf',vf,'-fps_mode','passthrough',
                        '-frames:v','3','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,check=True)
    ims=np.frombuffer(f.stdout,np.uint8).reshape(3,432,768,3)
    # Compare interior pixels, excluding time labels, captions and legends.
    panels=len(meta['panels']) if side=='with_case' else 1
    rows,cols={1:(1,1),2:(1,2),4:(2,2)}[panels]
    contrast=[]
    for i in range(rows):
        for j in range(cols):
            a=ims[:,int((i+.18)*432/rows):int((i+.80)*432/rows),int((j+.23)*768/cols):int((j+.85)*768/cols)].astype(float)
            delta=float(np.abs(a[1:]-a[0]).mean())
            if delta<.10:raise ValueError(f'No visible field or geometry change in {movie.name} panel {i},{j}: {delta}')
            contrast.append(delta)
    sheet.parent.mkdir(parents=True,exist_ok=True);page=Image.new('RGB',(768,3*(432+24)),'white');draw=ImageDraw.Draw(page)
    for j,num in enumerate(samples):
        draw.text((10,j*456+4),f'{side} / {r["file"]} / frame {num}',fill='#08357e');page.paste(Image.fromarray(ims[j]),(0,j*456+24))
    page.save(sheet,quality=90)
    proof=dict(sha256=sha,sidecar_sha256=digest(movie.with_suffix('.json')),sheet_sha256=digest(sheet),frames=frames,
               fps=fmt['fps'],width=3840,height=2160,duration_s=secs,bytes=movie.stat().st_size,check_frames=samples,
               panel_average_pixel_changes=contrast,reference_sha256=r['sha256'],comparison_panels=panels,coordinate_method=meta.get('coordinate_method'),field_method=meta.get('field_method'))
    write_json(receipt,proof);return proof


def pair_check(r):
    a,b=[read((ROOT/r[g]).with_suffix('.json')) for g in SLOTS]
    if r['kind']==KINDS[0]:assert b['baseline_film_sha256']==a['video_sha256']
    else:
        fld='range_mm' if r['kind']==KINDS[1] else 'scale'
        assert a[fld]==b[fld] and np.ptp(a[fld])>0
        if r['kind']==KINDS[2]:assert a['coordinate_method']==b['coordinate_method']
    assert (a.get('sha256') or a['video_sha256'])!=b['sha256']


def command(args,lease):
    # The renderer inherits this lease so it still excludes another worker if its supervisor exits.
    p=subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,pass_fds=(lease.fileno(),))
    if p.returncode:raise RuntimeError(p.stdout[-3000:])


def seeded_command(row,bare,cased):
    sidecar=lambda p:read(p.with_suffix('.json')) if p.is_file() else {}
    a,b=sidecar(bare),sidecar(cased)
    raised=[VARIANTS[0],*VARIANTS[3:]]
    for variants,method in [(VARIANTS,'native'),(raised,'native'),(raised,'independent')]:
        if method=='independent' and a.get('coordinate_method')=='native':continue
        parent='motion' if method=='native' else 'independent_motion'
        if not all((ROOT/'validation'/parent/(native_case(v,row['suffix'])+'.json')).is_file() for v in variants):
            continue
        if len(b.get('panels',[]))==len(variants)-1 and b.get('coordinate_method')==method and a.get('coordinate_method')==method and a['scale']==b['scale']:
            return None
        return (['--raised-only'] if len(variants)==3 else [])+['--coordinates',method]
    if not a and proof_path(row,'bare').is_file():return ['--bare-only']
    return None


def raised_rms_method(row):
    raised=[VARIANTS[0],*VARIANTS[3:]]
    if all(proof_path(row,v).is_file() for v in raised):
        return 'native'
    if not proof_path(row,'bare').is_file():
        return None
    axes=ROOT/'validation/rms_film_checks'
    controls=[native_case('bare','psd_'+a) for a in 'XYZ']+[native_case(v,'psd_X') for v in VARIANTS[3:]]
    if all((axes/(k+'.json')).is_file() for k in controls) and all(
            (ROOT/'validation/rms_film_fields'/(native_case(v,row['suffix'])+'.json')).is_file() for v in VARIANTS[3:]):
        return 'independent'
    return None


def cycle(render,refresh,lease):
    result=[];issues=[];models=ROOT/'model'
    for r in catalog():
        s=Path(r['file']).stem;issue=RT/'issues'/Path(r['file']).with_suffix('.json')
        try:
            if render and not issue.exists():
                if shutil.disk_usage(ROOT).free<425000000000:raise RuntimeError('Host reserve for production film fields reached')
                bare=ROOT/r['without_case']
                if r['kind']==KINDS[0] and not bare.exists() and proof_path(r,'bare').is_file():
                    assert not bare.with_suffix('.json').exists()
                    p=read(proof_path(r,'bare'));key=p['case'];path=ROOT/'.runtime/archive'/CAMP/key/'file.rst'
                    verified(path,p['rst_sha256'])
                    command([models/'modal_video.py',path,r['rank'],'Bare board / '+('refined default contacts' if r['suffix']=='refined' else 'six locked bolts'),bare],lease)
                if r['kind']==KINDS[1] and not bare.exists() and proof_path(r,'bare').is_file():
                    command([models/r['script'],s,'--campaign',CAMP,'--bare-only'],lease)
                cased=ROOT/r['with_case']
                complete_sources=all(proof_path(r,v).is_file() for v in VARIANTS)
                displayed=read(cased.with_suffix('.json')) if cased.is_file() else {}
                existing_panels=len(displayed.get('panels',[]))
                if r['kind']==KINDS[1] and displayed:
                    old_range=read(bare.with_suffix('.json'))['range_mm']
                    if displayed.get('layout_revision')!=2 or displayed['range_mm']!=old_range:
                        existing_panels=0
                if r['kind']==KINDS[2]:
                    options=seeded_command(r,bare,cased)
                    if options is not None:command([models/r['script'],s,'--campaign',CAMP,*options],lease)
                elif complete_sources and existing_panels<4:
                    command([models/r['script'],s,'--campaign',CAMP],lease)
                elif r['kind']==KINDS[0] and existing_panels<4:
                    native_raised=all(proof_path(r,v).is_file() for v in [VARIANTS[0],*VARIANTS[3:]])
                    if native_raised and (not existing_panels or displayed.get('modal_source')=='wide native basis'):
                        command([models/r['script'],s,'--campaign',CAMP,'--raised-only'],lease)
                    elif not existing_panels and r['suffix']=='modal20' and (ROOT/'validation/bolted_mode_film.json').is_file():
                        command([models/r['script'],s,'--campaign',CAMP,'--raised-basis'],lease)
                elif r['kind']==KINDS[1] and existing_panels<4:
                    method=raised_rms_method(r)
                    if method and (not existing_panels or displayed.get('field_method','native')!=method):
                        flags=['--raised-only']
                        if method=='independent':flags.append('--independent-raised')
                        command([models/r['script'],s,'--campaign',CAMP,*flags],lease)
            for g in SLOTS:
                movie=ROOT/r[g]
                if movie.is_file():
                    proof=decode(r,g,refresh)
                    result.append(dict(file=r[g],kind=r['kind'],**proof))
                elif movie.with_suffix('.json').exists():raise ValueError('Orphaned film sidecar')
            if all((ROOT/r[g]).is_file() for g in SLOTS):pair_check(r)
            if issue.exists():issues.append(r['file'])
        except Exception as exc:
            write_json(issue,dict(time=now(),subject=r['file'],error=str(exc),type=type(exc).__name__))
            issues.append(r['file'])
    provisional=sum(p.get('comparison_panels')==2 for p in result)
    report=dict(total_requested=44,decoded=len(result),raised_comparisons=provisional,
                paired_and_encoded=len(result)==44 and not issues and not provisional and not any('independent' in (p.get('coordinate_method'),p.get('field_method')) for p in result),issues=issues,films=result)
    write_json(RT/'coverage.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--watch',action='store_true');p.add_argument('--render',action='store_true')
    p.add_argument('--refresh',action='store_true');a=p.parse_args()
    RT.mkdir(parents=True,exist_ok=True);lease=(RT/'worker.lock').open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    source=Path(__file__).resolve()
    generation=digest(source)
    write_json(RT/'worker.json',dict(pid=os.getpid(),started=now(),render=a.render,watch=a.watch,source_sha256=generation))
    while True:
        data=cycle(a.render,a.refresh,lease)
        if not a.watch or data['paired_and_encoded']:break
        time.sleep(60)
        if digest(source)!=generation:
            os.execv(sys.executable,[sys.executable,'-u',str(source),*sys.argv[1:]])
    print(data['decoded'],'of 44 decoded;',len(data['issues']),'issues')

if __name__=='__main__':main()
