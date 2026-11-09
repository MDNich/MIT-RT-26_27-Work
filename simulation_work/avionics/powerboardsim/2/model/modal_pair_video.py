"""Render the four mounting variants at the original film's rank and show shape correspondence."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pyvista as pv
from PIL import Image
from native_rst import read_rst
from modal_correspondence import checksum,compare
from modal_video import render as render_bare
from rms_video import ROOT,VARIANTS,LABELS
from film_identity import verified,already_rendered

SUBJECTS = {'modal_fig01_default_mode01':('refined',1), 'modal_fig02_default_mode20':('refined',20),
            'modal_fig03_bolted_mode20':('modal20',20)}


def surfaces(rst,rank):
    r=read_rst(str(rst)); g=r.grid
    numbers,disp=r.nodal_displacement(rank-1)
    order=np.argsort(numbers)
    solid=np.isin(g.cell_data['ansys_elem_type_num'],[185,186,187,188])
    case=g.cell_data['ansys_material_type']==850
    groups=[]
    for flag,mask in ((False,solid&~case),(True,solid&case)):
        if not mask.any():continue
        mesh=g.extract_cells(mask).extract_surface(algorithm='dataset_surface',nonlinear_subdivision=0).triangulate()
        ids=mesh.point_data['ansys_node_num'];p=np.searchsorted(numbers[order],ids)
        if max(p)>=len(numbers) or not np.array_equal(numbers[order[p]],ids):raise ValueError('Missing native displacement')
        v=disp[order[p],:3].astype(float)
        if not np.isfinite(v).all():raise ValueError('Invalid surface displacement')
        mesh.clear_data();groups.append((mesh,mesh.points.copy(),v,flag))
    peak=max(np.max(np.linalg.norm(v,axis=1)) for _,_,v,_ in groups)
    if peak<=0:raise ValueError('Missing physical motion')
    return [(m,orig,v/peak,flag) for m,orig,v,flag in groups],float(r.time_values[rank-1])


def draw(panels,rank,target,preview=False):
    if len(panels)!=4:raise ValueError('Four panels required')
    p=pv.Plotter(shape=(2,2),window_size=(1440,810) if preview else (3840,2160),off_screen=True,border=False)
    colors='Relative amplitude'
    transforms=[]
    for i,(name,parts,Hz,mac,sign) in enumerate(panels):
        p.subplot(i//2,i%2);p.set_background('#f8f9fc')
        for j,(mesh,orig,v,case) in enumerate(parts):
            norms=np.linalg.norm(v,axis=1)
            mesh.point_data[colors]=norms.copy()
            transforms.append((mesh,orig,v*sign,norms))
            p.add_mesh(mesh,scalars=colors,cmap='viridis',clim=(0,1),opacity=.42 if case else 1,
                       show_scalar_bar=(i==0 and j==0),scalar_bar_args=dict(title='Relative amplitude',vertical=True,
                       position_x=.10,position_y=.18,width=.043,height=.42,n_labels=3,fmt='%.1f',
                       title_font_size=14,label_font_size=13,color='#25334a'))
        p.add_text(f'{name}   |   mode {rank}: {Hz:.2f} Hz',position='upper_left',
                   font='arial',font_size=11 if preview else 21,color='#08357e')
        p.add_text(f'Same-rank shape correlation (MAC) {mac:.2f}   |   6 mm display amplitude',
                   position='lower_left',font='arial',font_size=8 if preview else 13,color='#183046')
        center=np.array([.0346,.0604,-.004])
        p.camera_position=[center+np.array([.140,.065,-.223]),center,(0,1,0)]
        p.enable_parallel_projection();p.camera.parallel_scale=.083
    p.show(auto_close=False,interactive=False)
    def frame(a):
        for mesh,orig,v,norm in transforms:
            mesh.points=orig+.006*a*v
            mesh.point_data[colors]=abs(a)*norm
        p.render()
        return p.screenshot(return_img=True)[:,:,:3]
    if preview:
        Image.fromarray(frame(1.)).save(target);p.close();return
    if target.exists():raise FileExistsError(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix('.part.mp4')
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime') as cache:
        paths=[]
        for k in range(-45,46):
            path=Path(cache)/f'{k+45:02d}.png'
            Image.fromarray(frame(np.sin(k*np.pi/90))).save(path,compress_level=1)
            paths.append(path)
        p.close()
        exe=imageio_ffmpeg.get_ffmpeg_exe()
        cmd=[exe,'-v','error','-y','-f','image2pipe','-framerate','60','-vcodec','png','-i','pipe:0','-frames:v','540','-c:v','h264_videotoolbox','-b:v','15M','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)]
        with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
            for i in range(540):
                phase=i%180
                k=phase if phase<=45 else 90-phase if phase<=135 else phase-180
                proc.stdin.write(paths[k+45].read_bytes())
            proc.stdin.close()
            if proc.wait():raise RuntimeError('Encoding failed')
    total,duration=imageio_ffmpeg.count_frames_and_secs(str(tmp))
    meta_iter=imageio_ffmpeg.read_frames(str(tmp));meta=next(meta_iter);meta_iter.close()
    assert (total,meta['fps'],tuple(meta['size']))==(540,60,(3840,2160)) and abs(duration-9)<.03
    tmp.replace(target)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('subject',choices=SUBJECTS);p.add_argument('--campaign',default='nov08_01')
    p.add_argument('--preview',action='store_true',help='Historical repeat rendered in all four panels to check layout only')
    args=p.parse_args();kind,rank=SUBJECTS[args.subject]
    base=ROOT/f'.runtime/archive/{args.campaign}'
    bare=base/('bare_'+kind)/'file.rst'
    if args.preview:
        panels=[]
        for i in range(4):
            parts,f=surfaces(bare,rank)
            panels.append((f'Bare reference layout check {i+1}',parts,f,1.,1))
        draw(panels,rank,ROOT/'.runtime/qa/modal-panels.png',True);return
    refs={}
    for v in VARIANTS:
        key=f'{v}_{kind}';audit=json.loads((ROOT/f'validation/global/{key}.json').read_text())
        f=base/key/'file.rst';assert audit['campaign']==args.campaign and audit['case']==key and verified(f,audit['rst_sha256'])==audit['rst_sha256']
        refs[v]=(f,audit['rst_sha256'])
    bare_out=ROOT/f'output/videos/without_case/power_board_4k60/{args.subject}.mp4'
    if not bare_out.is_file():
        render_bare(bare,rank,'Bare board / '+('refined default contacts' if kind=='refined' else 'six locked bolts'),bare_out)
    film=json.loads(bare_out.with_suffix('.json').read_text())
    assert film['rank']==rank and film['video_sha256']==checksum(bare_out)
    baseline_sign=1
    if film['source_rst_sha256']!=refs['bare'][1]:
        repeat=json.loads((ROOT/'validation/modal_shape_repeat.json').read_text())
        assert repeat['reference_rst_sha256']==film['source_rst_sha256'] and repeat['candidate_rst_sha256']==refs['bare'][1]
        baseline_sign=repeat['modes'][rank-1]['equal_rank_sign']
    panels=[];evidence=[]
    for v,label in zip(VARIANTS[1:],LABELS[1:]):
        f,sha=refs[v];path=ROOT/f'validation/modal_matches/{v}_{kind}.json';path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_text(json.dumps(compare(bare,f),indent=2)+'\n')
        data=json.loads(path.read_text());assert data['reference_rst_sha256']==refs['bare'][1] and data['candidate_rst_sha256']==sha
        row=data['modes'][rank-1];parts,Hz=surfaces(f,rank)
        sign=row['equal_rank_sign']*baseline_sign or 1
        panels.append((label,parts,Hz,row['equal_rank_MAC'],sign))
        evidence.append(dict(variant=v,rst_sha256=sha,rank=rank,Hz=Hz,same_rank_MAC=row['equal_rank_MAC'],phase_sign=sign,closest_shape_rank=row['best_rank']))
    target=ROOT/f'output/videos/with_case/power_board_4k60/{args.subject}.mp4'
    if already_rendered(target,dict(subject=args.subject,panels=evidence,baseline_film_sha256=film['video_sha256'],peak_display_displacement_mm=6)):return
    draw(panels,rank,target)
    target.with_suffix('.json').write_text(json.dumps(dict(subject=args.subject,panels=evidence,baseline_film_sha256=film['video_sha256'],
            sha256=checksum(target),frames=540,duration_s=9,fps=60,resolution=[3840,2160],peak_display_displacement_mm=6,
            interpretation='Same frequency rank on each model. MAC compares original-solid translations. Eigenvector signs face the bare reference; amplitudes are arbitrary.'),indent=2)+'\n')

if __name__=='__main__':main()
