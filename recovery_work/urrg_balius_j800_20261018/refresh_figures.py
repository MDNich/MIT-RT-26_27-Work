from pathlib import Path
import sys,csv,json,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from balius_recovery_study import *
study=json.loads((OUTPUT/'study_inputs.json').read_text());launch=study['launch_site']
boundary=load_perimeter(OUTPUT/'earth_data/perimeter_mgrs.txt',launch)
terrain=Terrain(OUTPUT/'earth_data/usgs_3dep_dem_2m.tif',boundary['crs']);texture=texture_data()
results=[]
for key,*_ in DESIGNS:
 out=OUTPUT/key;s=json.loads((out/'summary.json').read_text())
 g=list(csv.DictReader((out/'terrain_landings.csv').open()))
 for r in g:
  for k in r.keys()-{'case_id','motor','design','ground_hit','warnings','inside_green_area'}:r[k]=float(r[k])
  for k in ['ground_hit','inside_green_area']:r[k]=r[k].lower()=='true'
 t=[np.genfromtxt(out/'terrain_tracks'/f'{r["case_id"]}_sim3.csv.gz',delimiter=',',skip_header=1) for r in g]
 results.append((s,g,t,load_rows(out/'extended_runs.csv')))
report=json.loads((OUTPUT/'comparison_summary.json').read_text())
report['map_half_width_m']=300.0
limit,limit3d,top=300,report['scene_half_width_m'],report['scene_top_m']
mesh=ground_mesh(terrain,boundary,texture,limit3d)
for s,g,t,raw in results:
 make_satellite(s,g,boundary,texture,limit)
 make_satellite(s,g,boundary,texture,limit,perimeter=True)
 make_3d(s,g,t,mesh,limit3d,top)
fig=plt.figure(figsize=(16,9),facecolor='#f7f9fb')
for i,(s,g,t,raw) in enumerate(results):
 ax=fig.add_subplot(1,2,i+1,projection='3d',computed_zorder=False)
 add_3d(ax,s,g,t,mesh,limit3d,top)
 fig.text(.25+.5*i,.855,f'{s["design"]["label"]} · J800T\n{s["completed"]} completed · {s["inside_percent"]:.1f}% inside',ha='center',va='center',fontsize=15)
fig.suptitle('URRG · Balius J800T trajectories meet the terrain',fontsize=23,fontweight='bold',y=.97,color='#173247')
fig.text(.5,.915,'Identical sampled weather · source recovery settings retained · true vertical scale (1×)',ha='center',fontsize=12)
fig.text(.5,.055,'Native OpenRocket paths stop at first terrain contact. Satellite texture: Esri World Imagery · Terrain: USGS 3DEP / NAVD88',ha='center',fontsize=10)
fig.subplots_adjust(left=.015,right=.98,top=.82,bottom=.12,wspace=.03)
fig.savefig(OUTPUT/'comparison_3d.png',dpi=180);plt.close(fig)
(OUTPUT/'comparison_summary.json').write_text(json.dumps(report,indent=2)+'\n')
package(results,report)
