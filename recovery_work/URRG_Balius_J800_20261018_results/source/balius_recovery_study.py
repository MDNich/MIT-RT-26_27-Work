"""Paired J800T recovery Monte Carlo for the two supplied Balius CDR designs.

Reuses the validated native-engine runner and terrain intersection implementation.
Preserves each ORK design and its configuration-specific recovery defaults.
"""
from __future__ import annotations
import argparse,csv,gzip,json,shutil,zipfile,copy
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Polygon as PlotPolygon
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import rasterio
from scipy.ndimage import map_coordinates
from pyproj import Transformer
from shapely.geometry import Point,Polygon,box,mapping
from shapely import contains_xy
import montecarlo_recovery as mc
from recovery_perimeter import load_perimeter
from recovery_terrain import Terrain,first_contact,load_rows,thin_track

HERE=Path(__file__).resolve().parent
CACHE=HERE/'urrg_no_drogue_20261016_terrain'
OUTPUT=HERE/'urrg_balius_j800_20261018'
DESIGNS=[('canards','Balius CDR · Canards','#39deec',Path('/Users/mdn/Downloads/balius-cdr-canards.ork')),
         ('co2','Balius CDR · CO₂','#ffb955',Path('/Users/mdn/Downloads/balius-cdr-co2.ork'))]
JAR=Path('/tmp/urrg-recovery-engine-20261016.jar')
JAVA='/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home'
SEED=20261011


def write_csv(path,rows):
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def inspect_design(path):
    with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read('rocket.ork'))
    motors={m.attrib['configid']:m for m in root.findall('.//motormount/motor')}
    candidates=[]
    for i,s in enumerate(root.findall('./simulations/simulation')):
        cid=s.findtext('conditions/configid');m=motors[cid]
        if m.findtext('designation')=='J800T':candidates.append((i,s,m))
    if not candidates:raise ValueError(f'No existing J800T simulation in {path}')
    # The descriptive named simulation and generic Simulation 3 are duplicates.
    # Require identical conditions, then use the descriptive named entry.
    signatures={ET.tostring(s.find('conditions')) for _,s,_ in candidates}
    if len(signatures)!=1:raise ValueError('Multiple materially different J800T simulations; choose explicitly.')
    i,s,m=candidates[-1];cid=s.findtext('conditions/configid');cond=s.find('conditions')
    chutes=root.findall('.//parachute')
    if len(chutes)!=1:raise ValueError('This study expects one main parachute.')
    chute=chutes[0];override=chute.find(f"deploymentconfiguration[@configid='{cid}']")
    deployment=override if override is not None else chute
    event=deployment.findtext('deployevent');delay=float(deployment.findtext('deploydelay'))
    if event!='apogee' or delay!=1:raise ValueError('Unexpected recovery setting; review rather than overwrite.')
    info={'source_path':str(path),'source_sha256':mc.digest(path),'motor':'J800T',
          'motor_digest':m.findtext('digest'),'motor_configuration_id':cid,
          'simulation_index':i,'simulation_name':s.findtext('name'),
          'equivalent_j800_simulations':[j for j,_,_ in candidates],
          'rocket_xml_sha256':__import__('hashlib').sha256(ET.tostring(root.find('rocket'))).hexdigest(),
          'rail_length_m':float(cond.findtext('launchrodlength')),'rail_angle_deg':float(cond.findtext('launchrodangle')),
          'timestep_s':float(cond.findtext('timestep')),'geodetic_method':cond.findtext('geodeticmethod'),
          'main_diameter_m':float(chute.findtext('diameter')),'main_cd_setting':chute.findtext('cd'),
          'deployment_event':event,'deployment_delay_s':delay,'recovery_override_selected':override is not None,
          'simulation_extensions':len(s.findall('extension')),
          'control_note':'No active flight-control extension is stored in these simulations; geometry and mass effects are simulated as saved.'}
    return root,info


