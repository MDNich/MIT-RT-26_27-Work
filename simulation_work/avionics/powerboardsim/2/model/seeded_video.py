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
from study_cases import branch_for,native_case
from film_identity import publish_baseline

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
    fields=None
    if source_sha is not None and rst.parent.name!='bare_basis':
        from basis_comparison import field_files as native_mode_files
        campaign=rst.parent.parent.name
        assert rst==ROOT/'.runtime/archive'/campaign/rst.parent.name/'file.rst'
        fields=native_mode_files(rst.parent.name,campaign,source_sha,r.nsets)
    basis=displacement_basis(r,ids,fields)
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


def render(items,target,ax,scope,comp,period,limit,preview,method='native'):
    n=len(items);big=(3840,2160);px=(1280,720) if preview else big
    if not preview:
        field='Dynamic von Mises [MPa]' if comp=='stress' else f'Signed U{comp} [mm]'
        fields=dict(coordinate_method=method,base=ax,scope=scope,response=field,scale=[0 if comp=='stress' else -limit,limit],
           panels=[dict(name=name,rst_sha256=d['identity']['rst_sha256'],coordinates_sha256=d['identity']['coordinates_sha256'],peak=d['peak']) for name,_,d in items],
           display_displacement_multiplier=50,physical_interval_s=(FRAMES[[0,-1]]/FS).tolist())
        if already_rendered(target,fields):return
    plot=pv.Plotter(shape={1:(1,1),2:(1,2),4:(2,2)}[n],window_size=px,off_screen=True,border=False)
    field='Dynamic von Mises [MPa]' if comp=='stress' else f'Signed U{comp} [mm]'
    series=[];clocks=[];clim=(0,limit) if comp=='stress' else (-limit,limit)
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
                          position_y=.20,width=.045,height=.48,n_labels=5,fmt='%.3g',label_font_size=21,title_font_size=23,color='#182e4c'))
            series.append((mesh,orig,ix,dis,stress))
        plot.add_text(f'{name}   /   Base {ax}   /   {field}',position='upper_left',font='arial',font_size=14 if preview else 21,color='#08357E')
        integration='Independent modal integration' if method=='independent' else 'Native modal coordinates'
        footer=('PCB' if scope=='pcb' else 'Assembly')+'   /   50x displacement   /   time slowed 273x'
        plot.add_text(footer+'\n'+integration+'   /   fixed contact state',position='lower_left',
                      font='arial',font_size=11 if preview else 16,color='#183046')
        clocks.append(plot.add_text('t = 0.000000 s',position='upper_right',font_size=10 if preview else 15,font='arial',color='#183046'))
        center=np.array([.0346,.0604,-.004])
        plot.camera_position=[center+(np.array([.14,.065,-.223]) if scope=='assembly' else np.array([.115,-.080,.220])),center,(0,1,0)]
        plot.enable_parallel_projection();plot.camera.parallel_scale=.083
    plot.show(auto_close=False,interactive=False)
    def one(k):
        for mesh,orig,ix,dis,stress in series:
            u=dis[k,ix];mesh.points=orig+50*u
            mesh.point_data[field]=stress[k] if comp=='stress' else u[:,'XYZ'.index(comp)]*1000
        for clock in clocks:
            clock.SetText(3,f't = {FRAMES[period[k]]/FS:.6f} s')
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
    target.with_suffix('.json').write_text(json.dumps(dict(sha256=digest(target),frames=total,duration_s=duration,fps=60,resolution=big,base=ax,coordinate_method=method,
        scope=scope,response=field,scale=clim,display_displacement_multiplier=50,physical_interval_s=(FRAMES[[0,-1]]/FS).tolist(),
        panels=[dict(name=name,rst_sha256=d['identity']['rst_sha256'],coordinates_sha256=d['identity']['coordinates_sha256'],peak=d['peak']) for name,_,d in items]),indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('subject',choices=SUBJECTS)
    p.add_argument('--historical-preview-rst',type=Path);p.add_argument('--campaign',default='nov08_01');group=p.add_mutually_exclusive_group();group.add_argument('--bare-only',action='store_true');group.add_argument('--raised-only',action='store_true')
    p.add_argument('--coordinates',choices=('native','independent'),default='native')
    args=p.parse_args();ax,scope,comp=SUBJECTS[args.subject]
    period=np.arange(480) if not args.historical_preview_rst else np.array([119])
    items=[]
    if args.historical_preview_rst:
        rst=args.historical_preview_rst
        clip=ROOT.parent/f'1/output/latex/random_vibration/reproduction/motion/inputs/modal_coordinates_{ax}_clip.csv'
        cache=ROOT/f'.runtime/qa/seeded_preview/{args.subject}'
        data=field_files(rst,clip,period,scope,comp,cache,ROOT/'.runtime/qa/october_pcb_stress')
        render([('October reference',cache,data)],cache/'preview.png',ax,scope,comp,period,data['peak'],True);return
    variants=VARIANTS[:1] if args.bare_only else ([VARIANTS[0],*VARIANTS[3:]] if args.raised_only else VARIANTS)
    method=args.coordinates
    assert method=='native' or args.raised_only
    category='motion' if method=='native' else 'independent_motion'
    for v in variants:
        name=LABELS[VARIANTS.index(v)]
        key=native_case(v,'motion_'+ax);branch=branch_for(v,'basis')
        proof=json.loads((ROOT/f'validation/{category}/{key}.json').read_text())
        basis=json.loads((ROOT/f'validation/global/{branch}_basis.json').read_text())
        assert proof['case']==key and proof['branch']==branch and proof['campaign']==basis['campaign']==args.campaign
        rst=ROOT/f'.runtime/archive/{args.campaign}/{branch}_basis/file.rst';src=verified(rst,basis['rst_sha256'])
        coord_root=ROOT/f'.runtime/post/{args.campaign}/{key}'
        if method=='independent':coord_root=coord_root/'independent'
        clip=coord_root/'coordinates.npz'
        assert proof['basis_rst_sha256']==basis['rst_sha256']==src and proof['clip_sha256']==verified(clip,proof['clip_sha256'])
        root=ROOT/f'.runtime/post/{args.campaign}/{v}_films';cache=root/args.subject/proof['clip_sha256']
        data=field_files(rst,clip,period,scope,comp,cache,root/'pcb_stress',src);items.append((name,cache,data))
    limit=max(d['peak'] for _,_,d in items)
    dest=ROOT/f'output/videos/without_case/power_board_random_motion_4k60/{args.subject}.mp4'
    group='raised' if args.raised_only else ('bare' if args.bare_only else 'all_four')
    generations=ROOT/'.runtime/films/seeded'/args.subject/method/group/float(limit).hex()
    targets=[(items[:1],dest,generations/'bare.mp4')]
    if not args.bare_only:
        cased=ROOT/f'output/videos/with_case/power_board_random_motion_4k60/{args.subject}.mp4'
        targets.append((items[1:],cased,generations/'cased.mp4'))
    for panels,out,take in targets:
        render(panels,take,ax,scope,comp,period,limit,False,method)
        old=out.with_suffix('.json')
        if not old.is_file():continue
        previous=json.loads(old.read_text())
        by_name={name:d['identity'] for name,_,d in panels}
        old_method=previous.get('coordinate_method','native')
        if old_method=='native' and method!='native':raise ValueError('Cannot replace native history with independent integration')
        for panel in previous['panels']:
            current=by_name[panel['name']]
            assert current['rst_sha256']==panel['rst_sha256']
            if old_method==method:
                assert current['coordinates_sha256']==panel['coordinates_sha256']
            else:
                branch=VARIANTS[LABELS.index(panel['name'])]
                native=json.loads((ROOT/'validation/motion'/(native_case(branch,'motion_'+ax)+'.json')).read_text())
                assert native['independent_clip_check']['clip_sha256']==panel['coordinates_sha256']
                assert native['clip_sha256']==current['coordinates_sha256']
    for _,out,take in reversed(targets):
        publish_baseline(take,out,('base','scope','response','physical_interval_s','display_displacement_multiplier'))
if __name__=='__main__':main()
