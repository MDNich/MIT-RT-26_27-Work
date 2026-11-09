"""Export paired 4K60 signed-motion clips, including discontinuous dynamic PCB stress."""
import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pyvista as pv
from PIL import Image
from native_rst import read_rst

from motion_surface import displacement_basis,pcb_skin
from pcb_dynamic_stress import cache_modes,digest,equivalent,extrema
from rms_video import ROOT,VARIANTS,LABELS
from seeded_motion import FS,FRAMES
from film_identity import verified,already_rendered

# The original subjects specify the visible scope and response direction.
SUBJECTS={
 'random_fig06_baseX_responseX':('X','assembly','X'), 'random_fig11_baseY_responseZ':('Y','assembly','Z'),
 'random_fig14_baseZ_responseZ':('Z','assembly','Z'), 'random_fig15_pcb_baseX':('X','pcb','Z'),
 'random_fig16_pcb_baseY':('Y','pcb','Z'), 'random_fig17_pcb_baseZ':('Z','pcb','Z'),
 'random_fig18_pcb_stress':('X','pcb','stress')}


def field_files(rst,clip,period,scope,component,cache,stress_cache,source_sha=None):
    cache.mkdir(parents=True,exist_ok=True)
    seal=cache/'fields.json'
    identity=dict(rst_sha256=source_sha or digest(rst),coordinates_sha256=digest(clip),frames=period.tolist(),scope=scope,component=component)
    if seal.exists():
        saved=json.loads(seal.read_text())
        if saved['identity']!=identity:raise ValueError('Refusing to use fields from a different basis or clip')
        return saved
    r=read_rst(str(rst));g=r.grid
    if clip.suffix=='.csv':
        q=np.loadtxt(clip,delimiter=',',skiprows=1)[:,1:]
    else:
        with np.load(clip) as arr:
            q=arr['coordinates']
            assert np.array_equal(arr['time_s'],FRAMES/FS) and np.allclose(r.time_values,arr['frequencies_Hz'],rtol=1e-9)
    assert q.shape==(480,len(r.time_values))
    q=q[period];parts=[];limit=0.
    solid=np.isin(g.cell_data['ansys_elem_type_num'],[185,186,187,188]);mat=g.cell_data['ansys_material_type']
    if component=='stress':
        meta=cache_modes(rst,stress_cache);assert meta['rst_sha256']==identity['rst_sha256']
        mesh,ids,idx=pcb_skin(r,np.load(stress_cache/'locations.npz'))
        parts.append((mesh,ids,False))
        tens=np.load(stress_cache/'tensors.npy',mmap_mode='r')
        limit=float(extrema(tens,q)[1].max())*1.e-6
        writer=np.lib.format.open_memmap(cache/'stress.npy',mode='w+',dtype=np.float32,shape=(len(q),len(idx)))
        for j in range(0,len(idx),2048):
            block=np.ascontiguousarray(tens[:,idx[j:j+2048]]).reshape(len(tens),-1)
            writer[:,j:j+2048]=1.e-6*equivalent((q@block).reshape(len(q),-1,6))
        writer.flush();del writer
    else:
        mask=solid&(mat==208) if scope=='pcb' else solid
        for keep,case in ((mask&(mat!=850),False),(mask&(mat==850),True)):
            if not keep.any():continue
            mesh=g.extract_cells(keep).extract_surface(algorithm='dataset_surface',nonlinear_subdivision=0).triangulate()
            ids=mesh.point_data['ansys_node_num'].copy()
            parts.append((mesh,ids,case))
    ids=np.unique(np.concatenate([entry[1] for entry in parts]))
    basis=displacement_basis(r,ids)
    writer=np.lib.format.open_memmap(cache/'displacement.npy',mode='w+',dtype=np.float32,shape=(len(q),len(ids),3))
    for j in range(0,len(ids),4096):
        val=(q@np.ascontiguousarray(basis[:,j:j+4096]).reshape(len(basis),-1)).reshape(len(q),-1,3)
        writer[:,j:j+4096]=val
        if component!='stress':limit=max(limit,float(1000*np.abs(val[:,:,'XYZ'.index(component)]).max()))
    writer.flush();del writer
    geometries=[]
    for j,(mesh,node,case) in enumerate(parts):
        mesh.clear_data();mesh.point_data['motion_row']=np.searchsorted(ids,node)
        mesh.save(cache/f'mesh{j}.vtp')
        geometries.append({'file':f'mesh{j}.vtp','case_surface':case})
    if not np.isfinite(limit) or limit<=0:raise ValueError('Invalid common scale')
    data=dict(identity=identity,geometries=geometries,peak=limit)
    seal.write_text(json.dumps(data,indent=2)+'\n')
    return data