def prepare():
    OUTPUT.mkdir(exist_ok=True)
    launch=mc.site(HERE.parent/'ui_work/rocket_UI_v0a/src/rocket_gnc_monitor/site_presets.py')
    shared=OUTPUT/'earth_data';shared.mkdir(exist_ok=True)
    for name in ['usgs_3dep_dem_2m.tif','satellite_local.tif','imagery_source.json','dem_request.json','dem_identify_pad.json','perimeter_mgrs.txt']:
        shutil.copy2(CACHE/name,shared/name)
    # Exact same 500 weather cases as the previous study, paired across designs.
    old=list(csv.DictReader((CACHE/'cases.csv').open()))
    weather=[r for r in old if r['simulation_index']=='0']
    assert len(weather)==500
    cases=[]
    for i,r in enumerate(weather):cases.append(dict(r,case_id=f'mc_3_{i:04}',simulation_index='3'))
    audit={}
    for key,label,color,source in DESIGNS:
        out=OUTPUT/key;out.mkdir(exist_ok=True)
        root,info=inspect_design(source)
        assert info['simulation_index']==3 and info['simulation_extensions']==0
        shutil.copy2(source,out/source.name)
        mc.write_site_copy(source,out/(source.stem+'.URRG.ork'),root,launch)
        _,siteinfo=inspect_design(out/(source.stem+'.URRG.ork'))
        assert siteinfo['rocket_xml_sha256']==info['rocket_xml_sha256']
        info.update(label=label,key=key,color=color,launch_site=launch)
        (out/'design.json').write_text(json.dumps(info,indent=2)+'\n')
        write_csv(out/'cases.csv',cases)
        # Controls: low, median and high wind plus duplicate identical seed.
        selected=sorted(cases,key=lambda r:float(r['ground_wind_mps']))
        control=[dict(selected[j],case_id=f'control_{k}') for k,j in enumerate([0,249,499])]
        control.append(dict(control[1],case_id='control_repeat'))
        write_csv(out/'control_cases.csv',control)
        audit[key]=info
    assert mc.digest(OUTPUT/'canards/cases.csv')==mc.digest(OUTPUT/'co2/cases.csv')
    (OUTPUT/'study_inputs.json').write_text(json.dumps({'generated_date':'2026-10-18','trials_per_design':500,
        'motor':'J800T','launch_site':launch,'wind_mean_range_mps':[0,5],'wind_direction_range_deg':[0,360],
        'turbulence_intensity_range':[.05,.20],'seed':SEED,'paired_identical_weather':True,
        'weather_cases_sha256':mc.digest(OUTPUT/'canards/cases.csv'),'designs':audit,
        'earth_data_reused_from':'2026-10-16 URRG study; identical cached elevation and imagery',
        'dem_sha256':mc.digest(shared/'usgs_3dep_dem_2m.tif'),'perimeter_sha256':mc.digest(shared/'perimeter_mgrs.txt')},indent=2)+'\n')
    return launch,audit


def run_one(key,launch,controls=False,extended=True):
    info=json.loads((OUTPUT/key/'design.json').read_text());out=OUTPUT/key
    destination=out/('controls_extended' if extended else 'controls_flat') if controls else out
    destination.mkdir(exist_ok=True)
    args=SimpleNamespace(output=destination,ork=out/(Path(info['source_path']).stem+'.URRG.ork'),
        openrocket_jar=JAR,java_home=JAVA,trials=4 if controls else 500,seed=SEED,wind_speed=None,
        random_wind_max=5.,turbulence_min=.05,turbulence_max=.20,workers=1 if controls else 2,
        perimeter_mgrs=OUTPUT/'earth_data/perimeter_mgrs.txt',
        trace_dir=(destination/'traces') if extended else None,virtual_floor_depth=20)
    cases=out/('control_cases.csv' if controls else 'cases.csv')
    mc.run_engine(args,cases,destination/('runs.csv' if controls else 'extended_runs.csv'),launch)
    log='\n'.join(p.read_text() for p in destination.glob('engine_*.log'))
    assert 'CONFIG_AUDIT simulation=3 motor=J800T' in log
    assert 'event=APOGEE delay_s=1.0' in log
    print(key, 'controls' if controls else '500 Monte Carlo trajectories','complete',flush=True)


