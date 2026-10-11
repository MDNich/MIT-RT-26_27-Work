from pathlib import Path
import sys,json,re
T=Path(__file__).resolve().parents[1];P=T.parents[1];name=sys.argv[1]
old=next(x for x in json.loads((P/'outputs/video_4k60_20261005_1928/manifest.json').read_text()) if x['name']==name)
assert old['kind']=='rms' and old['result']!=4289
base=re.search(r'Base ([XYZ])',old['title']).group(1);response=re.search(r'response ([XYZ])',old['title']).group(1);pcb='pcb_' in name
branch=T/('expand_'+base);assert(branch/'ACCEPTED.json').exists()
ids=[int(x) for x in (branch/'result_ids.txt').read_text().split(',')];result=ids[3] if pcb else ids['XYZ'.index(response)]
out=T/'videos'/name;out.mkdir(exist_ok=False)
local='C:\\Temp\\PBMotionVideos\\'+name;host='Z:'+str(out).split('/Users/mdn',1)[1].replace('/','\\')
view='PCB-scoped contour - isometric view' if pcb else 'Full assembly - '+{'Iso':'isometric view','Battery':'battery view','Back':'rear view'}[old['camera']]
m={'base':base,'response':response,'view_label':view,'source_result_id':result,'source_analysis_id':int((branch/'IMPORTED.txt').read_text()),'camera':old['camera'],'frame_count':480,'physical_first_time_s':1+1/16384,'frame_dt_s':1/16384,'fps':60,'motion_scale':50,'slowdown':16384/60,'seed':20261005+'XYZ'.index(base),'contour_units':'m','source':'expand_'+base,'local_output':local,'host_output':host}
(out/'manifest.json').write_text(json.dumps(m,indent=2))
job={'result':result,'camera':old['camera'],'local_output':local,'host_output':host}
(out/'export.py').write_text('JOB='+repr(job)+'\n'+(T/'control/render_local_template.py').read_text())
print(out/'export.py')
