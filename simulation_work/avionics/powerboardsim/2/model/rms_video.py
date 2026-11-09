"""Render paired, fixed RMS fields from native PSD files, using the same absolute colour limits."""
import argparse, csv, hashlib, json, math, subprocess
from pathlib import Path
import imageio_ffmpeg, numpy as np, pyvista as pv
from native_rst import read_rst
from study_cases import native_case
from film_identity import verified,already_rendered,publish_baseline
ROOT=Path(__file__).resolve().parents[1]
VARIANTS=['bare','flush_nylon','flush_aluminium','stand3_nylon','stand3_aluminium']
LABELS=['Bare board','Flush / nylon screws','Flush / aluminium screws','3 mm / nylon screws','3 mm / aluminium screws']
SNUG_VARIANTS=['bare','snug125_nylon','snug125_aluminium']
VARIANT_LABELS={**dict(zip(VARIANTS,LABELS,strict=True)), 'snug125_nylon':'1.25 mm Balius / nylon screws',
                'snug125_aluminium':'1.25 mm Balius / aluminium screws'}


def video_directory(snug_fit):
    base=ROOT/'output/videos'
    return base/'snug125' if snug_fit else base


def surfaces(result):
    grid=result.grid
    solid=np.isin(grid.cell_data['ansys_elem_type_num'],[185,186,187,188])
    case=grid.cell_data['ansys_material_type']==850
    items=[]
    for group,opaque in ((solid&~case,True),(solid&case,False)):
        if not group.any():continue
        surface=grid.extract_cells(group).extract_surface(algorithm='dataset_surface',nonlinear_subdivision=0).triangulate()
        items.append((surface,opaque))
    return items


def apply_field(items,nodes,values_mm):
    order=np.argsort(nodes)
    actors=[];peak=0.
    for surface,opaque in items:
        ids=surface.point_data['ansys_node_num']
        idx=order[np.searchsorted(nodes[order],ids)]
        assert np.array_equal(nodes[idx],ids)
        u=values_mm[idx];assert np.isfinite(u).all() and u.min()>=0
        peak=max(peak,float(u.max()))
        surface.clear_data();surface['RMS displacement [mm]']=u
        actors.append((surface,opaque))
    return actors,peak


def field(path,component):
    result=read_rst(str(path))
    node,disp=result.nodal_solution([3,1])
    return apply_field(surfaces(result),node,1000*np.abs(disp[:,'XYZ'.index(component)]))
def camera(plot,phase,view):
    if view=='Rear view':initial=160.
    elif view=='Battery view':initial=13.
    else:initial=36.
    angle=math.radians(initial+22*math.sin(2*np.pi*phase))
    center=np.array([.0346,.0604,-.004])
    plot.camera_position=[center+np.array([.24*math.sin(angle),.06,-.24*math.cos(angle)]),center,(0,1,0)]
    plot.enable_parallel_projection();plot.camera.parallel_scale=.088