def validate_controls(key):
    out=OUTPUT/key
    flat={r['case_id']:r for r in load_rows(out/'controls_flat/runs.csv')}
    ext={r['case_id']:r for r in load_rows(out/'controls_extended/runs.csv')}
    checks=[]
    for case,r in ext.items():
        old=flat[case]
        assert r['ground_hit']==old['ground_hit']
        differences={k:abs(r[k]-old[k]) for k in ['apogee_m','apogee_time_s','deployment_time_s','rail_speed_mps'] if np.isfinite(r[k])}
        assert max(differences.values())<1e-6
        entry={'case_id':case,'completed':r['ground_hit'],'unchanged_ascent_and_deployment':differences}
        if r['ground_hit']:
            tr=np.genfromtxt(out/'controls_extended/traces'/f'{case}_sim3.csv.gz',delimiter=',',skip_header=1)
            idx=np.flatnonzero((tr[:-1,3]>0)&(tr[1:,3]<=0))[-1]
            point=tr[idx]+tr[idx,3]/(tr[idx,3]-tr[idx+1,3])*(tr[idx+1]-tr[idx])
            error=float(np.hypot(point[1]-old['east_m'],point[2]-old['north_m']))
            assert error<.5 and abs(tr[-1,3]+20)<.01
            entry['flat_plane_endpoint_interpolation_difference_m']=error
        checks.append(entry)
    for source in [flat,ext]:
        for k in source['control_1']:
            if k!='case_id':
                a,b=source['control_1'][k],source['control_repeat'][k]
                assert a==b or (isinstance(a,float) and np.isnan(a) and np.isnan(b)),(key,k,a,b)
    report={'passed':True,'repeat_seed_identical':True,'controls':checks}
    (out/'control_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def analyze_design(key,terrain,boundary):
    from matplotlib.path import Path as MplPath
    out=OUTPUT/key;info=json.loads((out/'design.json').read_text())
    rows=load_rows(out/'extended_runs.csv');assert len(rows)==500
    expected=list(csv.DictReader((out/'cases.csv').open()))
    assert [r['case_id'] for r in rows]==[r['case_id'] for r in expected]
    assert all(r['simulation_index']==3 for r in rows)
    native_log='\n'.join(p.read_text() for p in out.glob('engine_*.log'))
    assert 'Loader warnings: Messages[]' in native_log and 'automatic_cd=true event=APOGEE delay_s=1.0' in native_log
    assert 'cd=0.8' in native_log
    codes=boundary['codes']
    direct_vertices=np.array([(300000+int(c[5:10]),4700000+int(c[10:15])) for c in codes])
    independent_polygon=MplPath(np.vstack([direct_vertices,direct_vertices[0]]))
    landings=[];tracks=[];max_error=0;independent_error=0
    (out/'terrain_tracks').mkdir(exist_ok=True)
    for r in rows:
        if not r['ground_hit']:continue
        assert np.isfinite(r['deployment_time_s'])
        path=out/'traces'/f'{r["case_id"]}_sim3.csv.gz'
        tr=np.genfromtxt(path,delimiter=',',skip_header=1)
        assert np.all(np.diff(tr[:,0])>=0) and np.isfinite(tr).all()
        assert abs(tr[-1,3]+20)<.01
        hit,trimmed,error=first_contact(tr,terrain);max_error=max(max_error,error)
        lon,lat=terrain.to_lonlat.transform(hit[1],hit[2]);ux,uy=terrain.to_utm.transform(hit[1],hit[2])
        point=Point(ux,uy);inside=bool(boundary['polygon'].covers(point));clearance=point.distance(boundary['polygon'].boundary)
        assert inside==bool(independent_polygon.contains_point((ux,uy)))
        col,row=~terrain.transform*(ux,uy);col-=.5;row-=.5
        c,q=int(np.floor(col)),int(np.floor(row));fx,fy=col-c,row-q;a=terrain.data
        z=(1-fy)*((1-fx)*a[q,c]+fx*a[q,c+1])+fy*((1-fx)*a[q+1,c]+fx*a[q+1,c+1])
        independent_error=max(independent_error,abs(z-hit[3]-terrain.pad_m))
        assert hit[0]>r['deployment_time_s'] and hit[4]<0
        j=np.flatnonzero((tr[:-1,3]>0)&(tr[1:,3]<=0))[-1]
        flat=tr[j]+tr[j,3]/(tr[j,3]-tr[j+1,3])*(tr[j+1]-tr[j])
        landing=dict(r,design=key,motor='J800T',east_m=float(hit[1]),north_m=float(hit[2]),
            radius_m=float(np.hypot(hit[1],hit[2])),flight_time_s=float(hit[0]),vertical_landing_mps=float(abs(hit[4])),
            longitude_deg=lon,latitude_deg=lat,terrain_elevation_navd88_m=float(z),terrain_above_pad_m=float(hit[3]),
            inside_green_area=inside,signed_boundary_clearance_m=clearance if inside else -clearance,
            pad_plane_east_m=float(flat[1]),pad_plane_north_m=float(flat[2]),
            terrain_horizontal_shift_m=float(np.hypot(hit[1]-flat[1],hit[2]-flat[2])))
        landings.append(landing);tracks.append(trimmed)
        with gzip.open(out/'terrain_tracks'/f'{r["case_id"]}_sim3.csv.gz','wt') as f:
            np.savetxt(f,trimmed,delimiter=',',header='time_s,east_m,north_m,height_above_pad_m,vertical_velocity_mps',comments='',fmt='%.9f')
    if not landings:raise ValueError(f'{key}: no completed landings; inspect excluded runs')
    assert max_error<1e-6 and independent_error<1e-6
    write_csv(out/'terrain_landings.csv',landings)
    incomplete=[r for r in rows if not r['ground_hit']]
    if incomplete:write_csv(out/'excluded_runs.csv',incomplete)
    inside=sum(r['inside_green_area'] for r in landings)
    s=dict(design=info,launch_site=info['launch_site'],attempted=500,completed=len(landings),excluded_incomplete=len(incomplete),
        excluded_reasons=sorted({r['warnings'] for r in incomplete}),inside=inside,outside=len(landings)-inside,
        inside_percent=100*inside/len(landings),denominator='Completed flights with main deployment only; incomplete/tumble aborts excluded.',
        main_cd_resolved_by_engine=.8,terrain_pad_elevation_navd88_m=terrain.pad_m,
        weather='Mean wind uniform 0–5 m/s, direction uniform 0–360°, turbulence intensity uniform 5–20%; seed 20261011, 500 paired strata.',
        uncertainty_scope='Native pink-noise speed turbulence within each flight. Direction and mean speed fixed within flight and altitude; no control actuation, wind shear, mass/Cd or chute-inflation uncertainty.',
        terrain_method='First post-apogee intersection of piecewise-linear native trajectory with bilinear USGS 3DEP DEM; paths extended below pad plane.',
        terrain_dem_resolution_m=2,terrain_datum='NAVD88',vertical_exaggeration=1,
        landings_within_1m_of_boundary=sum(abs(r['signed_boundary_clearance_m'])<=1 for r in landings))
    for metric in ['radius_m','apogee_m','vertical_landing_mps','flight_time_s','launch_mass_kg','landing_mass_kg','rail_speed_mps','terrain_elevation_navd88_m','terrain_horizontal_shift_m']:
        s[metric]=mc.stats([r[metric] for r in landings])
    s['apogee_to_landing_s']=mc.stats([r['flight_time_s']-r['apogee_time_s'] for r in landings])
    validation={'passed':True,'attempts':len(rows),'completed_intersections':len(landings),'max_surface_residual_m':max_error,
        'max_independent_bilinear_residual_m':float(independent_error),'independent_mgrs_polygon_agrees':True,
        'all_contacts_after_main_deployment':True,'all_trials_use_simulation_index':3,
        'native_engine_motor':'J800T','native_main_diameter_m':.6096,'native_main_cd':.8,
        'native_main_deployment':'APOGEE + 1 s','source_rocket_preserved':True,
        'controls':json.loads((out/'control_validation.json').read_text())}
    (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
    features=[{'type':'Feature','properties':{'name':'Supplied URRG green area'},'geometry':mapping(Polygon(boundary['lonlat']))}]
    for r in landings:
        features.append({'type':'Feature','properties':{k:r[k] for k in ['case_id','design','motor','radius_m','inside_green_area','terrain_elevation_navd88_m']},
            'geometry':{'type':'Point','coordinates':[r['longitude_deg'],r['latitude_deg']]}})
    (out/'terrain_landings.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features})+'\n')
    print(key,':',len(landings),'completed;',inside,'inside; 95% radius',s['radius_m']['p95'],flush=True)
    return s,landings,tracks,rows


def texture_data():
    with rasterio.open(OUTPUT/'earth_data/satellite_local.tif') as ds:
        a=np.moveaxis(ds.read(),0,-1);b=ds.bounds;t=ds.transform
    return a,(b.left,b.right,b.bottom,b.top),t


def make_satellite(s,landings,boundary,texture,limit,perimeter=False):
    info=s['design'];color=info['color'];out=OUTPUT/info['key'];rgb,extent,_=texture
    fig,ax=plt.subplots(figsize=(10,10.8),facecolor='#f7f9fb')
    fig.subplots_adjust(left=.09,right=.97,bottom=.17,top=.84)
    ax.imshow(rgb,extent=extent,zorder=0)
    p95=s['radius_m']['p95']
    if perimeter:
        local=boundary['local'];ring=np.vstack([local,local[0]])
        ax.add_patch(PlotPolygon(local,closed=True,facecolor='#4cdf71',edgecolor='none',alpha=.15,zorder=1))
        ax.plot(ring[:,0],ring[:,1],c='#52f47e',lw=1.8,label='Supplied green-area boundary',zorder=2)
    ax.add_patch(Circle((0,0),p95,fill=False,edgecolor=color,lw=2,ls='--',label=f'J800T · conditional 95% radius {p95:.0f} m',zorder=3))
    ax.scatter([r['east_m'] for r in landings],[r['north_m'] for r in landings],s=19,c=color,alpha=.9,
               edgecolors='#193344',linewidths=.3,zorder=4,label='Individual terrain-corrected landings')
    if perimeter:
        outside=[r for r in landings if not r['inside_green_area']]
        if outside:ax.scatter([r['east_m'] for r in outside],[r['north_m'] for r in outside],marker='x',s=32,c='#ff4d50',lw=1.3,label='Outside green area',zorder=5)
    ax.scatter([0],[0],marker='+',s=240,c='white',lw=3,zorder=6,label='URRG launch point')
    ax.set(xlim=(-limit,limit),ylim=(-limit,limit),aspect='equal',xlabel='East of launch (m)',ylabel='North of launch (m)')
    ax.legend(loc='upper right',fontsize=8.5,facecolor='#172e42',labelcolor='white',framealpha=.96)
    ax.text(.025,.98,'N ↑',transform=ax.transAxes,va='top',fontsize=16,color='white',bbox=dict(facecolor='#172e42',alpha=.85,edgecolor='none'))
    fig.suptitle(f'{info["label"]} · J800T\nSimulated landings on satellite imagery',fontsize=19,fontweight='bold',y=.965,color='#173247')
    fig.text(.5,.875,'Mean wind 0–5 m/s · direction 0–360° · turbulence 5–20%',ha='center',fontsize=11)
    fig.text(.5,.098,f'Inside green area: {s["inside"]}/{s["completed"]} ({s["inside_percent"]:.1f}%) · {s["excluded_incomplete"]} incomplete runs excluded from 500 attempts',ha='center',fontsize=10)
    fig.text(.5,.07,'File defaults: 0.610 m main at apogee + 1 s · 1 m rail · no drogue',ha='center',fontsize=10)
    fig.text(.5,.044,'Landing statistics use completed flights only. Assumed wind scenarios; no forecast.',ha='center',fontsize=9)
    fig.text(.5,.02,'Imagery: Esri, Maxar, Earthstar Geographics and GIS community · Terrain: USGS 3DEP / NAVD88',ha='center',fontsize=8,color='#536a7a')
    fig.savefig(out/('landing_perimeter.png' if perimeter else 'landing_satellite.png'),dpi=190);plt.close(fig)


def ground_mesh(terrain,boundary,texture,limit):
    rgb,_,trans=texture;axis=np.linspace(-limit,limit,int(2*limit/10)+1);x,y=np.meshgrid(axis,axis)
    z=terrain.sample(x,y)-terrain.pad_m;c,r=~trans*(x,y);c-=.5;r-=.5
    colors=np.stack([map_coordinates(rgb[:,:,i].astype(float),[r,c],order=1,mode='nearest') for i in range(3)],axis=-1)/255
    mask=contains_xy(Polygon(boundary['local']),x,y);colors[mask]=.88*colors[mask]+.12*np.array([.2,.9,.35])
    intersection=Polygon(boundary['local']).boundary.intersection(box(-limit,-limit,limit,limit))
    segments=list(intersection.geoms) if hasattr(intersection,'geoms') else [intersection]
    perimeter=[]
    for seg in segments:
        xy=np.array(seg.coords)
        if len(xy):perimeter.append(np.column_stack([xy,terrain.sample(xy[:,0],xy[:,1])-terrain.pad_m]))
    return x,y,z,colors,perimeter


def add_3d(ax,s,landings,tracks,mesh,limit,top):
    x,y,z,colors,perimeter=mesh;color=s['design']['color']
    ax.plot_surface(x,y,z,facecolors=colors,rcount=len(x),ccount=len(x),linewidth=0,antialiased=False,shade=False,zorder=0)
    ax.add_collection3d(Line3DCollection([thin_track(t) for t in tracks],colors=color,linewidths=.5,alpha=.20,zorder=2))
    for p in perimeter:ax.plot(*p.T,c='#29e967',lw=1.6,zorder=3)
    for inside in (True,False):
        points=[r for r in landings if r['inside_green_area']==inside]
        if points:ax.scatter([r['east_m'] for r in points],[r['north_m'] for r in points],[r['terrain_above_pad_m'] for r in points],
            c=color if inside else '#ff4d50',s=13 if inside else 28,marker='o' if inside else 'x',linewidths=.3,
            edgecolors='#1e3446' if inside else None,depthshade=False,zorder=4)
    ax.scatter([0],[0],[0],s=120,marker='*',c='white',edgecolors='#173247',zorder=5)
    ax.set(xlim=(-limit,limit),ylim=(-limit,limit),zlim=(-30,top),xlabel='East of launch (m)',ylabel='North of launch (m)',zlabel='Height above pad (m)')
    ax.set_box_aspect((2*limit,2*limit,top+30));ax.view_init(elev=26,azim=-60)
    ax.set_xticks([-.75*limit,0,.75*limit]);ax.set_yticks([-.75*limit,0,.75*limit]);ax.set_zticks(np.arange(0,top+1,200));ax.tick_params(labelsize=9)
    ax.set_facecolor('#f7f9fb')


def make_3d(s,landings,tracks,mesh,limit,top):
    fig=plt.figure(figsize=(10.8,10.8),facecolor='#f7f9fb');ax=fig.add_subplot(111,projection='3d',computed_zorder=False)
    fig.subplots_adjust(left=.015,right=.94,bottom=.13,top=.82)
    add_3d(ax,s,landings,tracks,mesh,limit,top)
    fig.suptitle(f'{s["design"]["label"]} · J800T\nFlight paths meet the real terrain',fontsize=21,fontweight='bold',y=.97,color='#173247')
    fig.text(.5,.867,f'{s["completed"]} completed tracks · {s["inside_percent"]:.1f}% inside the green area',ha='center',fontsize=15)
    fig.text(.5,.075,'True vertical scale (1×) · every completed track stops at its first descending ground intersection',ha='center',fontsize=10)
    fig.text(.5,.05,f'White star: launch pad · green line: boundary · {s["excluded_incomplete"]} incomplete runs excluded',ha='center',fontsize=10)
    fig.text(.5,.025,'Imagery: Esri World Imagery · Terrain: USGS 3DEP, 2 m DEM / NAVD88 · 10 m display mesh',ha='center',fontsize=9,color='#536a7a')
    fig.savefig(OUTPUT/s['design']['key']/'tracks_3d.png',dpi=190);plt.close(fig)


def make_interactive(s,landings,tracks,mesh,limit,top):
    import plotly.graph_objects as go
    x,y,z,colors,perimeter=mesh;n,m=x.shape;ids=np.arange(n*m).reshape(n,m)
    a,b,c,d=(ids[:-1,:-1].ravel(),ids[:-1,1:].ravel(),ids[1:,:-1].ravel(),ids[1:,1:].ravel())
    fig=go.Figure(go.Mesh3d(x=x.ravel(),y=y.ravel(),z=z.ravel(),i=np.r_[a,b],j=np.r_[b,d],k=np.r_[c,c],
        vertexcolor=['rgb(%d,%d,%d)'%tuple(v) for v in (colors.reshape(-1,3)*255).astype(int)],
        lighting=dict(ambient=1,diffuse=0,specular=0),name='Terrain + imagery',hoverinfo='skip',showlegend=True))
    path=np.vstack([np.vstack([thin_track(t),[np.nan]*3]) for t in tracks])
    fig.add_trace(go.Scatter3d(x=path[:,0],y=path[:,1],z=path[:,2],mode='lines',line=dict(color=s['design']['color'],width=1.6),opacity=.3,name='Completed flight paths',hoverinfo='skip'))
    for inside in (True,False):
        g=[r for r in landings if r['inside_green_area']==inside]
        if not g:continue
        fig.add_trace(go.Scatter3d(x=[r['east_m'] for r in g],y=[r['north_m'] for r in g],z=[r['terrain_above_pad_m'] for r in g],mode='markers',
            marker=dict(size=4 if inside else 6,color=s['design']['color'] if inside else '#ff4d50',symbol='circle' if inside else 'x',line=dict(width=.5,color='#173247')),
            name='Inside green area' if inside else 'Outside green area',
            customdata=[[r['case_id'],r['terrain_elevation_navd88_m'],r['ground_wind_mps'],r['wind_from_deg'],r['radius_m']] for r in g],
            hovertemplate='%{customdata[0]}<br>Radius %{customdata[4]:.1f} m<br>Terrain %{customdata[1]:.2f} m NAVD88<br>Mean wind %{customdata[2]:.2f} m/s from %{customdata[3]:.0f}°<extra>%{fullData.name}</extra>'))
    for i,p in enumerate(perimeter):fig.add_trace(go.Scatter3d(x=p[:,0],y=p[:,1],z=p[:,2],mode='lines',line=dict(color='#39f577',width=4),name='Green-area boundary',showlegend=i==0,hoverinfo='skip'))
    fig.add_trace(go.Scatter3d(x=[0],y=[0],z=[0],mode='markers',marker=dict(color='white',size=8,line=dict(width=2,color='#173247')),name='Launch pad'))
    fig.update_layout(template='plotly_white',height=850,margin=dict(l=0,r=0,t=10,b=0),
        scene=dict(xaxis=dict(title='East (m)',range=[-limit,limit]),yaxis=dict(title='North (m)',range=[-limit,limit]),
        zaxis=dict(title='Height above pad (m)',range=[-30,top]),aspectmode='data',camera=dict(eye=dict(x=1.35,y=-1.7,z=1.1))),
        legend=dict(x=.01,y=.98,bgcolor='rgba(255,255,255,.9)'))
    chart=fig.to_html(full_html=False,include_plotlyjs=True,config={'displaylogo':False,'responsive':True})
    text=f'''<!doctype html><html><head><meta charset="utf-8"><title>{s['design']['label']} · J800T 3D</title><style>body{{background:#f7f9fb;color:#173247;font:16px system-ui;margin:0}}header,footer{{max-width:1150px;padding:20px;margin:auto}}p{{line-height:1.6}}a{{color:#14758b}}</style></head><body><header><h1>{s['design']['label']} · J800T</h1><p><b>{s['inside']}/{s['completed']} completed flights inside the green area ({s['inside_percent']:.1f}%).</b> {s['excluded_incomplete']} incomplete trials excluded out of 500 attempts.</p><p>Drag to rotate, scroll to zoom; click legend items to hide or show paths. True vertical scale, 1×.</p></header>{chart}<footer><p>Native trajectories stop at their first descending intersection with the USGS 3DEP terrain (2 m DEM; 10 m mesh for display). The ground plane was extended 20 m below the pad to include lower-lying landings.</p><p>Same paired weather: mean wind 0–5 m/s, direction 0–360°, turbulence 5–20%. Native speed turbulence; no within-flight direction changes or vertical shear. No active-control extension is present. File settings: 0.6096 m main, automatic Cd = 0.8, main at apogee + 1 s, 1 m vertical rail. Assumed scenarios, not a weather forecast.</p><p>Launch: 18TUN2061530290 from telemetry UI. Imagery: Esri, Maxar, Earthstar Geographics and GIS community. Terrain: USGS 3DEP / NAVD88, cached 2026-10-16. Bare-earth terrain excludes crops and structures.</p><p><a href="landing_satellite.png">Satellite map</a> · <a href="tracks_3d.png">3D snapshot</a> · <a href="terrain_landings.csv">Landing data</a> · <a href="../index.html">Both designs</a></p></footer></body></html>'''
    (OUTPUT/s['design']['key']/'tracks_3d.html').write_text(text)


def diagnostics(results,launch):
    from recovery_plots import plot_randomized
    out=OUTPUT/'diagnostics';out.mkdir(exist_ok=True);configs=[];combined=[]
    for i,(s,g,t,raw) in enumerate(results):
        lookup={r['case_id']:r for r in g}
        combined.extend(dict(lookup.get(r['case_id'],r),simulation_index=i) for r in raw)
        configs.append({'index':i,'motor':('Canards' if i==0 else 'CO₂')+' · J800T','default_motor':False,
            'complete_trials':s['completed'],'incomplete_trials':s['excluded_incomplete'],'radius_m':s['radius_m']})
    args=SimpleNamespace(output=out,random_wind_max=5.,turbulence_min=.05,turbulence_max=.20,basemap=False,
        landing_surface_description='Terrain-corrected contacts · both designs use their saved 0.610 m main and J800T configuration.')
    plot_randomized(args,{'configs':configs,'launch_site':launch},combined)


def analyze_and_plot():
    study=json.loads((OUTPUT/'study_inputs.json').read_text());launch=study['launch_site']
    boundary=load_perimeter(OUTPUT/'earth_data/perimeter_mgrs.txt',launch)
    terrain=Terrain(OUTPUT/'earth_data/usgs_3dep_dem_2m.tif',boundary['crs']);texture=texture_data()
    results=[analyze_design(key,terrain,boundary) for key,*_ in DESIGNS]
    limit=max(300,50*np.ceil(1.18*max(s['radius_m']['max'] for s,*_ in results)/50))
    limit3d=max(400,100*np.ceil(1.2*max(s['radius_m']['max'] for s,*_ in results)/100))
    top=100*np.ceil(1.07*max(s['apogee_m']['max'] for s,*_ in results)/100)
    mesh=ground_mesh(terrain,boundary,texture,limit3d)
    for s,g,t,raw in results:
        make_satellite(s,g,boundary,texture,limit)
        make_satellite(s,g,boundary,texture,max(300,limit),perimeter=True)
        make_3d(s,g,t,mesh,limit3d,top)
        make_interactive(s,g,t,mesh,limit3d,top)
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
    diagnostics(results,launch)
    report={'generated_date':'2026-10-18','inputs':study,'perimeter':boundary['metadata'],
        'comparison':[{k:s[k] for k in ['design','attempted','completed','excluded_incomplete','inside','outside','inside_percent','radius_m','apogee_m','vertical_landing_mps','terrain_horizontal_shift_m']} for s,*_ in results],
        'map_half_width_m':float(limit),'scene_half_width_m':float(limit3d),'scene_top_m':float(top)}
    (OUTPUT/'comparison_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    package(results,report)


def package(results,report):
    lines=['URRG · Balius J800T Monte Carlo · 2026-10-18','',
        '500 paired weather trials for each supplied ORK, J800T only. Telemetry UI URRG pad: 18TUN2061530290.',
        'Mean wind uniform 0–5 m/s; direction uniform 0–360°; turbulence intensity uniform 5–20%.',
        'Same 500 Latin-hypercube weather draws and seeds as the previous study. Native pink-noise speed variation; direction and mean fixed within each flight and with altitude. Instantaneous gusts can exceed the mean-speed cap.',
        'Both files: main diameter 0.6096 m, automatic Cd resolves to 0.8, configuration-specific deployment at apogee + 1 s, vertical 1 m rail, ISA atmosphere. No drogue.',
        'Descriptive J800T simulation index 3 selected in each file; its conditions match the generic J800T simulation index 2. I500T and J570W configurations are not run.',
        'No active-control extension is present in these ORKs; canards and CO2 components contribute as stored geometry/mass. No unprovided control law or actuation is assumed.','']
    for s,*_ in results:
        lines.extend([s['design']['label'],f"Inside / completed: {s['inside']}/{s['completed']} = {s['inside_percent']:.2f}%; {s['outside']} outside; {s['excluded_incomplete']} incomplete excluded from 500 attempts.",
            f"Horizontal radius: median {s['radius_m']['median']:.1f} m; central 95% {s['radius_m']['p2_5']:.1f}–{s['radius_m']['p97_5']:.1f} m; conditional 95th-percentile radius {s['radius_m']['p95']:.1f} m; maximum {s['radius_m']['max']:.1f} m.",
            f"Median apogee {s['apogee_m']['median']:.1f} m above pad; vertical touchdown speed {s['vertical_landing_mps']['median']:.2f} m/s.",
            f"Largest horizontal terrain correction versus the track's pad-plane crossing: {s['terrain_horizontal_shift_m']['max']:.3f} m.",''])
    lines.extend(['Terrain and validation:',
        'Full native trajectories continue to a numerical floor 20 m below the pad. The origin shift occurs below 30 m during main descent without changing physical altitude or velocity. Paired flat/extended controls preserve ascent, rail exit and deployment timing; repeated seeds produce identical outputs.',
        'Each completed trajectory stops at its first descending intersection with a bilinear USGS 3DEP DEM exported at 2 m. All native track samples are used; the 3D display alone is thinned to about 100 points per trajectory and a 10 m terrain mesh. Vertical exaggeration is 1.',
        'USGS source at pad: NY_FingerLakes_2020_A20 1 m survey; vertical datum NAVD88. Cached DEM and Esri World Imagery from the previous 2026-10-16 run are reused for a consistent comparison.',
        'Boundary: ordered 1000-point MGRS perimeter, closed last-to-first; no convex hull. Containment was also checked using independently decoded MGRS digits and a separate point-in-polygon implementation. Bilinear elevation roots checked independently.',
        'Percentages and landing ranges are conditional on simulations finishing with main deployment; excluded tumble aborts have no modelled landing point. These are assumed numerical scenarios, not a measured launch-day probability. Bare-earth elevation does not include crops, trees or structures; model and terrain uncertainty are not sampled.',
        '','Artifacts:',
        'Each design folder contains its satellite landing plot, green-area map, 3D snapshot, standalone interactive 3D HTML, raw inputs and outputs, terrain-corrected CSV/GeoJSON and validation.',
        'The diagnostics folder contains the comparative Monte Carlo distributions, wind inputs, completion and flight metrics. The compact ZIP includes figures, HTML, tables, ORKs, validation and source code; full tracks and cached earth rasters remain in the workspace output folder.',
        'extended_runs.csv contains virtual-floor endpoints; use terrain_landings.csv for actual terrain landing positions.',
        '','Sources:',
        'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer',
        'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
        'Imagery credit: Esri, Maxar, Earthstar Geographics and GIS community. Elevation: USGS 3DEP.',
        '','Reproduction: use the hash-matched MIT engine and recorded Python dependencies. Run balius_recovery_study.py --stage all. Source inputs are the untouched ORKs, copied with hashes; site copies change location and clear cached results only.'])
    (OUTPUT/'results.txt').write_text('\n'.join(lines)+'\n')
    cells=''.join(f'<tr><td>{s["design"]["label"]}</td><td>{s["completed"]}/500</td><td>{s["radius_m"]["p95"]:.1f} m</td><td>{s["inside"]}/{s["completed"]} ({s["inside_percent"]:.1f}%)</td><td>{s["excluded_incomplete"]}</td></tr>' for s,*_ in results)
    sections=''
    for s,*_ in results:
        k=s['design']['key'];sections+=f'<section><h2>{s["design"]["label"]} · J800T</h2><p><a href="{k}/tracks_3d.html">Rotate interactive 3D</a> · <a href="{k}/terrain_landings.csv">Landing coordinates</a> · <a href="{k}/summary.json">Summary</a></p><img src="{k}/landing_satellite.png" alt="Satellite landings"><img src="{k}/tracks_3d.png" alt="3D flight paths"><img src="{k}/landing_perimeter.png" alt="Green-area containment"></section>'
    sections+='<section><h2>Comparison</h2><img src="comparison_3d.png" alt="3D comparison"></section>'
    for p in sorted((OUTPUT/'diagnostics').glob('*.png')):sections+=f'<section><h2>{p.stem.replace("_"," ").title()}</h2><img src="diagnostics/{p.name}" alt="{p.stem}"></section>'
    page='''<!doctype html><html><head><meta charset="utf-8"><title>Balius J800T · URRG recovery</title><style>body{max-width:1150px;margin:30px auto;padding:0 24px;background:#f7f9fb;color:#173247;font:16px system-ui}p{line-height:1.6}table{border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #cadbe7}section{background:white;border-radius:12px;margin:30px 0;padding:20px}img{width:100%;height:auto}a{color:#176b83}</style></head><body><h1>Balius CDR · J800T at URRG</h1><p>500 trials per design using identical randomized weather: mean wind 0–5 m/s, direction 0–360°, turbulence intensity 5–20%. Source settings retained: 0.610 m main at apogee + 1 s, 1 m vertical rail, no drogue. No active-control extension is present in either ORK.</p><table><tr><th>Design</th><th>Finished</th><th>95% radius</th><th>Inside / finished</th><th>Excluded</th></tr>'''+cells+'''</table><p>Terrain-corrected first ground contacts. All percentages and radii use completed simulations only. <a href="results.txt">Methods, results and limitations</a>.</p>'''+sections+'</body></html>'
    (OUTPUT/'index.html').write_text(page)
    manifest={'script_sha256':mc.digest(Path(__file__)),'java_runner_sha256':mc.digest(HERE/'RecoveryBatch.java'),
        'intersection_source_sha256':mc.digest(HERE/'recovery_terrain.py'),'engine_jar_sha256':mc.digest(JAR),
        'image_count':len(list(OUTPUT.rglob('*.png'))),'descriptive_source_unchanged':all(mc.digest(src)==json.loads((OUTPUT/k/'design.json').read_text())['source_sha256'] for k,_,_,src in DESIGNS)}
    (OUTPUT/'deliverable_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=HERE/'URRG_Balius_J800_20261018_results.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in OUTPUT.rglob('*'):
            if not p.is_file() or any(q in ['traces','terrain_tracks','earth_data'] for q in p.relative_to(OUTPUT).parts):continue
            if p.suffix not in ['.png','.html','.csv','.json','.txt','.ork','.geojson']:continue
            z.write(p,p.relative_to(OUTPUT))
        for name in ['balius_recovery_study.py','RecoveryBatch.java','montecarlo_recovery.py','recovery_terrain.py','recovery_perimeter.py','recovery_plots.py','requirements-recovery.txt']:
            z.write(HERE/name,'source/'+name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print('All plots and bundle ready:',archive,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['prepare','controls','run','analyze','all'],default='all');args=p.parse_args()
    if args.stage in ['prepare','all']:launch,audit=prepare()
    else:launch=json.loads((OUTPUT/'study_inputs.json').read_text())['launch_site']
    if args.stage in ['controls','all']:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in [pool.submit(run_one,key,launch,True,False) for key,*_ in DESIGNS]:f.result()
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in [pool.submit(run_one,key,launch,True,True) for key,*_ in DESIGNS]:f.result()
        for key,*_ in DESIGNS:validate_controls(key)
    if args.stage in ['run','all']:
        for key,*_ in DESIGNS:assert json.loads((OUTPUT/key/'control_validation.json').read_text())['passed']
        with ThreadPoolExecutor(max_workers=2) as pool:
            for f in [pool.submit(run_one,key,launch) for key,*_ in DESIGNS]:f.result()
    if args.stage in ['analyze','all']:analyze_and_plot()

if __name__=='__main__':main()
