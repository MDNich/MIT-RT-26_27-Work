"""Render a repeatable native MAPDL mode shape at 3840x2160, 60 Hz, three slowed cycles."""
import argparse, hashlib, json, math, subprocess
from pathlib import Path
import imageio_ffmpeg, numpy as np, pyvista as pv
from native_rst import read_rst
ROOT=Path(__file__).resolve().parents[1]

def skin(rst,rank):
    r=read_rst(str(rst))
    freq=float(r.time_values[rank-1])
    solid=r.grid.extract_cells(np.isin(r.grid.cell_data['ansys_elem_type_num'],[185,186,187,188]))
    mesh=solid.extract_surface(algorithm='dataset_surface',nonlinear_subdivision=0).triangulate()
    ids=mesh.point_data['ansys_node_num'].copy()
    n,v=r.nodal_displacement(rank-1);order=np.argsort(n);indices=np.searchsorted(n[order],ids)
    if np.any(n[order][indices]!=ids):raise ValueError('Missing native mode nodes')
    vector=v[order[indices],:3].astype(float)
    if not np.all(np.isfinite(vector)):raise ValueError('Nonfinite mode shape')
    maximum=np.linalg.norm(vector,axis=1).max()
    if maximum<=0:raise ValueError('Empty mode shape')
    mesh.clear_data();mesh.point_data['Mode magnitude']=np.linalg.norm(vector,axis=1)/maximum
    return mesh,vector/maximum,freq

def render(rst,rank,title,target):
    mesh,vec,freq=skin(rst,rank)
    original=mesh.points.copy()
    p=pv.Plotter(off_screen=True,window_size=(3840,2160))
    p.set_background('#f8f9fc')
    p.add_mesh(mesh,scalars='Mode magnitude',clim=(0,1),cmap='viridis',lighting=True,
               scalar_bar_args={'title':'Relative mode magnitude','vertical':True,'position_x':.055,'position_y':.22,'height':.47,'width':.048,'title_font_size':23,'label_font_size':22,'color':'#183046','fmt':'%.2f','n_labels':5})
    p.add_text(title,position=(150,1985),font_size=36,color='#08357e',font='arial')
    p.add_text(f'Mode {rank}     {freq:.3f} Hz',position=(154,1878),font_size=24,color='#252c36')
    p.add_text('Normalized eigenvector   |   6 mm displayed peak motion   |   3 slowed cycles',position=(150,90),font_size=20,color='#36404c')
    center=np.array([.0346,.0604,-.004]);p.camera_position=[center+np.array([.140,.065,-.223]),center,(0,1,0)]
    p.enable_parallel_projection();p.camera.parallel_scale=.083
    p.show(auto_close=False,interactive=False)
    temp=target.with_name(target.stem+'.part.mp4');target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise FileExistsError(target)
    exe=imageio_ffmpeg.get_ffmpeg_exe()
    # Render each unique sine amplitude once. Symmetric and repeated cycle frames are identical by construction.
    cache=ROOT/'.runtime/video_frames'/target.stem
    cache.mkdir(parents=True,exist_ok=True)
    from PIL import Image
    for k in range(-45,46):
        a=np.sin(k*np.pi/90)
        mesh.points=original+.006*a*vec
        mesh.point_data['Mode magnitude']=abs(a)*np.linalg.norm(vec,axis=1)
        p.render();rgb=p.screenshot(return_img=True)[:,:,:3]
        Image.fromarray(rgb).save(cache/f'state_{k+45:03d}.png',compress_level=1)
    p.close()
    frames=[(cache/f'state_{i:03d}.png').read_bytes() for i in range(91)]
    command=[exe,'-v','error','-y','-f','image2pipe','-framerate','60','-vcodec','png','-i','pipe:0','-frames:v','540','-c:v','h264_videotoolbox','-b:v','12M','-pix_fmt','yuv420p','-movflags','+faststart',str(temp)]
    with subprocess.Popen(command,stdin=subprocess.PIPE) as proc:
        for i in range(540):
            phase=i%180
            k=phase if phase<=45 else (90-phase if phase<=135 else phase-180)
            proc.stdin.write(frames[k+45])
        proc.stdin.close()
        if proc.wait():raise RuntimeError('Movie encoding failed')
    total,duration=imageio_ffmpeg.count_frames_and_secs(str(temp))
    assert total==540 and abs(duration-9)<.04,(total,duration)
    frames=imageio_ffmpeg.read_frames(str(temp));meta=next(frames);frames.close()
    assert tuple(meta['size'])==(3840,2160) and meta['fps']==60
    temp.replace(target)
    record=dict(name=target.name,case=title,rank=rank,frequency_Hz=freq,frames=total,duration_s=duration,resolution=meta['size'],fps=meta['fps'],bytes=target.stat().st_size,video_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),source_rst_sha256=hashlib.file_digest(rst.open('rb'),'sha256').hexdigest())
    target.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
    print(record,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('rst',type=Path);p.add_argument('rank',type=int);p.add_argument('title');p.add_argument('target',type=Path);a=p.parse_args();render(a.rst,a.rank,a.title,a.target)
