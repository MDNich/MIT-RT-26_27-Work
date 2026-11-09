"""Render paired, fixed RMS fields from native PSD files, using the same absolute colour limits."""
import argparse, csv, hashlib, json, math, subprocess
from pathlib import Path
import imageio_ffmpeg, numpy as np, pyvista as pv
from ansys.mapdl import reader
ROOT=Path(__file__).resolve().parents[1]
VARIANTS=['bare','flush_nylon','flush_aluminium','stand3_nylon','stand3_aluminium']
LABELS=['Bare board','Flush / nylon screws','Flush / aluminium screws','3 mm / nylon screws','3 mm / aluminium screws']
def field(path,component):
    result=reader.read_binary(str(path));grid=result.grid
    node,disp=result.nodal_solution([3,1]);order=np.argsort(node)
    solid=np.isin(grid.cell_data['ansys_elem_type_num'],[185,186,187,188])
    case=grid.cell_data['ansys_material_type']==850
    actors=[];peak=0
    for group,opaque in ((solid&~case,True),(solid&case,False)):
        if not group.any():continue
        surface=grid.extract_cells(group).extract_surface(algorithm='dataset_surface',nonlinear_subdivision=0).triangulate()
        ids=surface.point_data['ansys_node_num'];idx=order[np.searchsorted(node[order],ids)]
        assert np.array_equal(node[idx],ids)
        u=1000*np.abs(disp[idx,'XYZ'.index(component)]);assert np.all(np.isfinite(u))
        peak=max(peak,float(np.max(u)));surface.clear_data();surface['RMS displacement [mm]']=u
        actors.append((surface,opaque))
    return actors,peak
def camera(plot,phase,view):
    if view=='Rear view':initial=160.
    elif view=='Battery view':initial=13.
    else:initial=36.
    angle=math.radians(initial+22*math.sin(2*np.pi*phase))
    center=np.array([.0346,.0604,-.004])
    plot.camera_position=[center+np.array([.24*math.sin(angle),.06,-.24*math.cos(angle)]),center,(0,1,0)]
    plot.enable_parallel_projection();plot.camera.parallel_scale=.088
def draw(panels,title,axis,comp,view,limit,target,preview=False):
    n=len(panels);width,height=(1280,720) if preview else (3840,2160)
    p=pv.Plotter(shape=(1,1) if n==1 else (2,2),window_size=(width,height),off_screen=True,border=False)
    for i,(label,actors,peak) in enumerate(panels):
        p.subplot(i//2,i%2);p.set_background('#f8f9fc')
        for j,(mesh,opaque) in enumerate(actors):
            p.add_mesh(mesh,scalars='RMS displacement [mm]',clim=(0,limit),cmap='viridis',opacity=1. if opaque else .42,show_scalar_bar=j==0,
                       scalar_bar_args=dict(title='RMS [mm]',vertical=True,position_x=.03,position_y=.19,width=.047,height=.46,n_labels=4,fmt='%.3g',title_font_size=18,label_font_size=16,color='#25334a'))
        p.add_text(label+'   /   '+f'base {axis}, response {comp}',position='upper_left',font_size=13 if n>1 else 17,color='#08357e')
        p.add_text('1-sigma displacement   |   camera orbit' + ('   |   translucent case' if len(actors)>1 else ''),position='lower_left',font_size=8,color='#183046')
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
    target.with_suffix('.json').write_text(json.dumps(dict(subject=title,kind='Camera orbit of native fixed one-sigma RMS',base=axis,response=comp,view=view,range_mm=[0,limit],panels=[dict(label=a[0],visible_surface_peak_mm=a[2]) for a in panels],frames=frames,fps=60,duration_s=duration,sha256=hashlib.sha256(target.read_bytes()).hexdigest()),indent=2)+'\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('name');parser.add_argument('--campaign',default='nov08_01');parser.add_argument('--preview-rst',type=Path);args=parser.parse_args()
    source=ROOT.parent/'1/output/videos/power_board_4k60/index.csv'
    row=next(r for r in csv.DictReader(source.open()) if r['name']==args.name)
    assert row['kind']=='rms'
    base,response,view=(x.strip() for x in row['title'].split('|'));axis=base[-1];comp=response[-1]
    if args.preview_rst:
        actors,peak=field(args.preview_rst,comp)
        draw([('Reference reader check',actors,peak)],row['title'],axis,comp,view,peak,ROOT/'.runtime/qa/rms-reader-preview.png',True);return
    panels=[]
    for variant,name in zip(VARIANTS,LABELS):
        key=f'{variant}_psd_{axis}'
        audit=json.loads((ROOT/f'validation/global/{key}.json').read_text());assert audit['case']==key and audit['campaign']==args.campaign
        actors,peak=field(ROOT/f'.runtime/archive/{args.campaign}/{key}/file.rst',comp)
        panels.append((name,actors,peak))
    limit=max(i[2] for i in panels)
    for group,sub in [('without_case',panels[:1]),('with_case',panels[1:])]:
        draw(sub,row['title'],axis,comp,view,limit,ROOT/f'output/videos/{group}/power_board_4k60/{args.name}.mp4')
if __name__=='__main__':main()