def render(items,target,ax,scope,comp,period,limit,preview):
    n=len(items);big=(3840,2160);px=(1280,720) if preview else big
    if not preview:
        field='Dynamic von Mises [MPa]' if comp=='stress' else f'Signed U{comp} [mm]'
        fields=dict(base=ax,scope=scope,response=field,scale=[0 if comp=='stress' else -limit,limit],
           panels=[dict(name=name,rst_sha256=d['identity']['rst_sha256'],coordinates_sha256=d['identity']['coordinates_sha256'],peak=d['peak']) for name,_,d in items],
           display_displacement_multiplier=50,physical_interval_s=(FRAMES[[0,-1]]/FS).tolist())
        if already_rendered(target,fields):return
    plot=pv.Plotter(shape=(2,2) if n==4 else (1,1),window_size=px,off_screen=True,border=False)
    field='Dynamic von Mises [MPa]' if comp=='stress' else f'Signed U{comp} [mm]'
    series=[];clim=(0,limit) if comp=='stress' else (-limit,limit)
    for i,(name,cache,data) in enumerate(items):
        plot.subplot(i//2,i%2);plot.set_background('#f8f9fc')
        dis=np.load(cache/'displacement.npy',mmap_mode='r')
        stress=np.load(cache/'stress.npy',mmap_mode='r') if comp=='stress' else None
        for j,part in enumerate(data['geometries']):
            mesh=pv.read(cache/part['file']);ix=mesh.point_data['motion_row'];orig=mesh.points.copy()
            mesh.point_data[field]=np.zeros(len(orig))
            plot.add_mesh(mesh,scalars=field,cmap='YlOrRd' if comp=='stress' else 'coolwarm',clim=clim,lighting=comp!='stress',
                          opacity=.42 if part['case_surface'] else 1.,show_scalar_bar=(i==0 and j==0),
                          scalar_bar_args=dict(title='MPa' if comp=='stress' else 'mm',vertical=True,position_x=.085,
                          position_y=.20,width=.045,height=.48,n_labels=5,fmt='%.3g',label_font_size=16,title_font_size=16,color='#182e4c'))
            series.append((mesh,orig,ix,dis,stress))
        plot.add_text(f'{name}   /   Base {ax}   /   {field}',position='upper_left',font='arial',font_size=14 if preview else 21,color='#08357E')
        plot.add_text(('PCB only' if scope=='pcb' else 'Assembly')+'   /   50x displacement   /   time slowed 273x',position='lower_left',
                      font='arial',font_size=11 if preview else 16,color='#183046')
        center=np.array([.0346,.0604,-.004])
        plot.camera_position=[center+(np.array([.14,.065,-.223]) if scope=='assembly' else np.array([.115,-.080,.220])),center,(0,1,0)]
        plot.enable_parallel_projection();plot.camera.parallel_scale=.083
    plot.show(auto_close=False,interactive=False)
    def one(k):
        for mesh,orig,ix,dis,stress in series:
            u=dis[k,ix];mesh.points=orig+50*u
            mesh.point_data[field]=stress[k] if comp=='stress' else u[:,'XYZ'.index(comp)]*1000
        for i in range(n):
            plot.subplot(i//2,i%2)
            plot.add_text(f't = {FRAMES[period[k]]/FS:.6f} s',position='upper_right',name='physical_time',
                          font_size=10 if preview else 15,font='arial',color='#183046')
        plot.render();return np.ascontiguousarray(plot.screenshot(return_img=True)[:,:,:3])
    if preview:
        Image.fromarray(one(0)).save(target);plot.close();return
    if target.exists():raise FileExistsError(target)
    target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.part.mp4')
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','3840x2160','-r','60',
         '-i','pipe:0','-an','-c:v','h264_videotoolbox','-b:v','15M','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as process:
        for k in range(len(period)):process.stdin.write(one(k).tobytes())
        process.stdin.close()
        if process.wait():raise RuntimeError('Encoding failed')
    plot.close();total,duration=imageio_ffmpeg.count_frames_and_secs(str(tmp))
    reader_=imageio_ffmpeg.read_frames(str(tmp));meta=next(reader_);reader_.close()
    assert total==480 and abs(duration-8)<.03 and meta['fps']==60 and tuple(meta['size'])==big
    tmp.replace(target)
    target.with_suffix('.json').write_text(json.dumps(dict(sha256=digest(target),frames=total,duration_s=duration,fps=60,resolution=big,base=ax,
        scope=scope,response=field,scale=clim,display_displacement_multiplier=50,physical_interval_s=(FRAMES[[0,-1]]/FS).tolist(),
        panels=[dict(name=name,rst_sha256=d['identity']['rst_sha256'],coordinates_sha256=d['identity']['coordinates_sha256'],peak=d['peak']) for name,_,d in items]),indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('subject',choices=SUBJECTS)
    p.add_argument('--historical-preview-rst',type=Path);p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args();ax,scope,comp=SUBJECTS[args.subject]
    period=np.arange(480) if not args.historical_preview_rst else np.array([119])
    items=[]
    if args.historical_preview_rst:
        rst=args.historical_preview_rst
        clip=ROOT.parent/f'1/output/latex/random_vibration/reproduction/motion/inputs/modal_coordinates_{ax}_clip.csv'
        cache=ROOT/f'.runtime/qa/seeded_preview/{args.subject}'
        data=field_files(rst,clip,period,scope,comp,cache,ROOT/'.runtime/qa/october_pcb_stress')
        render([('October reference',cache,data)],cache/'preview.png',ax,scope,comp,period,data['peak'],True);return
    for v,name in zip(VARIANTS,LABELS):
        key=f'{v}_motion_{ax}'
        proof=json.loads((ROOT/f'validation/motion/{key}.json').read_text())
        basis=json.loads((ROOT/f'validation/global/{v}_basis.json').read_text())
        assert proof['case']==key and proof['branch']==v and proof['campaign']==basis['campaign']==args.campaign
        rst=ROOT/f'.runtime/archive/{args.campaign}/{v}_basis/file.rst';src=verified(rst,basis['rst_sha256'])
        clip=ROOT/f'.runtime/post/{args.campaign}/{key}/coordinates.npz'
        assert proof['basis_rst_sha256']==basis['rst_sha256']==src and proof['clip_sha256']==verified(clip,proof['clip_sha256'])
        root=ROOT/f'.runtime/post/{args.campaign}/{v}_films';cache=root/args.subject
        data=field_files(rst,clip,period,scope,comp,cache,root/'pcb_stress',src);items.append((name,cache,data))
    limit=max(d['peak'] for _,_,d in items)
    for group,panels in [('without_case',items[:1]),('with_case',items[1:])]:
        dest=ROOT/f'output/videos/{group}/power_board_random_motion_4k60/{args.subject}.mp4'
        render(panels,dest,ax,scope,comp,period,limit,False)
if __name__=='__main__':main()