def draw(panels,title,axis,comp,view,limit,target,preview=False,sources=None):
    layout_record={'layout_revision':2} if len(panels)>1 else {}
    integrated=bool(sources and any('surface_field_sha256' in s for s in sources))
    if integrated:
        assert all('surface_field_sha256' in s for s in sources)
        layout_record['field_method']='independent'
    if not preview and already_rendered(target,dict(subject=title,base=axis,response=comp,view=view,range_mm=[0,limit],sources=sources,**layout_record)):return
    n=len(panels);width,height=(1280,720) if preview else (3840,2160)
    layout={1:(1,1),2:(1,2),4:(2,2)}[n]
    p=pv.Plotter(shape=layout,window_size=(width,height),off_screen=True,border=False)
    for i,(label,actors,peak) in enumerate(panels):
        p.subplot(i//2,i%2);p.set_background('#f8f9fc')
        for j,(mesh,opaque) in enumerate(actors):
            p.add_mesh(mesh,scalars='RMS displacement [mm]',clim=(0,limit),cmap='viridis',opacity=1. if opaque else .42,show_scalar_bar=(i==0 and j==0),
                       scalar_bar_args=dict(title='RMS [mm]',vertical=True,position_x=.085,position_y=.19,width=.047,height=.46,n_labels=4,fmt='%.3g',title_font_size=26 if n>1 else 16,label_font_size=22 if n>1 else 14,color='#25334a'))
        p.add_text(label+'   /   '+f'base {axis}, response {comp}',position='upper_left',font_size=27 if n>1 else 17,color='#08357e')
        caption='1-sigma displacement   |   camera orbit'
        if len(actors)>1:caption+='   |   fixed contact state'
        if integrated:caption+='\nIndependent integration of native modes'
        p.add_text(caption,position='lower_left',font_size=16 if n>1 else 8,color='#183046')
        camera(p,0,view)
    p.show(auto_close=False,interactive=False)
    if preview:
        p.screenshot(str(target));p.close();return
    temp=target.with_name(target.stem+'.part.mp4');target.parent.mkdir(parents=True,exist_ok=True)
    exe=imageio_ffmpeg.get_ffmpeg_exe()
    cmd=[exe,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r','60','-i','pipe:0','-an','-c:v','h264_videotoolbox','-b:v','14M','-pix_fmt','yuv420p','-movflags','+faststart',str(temp)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        for frame in range(480):
            for i in range(n):p.subplot(i//2,i%2);camera(p,frame/480,view)
            p.render();proc.stdin.write(np.ascontiguousarray(p.screenshot(return_img=True)[:,:,:3]).tobytes())
        proc.stdin.close();assert proc.wait()==0
    p.close()
    frames,duration=imageio_ffmpeg.count_frames_and_secs(str(temp));assert frames==480 and abs(duration-8)<.03
    stream=imageio_ffmpeg.read_frames(str(temp));meta=next(stream);stream.close()
    assert tuple(meta['size'])==(3840,2160) and meta['fps']==60
    temp.replace(target)
    target.with_suffix('.json').write_text(json.dumps(dict(subject=title,resolution=[3840,2160],sources=sources,kind='Camera orbit of independently integrated fixed RMS' if integrated else 'Camera orbit of native fixed one-sigma RMS',base=axis,response=comp,view=view,range_mm=[0,limit],**layout_record,panels=[dict(label=a[0],visible_surface_peak_mm=a[2]) for a in panels],frames=frames,fps=60,duration_s=duration,sha256=hashlib.sha256(target.read_bytes()).hexdigest()),indent=2)+'\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('name');parser.add_argument('--campaign',default='nov08_01');parser.add_argument('--preview-rst',type=Path);mode=parser.add_mutually_exclusive_group();mode.add_argument('--bare-only',action='store_true');mode.add_argument('--raised-only',action='store_true')
    mode.add_argument('--snug-fit',action='store_true')
    parser.add_argument('--independent-raised',action='store_true')
    args=parser.parse_args()
    assert not args.independent_raised or args.raised_only
    with (ROOT/'validation/video_pairs.csv').open() as stream:
        row=next(r for r in csv.DictReader(stream) if Path(r['file']).stem==args.name)
    assert row['kind']=='camera motion over fixed RMS'
    title=row['october_title']
    base,response,view=(x.strip() for x in title.split('|'));axis=base[-1];comp=response[-1]
    if args.preview_rst:
        actors,peak=field(args.preview_rst,comp)
        draw([('Reference reader check',actors,peak)],title,axis,comp,view,peak,ROOT/'.runtime/qa/rms-reader-preview.png',True);return
    panels=[];sources=[]
    variants=VARIANTS[:1] if args.bare_only else ([VARIANTS[0],*VARIANTS[3:]] if args.raised_only else VARIANTS)
    if args.snug_fit:variants=SNUG_VARIANTS
    for variant in variants:
        name=VARIANT_LABELS[variant]
        key=native_case(variant,'psd_'+axis)
        if args.independent_raised and variant!='bare':
            from rms_film_fields import film_field
            actors,peak,source=film_field(variant,axis,comp,args.campaign)
        else:
            audit=json.loads((ROOT/f'validation/global/{key}.json').read_text());assert audit['case']==key and audit['campaign']==args.campaign
            rst=ROOT/f'.runtime/archive/{args.campaign}/{key}/file.rst'
            verified(rst,audit['rst_sha256']);source=dict(variant=variant,rst_sha256=audit['rst_sha256'])
            actors,peak=field(rst,comp)
        sources.append(source)
        panels.append((name,actors,peak))
    limit=max(i[2] for i in panels)
    dest=video_directory(args.snug_fit)/f'without_case/power_board_4k60/{args.name}.mp4'
    generation=ROOT/'.runtime/films/baselines'/args.name/(float(limit).hex()+'.mp4')
    draw(panels[:1],title,axis,comp,view,limit,generation,sources=sources[:1])
    if not args.bare_only:
        cased=video_directory(args.snug_fit)/f'with_case/power_board_4k60/{args.name}.mp4'
        group='snug125' if args.snug_fit else ('raised' if args.raised_only else 'all_four')
        if args.independent_raised:group+='-independent'
        take=ROOT/'.runtime/films/comparisons'/args.name/(group+'_v2')/(float(limit).hex()+'.mp4')
        draw(panels[1:],title,axis,comp,view,limit,take,sources=sources[1:])
        sidecar=cased.with_suffix('.json')
        if sidecar.exists():
            previous=json.loads(sidecar.read_text())['sources']
            current={s['variant']:s for s in sources[1:]}
            for old in previous:
                new=current[old['variant']]
                if new==old:continue
                if 'surface_field_sha256' not in old or 'surface_field_sha256' in new:
                    raise ValueError('Previously published case has changed or is missing from this comparison')
                from rms_film_fields import compare_native
                compare_native(old['variant'],axis,args.campaign)
                prior=json.loads((ROOT/'validation/rms_film_fields'/(native_case(old['variant'],'psd_'+axis)+'.json')).read_text())
                assert prior['rst_sha256']==old['rst_sha256'] and prior['surface_field_sha256']==old['surface_field_sha256']
        # Finish both encodes and source checks before replacing either publication.
        publish_baseline(take,cased,('subject','base','response','view'))
    publish_baseline(generation,dest,('subject','base','response','view','sources'))
if __name__=='__main__':main()
