"""Intersect native OpenRocket tracks with USGS 3DEP and render georeferenced maps.

Run after RecoveryBatch exports full tracks with a virtual floor below the DEM.
No flight coordinates are jittered, rotated or simply draped onto the ground.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
from scipy.ndimage import map_coordinates
from scipy.optimize import brentq
from pyproj import Transformer
from shapely.geometry import Point, Polygon, box, mapping
from shapely import contains_xy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon as PlotPolygon, Circle
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Line3DCollection

from recovery_perimeter import load_perimeter
from montecarlo_recovery import digest, json_finite, stats

DEM_SOURCE = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer'
COLORS = ['#3dded6', '#ffbf50']
MOTORS = ['HP-I500T', 'J570W']


class Terrain:
    """Bilinear DEM samples in local true east/north metres, with strict bounds."""
    def __init__(self, path, local_crs):
        with rasterio.open(path) as ds:
            self.data = ds.read(1).astype(float)
            self.transform, self.crs, self.bounds = ds.transform, ds.crs, ds.bounds
            self.nodata = ds.nodata
        self.to_utm = Transformer.from_crs(local_crs, self.crs, always_xy=True)
        self.to_lonlat = Transformer.from_crs(local_crs, 4326, always_xy=True)
        self.pad_m = float(self.sample(0., 0.))

    def sample(self, east, north):
        x, y = self.to_utm.transform(east, north)
        col, row = ~self.transform * (np.asarray(x), np.asarray(y))
        col, row = np.asarray(col)-.5, np.asarray(row)-.5
        if np.any((col<0)|(row<0)|(col>self.data.shape[1]-1)|(row>self.data.shape[0]-1)):
            raise ValueError('A terrain query is outside the DEM; expand the source raster.')
        z = map_coordinates(self.data, [row.ravel(), col.ravel()], order=1, mode='nearest').reshape(col.shape)
        if not np.all(np.isfinite(z)) or (self.nodata is not None and np.any(z == self.nodata)):
            raise ValueError('Missing elevation data at a trajectory point.')
        return z


def load_rows(path):
    rows = list(csv.DictReader(Path(path).open()))
    for r in rows:
        for k in r.keys()-{'case_id','ground_hit','warnings'}:
            r[k] = float(r[k])
        r['ground_hit'] = r['ground_hit'].lower() == 'true'
    return rows


def first_contact(track, terrain):
    """First post-apogee contact along the piecewise-linear native trajectory.

    Subdivide steps to <=0.5 m horizontal / <=0.125 s, then solve the first
    positive-to-nonpositive clearance bracket against bilinear DEM elevations.
    """
    start = int(np.argmax(track[:,3]))
    tail = track[start:]
    delta = np.diff(tail,axis=0)
    n = np.maximum(1,np.maximum(np.ceil(np.hypot(delta[:,1],delta[:,2])/.5),
                               np.ceil(delta[:,0]/.125))).astype(int)
    dense = np.concatenate([a+np.arange(count)[:,None]/count*d
                            for a,d,count in zip(tail[:-1],delta,n)]+[tail[-1:]])
    clearance = dense[:,3]+terrain.pad_m-terrain.sample(dense[:,1],dense[:,2])
    candidates = np.flatnonzero((clearance[:-1]>0)&(clearance[1:]<=0))
    if not len(candidates):
        raise ValueError('No descending terrain intersection; extend virtual floor or inspect trace.')
    i = candidates[0]
    a,d = dense[i],dense[i+1]-dense[i]
    def residual(f):
        p=a+f*d
        return float(p[3]+terrain.pad_m-terrain.sample(p[1],p[2]))
    fraction=brentq(residual,0,1,xtol=1e-12)
    hit=a+fraction*d
    trimmed=np.vstack([track[track[:,0]<hit[0]],hit])
    return hit,trimmed,abs(residual(fraction))


def analyze(out, flat):
    previous=json.loads((flat/'summary.json').read_text())
    launch=previous['launch_site']
    boundary=load_perimeter(out/'perimeter_mgrs.txt',launch)
    terrain=Terrain(out/'usgs_3dep_dem_2m.tif',boundary['crs'])
    old={(r['case_id'],int(r['simulation_index'])):r for r in load_rows(flat/'runs.csv')}
    rows=load_rows(out/'extended_runs.csv')
    groups=[[],[]]; tracks=[[],[]]; max_residual=0.; plane_errors=[]; ascent_errors=[]
    (out/'terrain_tracks').mkdir(exist_ok=True)
    for r in rows:
        i=int(r['simulation_index']);key=(r['case_id'],i);ref=old[key]
        assert r['ground_hit']==ref['ground_hit'], ('Changed completion',key)
        for k in ['apogee_m','apogee_time_s','rail_speed_mps','deployment_time_s']:
            if np.isfinite(r[k]) and np.isfinite(ref[k]):ascent_errors.append(abs(r[k]-ref[k]))
        if not r['ground_hit']:
            continue
        assert np.isfinite(r['deployment_time_s'])
        track=np.genfromtxt(out/'traces'/f'{r["case_id"]}_sim{i}.csv.gz',delimiter=',',skip_header=1)
        assert np.all(np.diff(track[:,0])>=0) and np.isfinite(track).all()
        assert track[-1,3] < -19.99
        hit,trimmed,residual=first_contact(track,terrain)
        max_residual=max(max_residual,residual)
        # Check the extended simulator against the original flat-ground result.
        idx=np.flatnonzero((track[:-1,3]>0)&(track[1:,3]<=0))[-1]
        p=track[idx]+track[idx,3]/(track[idx,3]-track[idx+1,3])*(track[idx+1]-track[idx])
        plane_errors.append(np.hypot(p[1]-ref['east_m'],p[2]-ref['north_m']))
        lon,lat=terrain.to_lonlat.transform(hit[1],hit[2])
        point=Point(terrain.to_utm.transform(hit[1],hit[2]))
        inside=bool(boundary['polygon'].covers(point))
        oldinside=bool(boundary['polygon'].covers(Point(terrain.to_utm.transform(ref['east_m'],ref['north_m']))))
        distance=point.distance(boundary['polygon'].boundary)
        result=dict(r, motor=MOTORS[i], east_m=float(hit[1]),north_m=float(hit[2]),
                    radius_m=float(np.hypot(hit[1],hit[2])),flight_time_s=float(hit[0]),
                    vertical_landing_mps=float(abs(hit[4])),longitude_deg=lon,latitude_deg=lat,
                    terrain_elevation_navd88_m=float(terrain.sample(hit[1],hit[2])),
                    terrain_above_pad_m=float(hit[3]),inside_green_area=inside,
                    signed_boundary_clearance_m=distance if inside else -distance,
                    flat_east_m=ref['east_m'],flat_north_m=ref['north_m'],
                    flat_inside_green_area=oldinside,
                    landing_shift_m=float(np.hypot(hit[1]-ref['east_m'],hit[2]-ref['north_m'])),
                    landing_time_change_s=float(hit[0]-ref['flight_time_s']),
                    flat_plane_interpolation_difference_m=float(plane_errors[-1]))
        groups[i].append(result);tracks[i].append(trimmed)
        with gzip.open(out/'terrain_tracks'/f'{r["case_id"]}_sim{i}.csv.gz','wt') as f:
            np.savetxt(f,trimmed,delimiter=',',header='time_s,east_m,north_m,height_above_pad_m,vertical_velocity_mps',comments='',fmt='%.9f')
    allrows=sum(groups,[])
    with (out/'terrain_landings.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(allrows[0]));writer.writeheader();writer.writerows(allrows)
    configs=[]
    for i,g in enumerate(groups):
        complete=len(g);inside=sum(r['inside_green_area'] for r in g)
        configs.append(dict(motor=MOTORS[i],default_motor=i==1,attempted=500,completed=complete,
                            excluded_tumble_aborts=500-complete,inside=inside,outside=complete-inside,
                            inside_percent=100*inside/complete,
                            changed_classification=sum(r['inside_green_area']!=r['flat_inside_green_area'] for r in g),
                            radius_m=stats([r['radius_m'] for r in g]),
                            terrain_elevation_navd88_m=stats([r['terrain_elevation_navd88_m'] for r in g]),
                            horizontal_change_from_flat_m=stats([r['landing_shift_m'] for r in g]),
                            landings_within_1m_of_boundary=sum(abs(r['signed_boundary_clearance_m'])<1 for r in g)))
    report=dict(launch_site=launch,terrain_pad_elevation_navd88_m=terrain.pad_m,
                trajectory_vertical_alignment_m=terrain.pad_m-launch['elevation_m'],
                dem_source=DEM_SOURCE,dem_resolution_m=2,dem_sha256=digest(out/'usgs_3dep_dem_2m.tif'),
                source_at_pad='USGS 1 m NY_FingerLakes_2020_A20, resampled by USGS 3DEP to a 2 m grid',
                vertical_datum='NAVD88; trajectory launch aligned to the bilinear DEM pad elevation',
                intersection_method='First post-apogee zero of piecewise-linear native trajectory height minus bilinear DEM height; bracket sampling <=0.5 m horizontal and <=0.125 s, then Brent root solve.',
                numerical_ground_plane='20 m below pad; numerical origin shifted only below 30 m during main-chute descent, with physical altitude unchanged',
                denominator='Completed Monte Carlo flights with main deployment only; tumble aborts excluded.',
                weather=previous['weather_description'],uncertainty_scope=previous['uncertainty_scope'],
                recovery='No drogue; main at apogee + 1 s; 1 m vertical launch rail; preserved iteration3 model.',
                perimeter=boundary['metadata'],configs=configs,
                validation={'completed_terrain_intersections':len(allrows),'max_intersection_residual_m':max_residual,
                            'max_ascent_or_deployment_difference_from_flat':float(max(ascent_errors)),
                            'flat_plane_horizontal_interpolation_difference_m':stats(plane_errors),
                            'completion_status_identical_to_flat':True,
                            'note':'Flat-plane endpoint differences quantify interpolation and native final-step clipping, separate from terrain corrections.'})
    assert report['validation']['max_ascent_or_deployment_difference_from_flat']<1e-6
    assert max_residual<1e-6 and len(allrows)==973
    assert max(plane_errors)<.5
    (out/'terrain_summary.json').write_text(json.dumps(json_finite(report),indent=2,allow_nan=False)+'\n')
    features=[{'type':'Feature','properties':{'name':'Supplied green-area perimeter'},'geometry':mapping(Polygon(boundary['lonlat']))},
              {'type':'Feature','properties':{'name':'Telemetry launch pad'},'geometry':{'type':'Point','coordinates':[launch['longitude_deg'],launch['latitude_deg']]}}]
    for r in allrows:
        features.append({'type':'Feature','properties':{k:r[k] for k in ['case_id','motor','inside_green_area','terrain_elevation_navd88_m','landing_shift_m']},
                         'geometry':{'type':'Point','coordinates':[r['longitude_deg'],r['latitude_deg']]}})
    (out/'terrain_landings.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features})+'\n')
    print(json.dumps(report['configs'],indent=2),flush=True)
    return report,boundary,terrain,groups,tracks


def basemap(out,boundary):
    """Download actual imagery once and cache it in the same metric map CRS."""
    import contextily as ctx
    path=out/'satellite_local.tif'
    if not path.exists():
        xy=boundary['local'];low=xy.min(axis=0)-120;high=xy.max(axis=0)+120
        x0,y0=low;x1,y1=high
        to_web=Transformer.from_crs(boundary['crs'],3857,always_xy=True)
        corners=np.array([to_web.transform(x,y) for x in (x0,x1) for y in (y0,y1)])
        source=out/'satellite_webmercator.tif'
        ctx.bounds2raster(*corners.min(axis=0),*corners.max(axis=0),path=str(source),
                          zoom=17,source=ctx.providers.Esri.WorldImagery,n_connections=4)
        width,height=int(np.ceil((x1-x0)/2)),int(np.ceil((y1-y0)/2))
        transform=from_bounds(x0,y0,x1,y1,width,height)
        with rasterio.open(source) as src, rasterio.open(path,'w',driver='GTiff',width=width,height=height,
                count=3,dtype='uint8',crs=boundary['crs'],transform=transform,compress='deflate') as dst:
            for band in (1,2,3):
                reproject(rasterio.band(src,band),rasterio.band(dst,band),src_transform=src.transform,src_crs=src.crs,
                          dst_transform=transform,dst_crs=boundary['crs'],resampling=Resampling.bilinear)
        (out/'imagery_source.json').write_text(json.dumps({'provider':'Esri World Imagery','url':ctx.providers.Esri.WorldImagery.url,
            'attribution':ctx.providers.Esri.WorldImagery.attribution,'retrieved':'2026-10-16',
            'tile_zoom':17,'reprojected_crs':boundary['crs'],'image_acquisition_date':'Not determined; retrieval date is not acquisition date.'},indent=2)+'\n')
    with rasterio.open(path) as ds:
        rgb=np.moveaxis(ds.read(),0,-1);bounds=ds.bounds;transform=ds.transform
    return rgb,(bounds.left,bounds.right,bounds.bottom,bounds.top),transform


def legend_handles(motors=False):
    if motors:
        points=[Line2D([],[],marker='o',ls='',color=COLORS[i],markeredgecolor='#152738',label=MOTORS[i],markersize=6) for i in range(2)]
    else:
        points=[Line2D([],[],marker='o',ls='',color='#8dffba',markeredgecolor='#163b28',label='Inside green area',markersize=6)]
    return points+[Line2D([],[],marker='x',ls='',color='#ff6259',label='Outside green area',markersize=7),
        Line2D([],[],marker='*',ls='',color='white',markeredgecolor='#172633',label='Launch pad',markersize=12),
        Line2D([],[],color='#52f17a',label='Supplied perimeter',lw=2)]


def decorate_2d(ax,rgb,extent,boundary,groups,limits,overview=False):
    ax.imshow(rgb,extent=extent,zorder=0)
    local=boundary['local'];ring=np.vstack([local,local[0]])
    ax.add_patch(PlotPolygon(local,closed=True,color='#58ef79',alpha=.13,zorder=1))
    ax.plot(ring[:,0],ring[:,1],c='#52f17a',lw=2.2,zorder=2)
    for feet in (500,1000,2000):
        radius=feet*.3048
        ax.add_patch(Circle((0,0),radius,fill=False,ls=(0,(5,4)),lw=1,color='#51f3f4',alpha=.8,zorder=3))
        ax.text(0,radius+12,f'{feet:,} ft',color='#73ffff',ha='center',fontsize=8,
                bbox=dict(facecolor='#0e2635',alpha=.75,edgecolor='none',pad=1.5),zorder=5)
    for i,g in groups:
        for inside in (True,False):
            p=[r for r in g if r['inside_green_area']==inside]
            ax.scatter([r['east_m'] for r in p],[r['north_m'] for r in p],
                       c=(COLORS[i] if overview else '#8dffba') if inside else '#ff6259',marker='o' if inside else 'x',
                       s=(11 if overview else 15) if inside else 27,linewidths=.35 if inside else 1.3,
                       edgecolors='#173c2e' if inside else None,alpha=.9,zorder=6)
    ax.scatter([0],[0],marker='*',s=220,c='white',edgecolors='#112c3f',linewidths=1.2,zorder=9)
    ax.set(xlim=limits[:2],ylim=limits[2:],aspect='equal');ax.set_xticks([]);ax.set_yticks([])
    ax.text(.04,.95,'N ↑',transform=ax.transAxes,color='white',fontsize=15,fontweight='bold',va='top',
            bbox=dict(facecolor='#102638',alpha=.8,edgecolor='none',pad=4),zorder=10)
    x0,x1,y0,y1=limits;length=500 if overview else 200
    x=x0+.055*(x1-x0);y=y0+.045*(y1-y0)
    ax.plot([x,x+length],[y,y],c='white',lw=4,zorder=9)
    ax.text(x+length/2,y+.018*(y1-y0),f'{length} m',ha='center',color='white',fontsize=9,zorder=9,
            bbox=dict(facecolor='#102638',alpha=.75,edgecolor='none',pad=2))


def plots_2d(out,report,boundary,groups,texture):
    rgb,extent,_=texture
    fig,axes=plt.subplots(1,2,figsize=(15,9),facecolor='#f7f9fb')
    fig.subplots_adjust(top=.80,bottom=.12,left=.025,right=.975,wspace=.045)
    for i,ax in enumerate(axes):
        c=report['configs'][i]
        decorate_2d(ax,rgb,extent,boundary,[(i,groups[i])],(-700,700,-700,700))
        fig.text(.25+.5*i,.855,f'{MOTORS[i]}'+(' · default motor' if i else '')+f'\n{c["inside"]}/{c["completed"]} inside · {c["inside_percent"]:.1f}%',fontsize=17,ha='center',va='center')
        ax.legend(handles=legend_handles(),loc='lower right',fontsize=9,facecolor='#102638',labelcolor='white',framealpha=.95)
    fig.suptitle('URRG  |  Terrain-corrected landing points',fontsize=23,fontweight='bold',y=.97,color='#132f43')
    fig.text(.5,.915,'Real satellite imagery · first trajectory–terrain contact · telemetry UI launch pad',ha='center',fontsize=12,color='#345064')
    fig.text(.5,.075,'No drogue · main at apogee + 1 s · 1 m rail · mean wind 0–5 m/s · all directions · turbulence 5–20%',ha='center',fontsize=10)
    fig.text(.5,.047,'500 trials per motor. Percentages exclude 25 I500T and 2 J570W tumble aborts. Rings are centred on the launch pad.',ha='center',fontsize=10)
    fig.text(.5,.019,'Imagery: Esri, Maxar, Earthstar Geographics and GIS community  |  Elevation: USGS 3DEP, 2 m grid / NAVD88',ha='center',fontsize=8,color='#536777')
    fig.savefig(out/'terrain_landings_2d.png',dpi=180);plt.close(fig)
    local=boundary['local'];low=local.min(axis=0)-100;high=local.max(axis=0)+100
    fig,ax=plt.subplots(figsize=(11,12),facecolor='#f7f9fb');fig.subplots_adjust(top=.90,bottom=.065,left=.025,right=.975)
    decorate_2d(ax,rgb,extent,boundary,list(enumerate(groups)),(low[0],high[0],low[1],high[1]),True)
    ax.legend(handles=legend_handles(True),loc='lower right',facecolor='#102638',labelcolor='white',framealpha=.95,fontsize=10)
    fig.suptitle('URRG  |  Full recovery area',fontsize=23,fontweight='bold',y=.965,color='#132f43')
    fig.text(.5,.923,'1,000 ordered perimeter points · 4.713 km² · terrain-corrected landings',ha='center',fontsize=12)
    fig.text(.5,.035,'Launch: 18TUN2061530290  |  Imagery: Esri World Imagery  |  Elevation: USGS 3DEP',ha='center',fontsize=9)
    fig.savefig(out/'terrain_site_2d.png',dpi=170);plt.close(fig)


def scene_data(terrain,boundary,texture):
    rgb,_,transform=texture
    axis=np.linspace(-700,700,141);x,y=np.meshgrid(axis,axis)
    z=terrain.sample(x,y)-terrain.pad_m
    col,row=~transform*(x,y);col-=.5;row-=.5
    colors=np.stack([map_coordinates(rgb[:,:,i].astype(float),[row,col],order=1,mode='nearest') for i in range(3)],axis=-1)/255
    mask=contains_xy(Polygon(boundary['local']),x,y)
    colors[mask]=.87*colors[mask]+.13*np.array([.19,.9,.34])
    boundary_lines=Polygon(boundary['local']).boundary.intersection(box(-700,-700,700,700))
    lines=list(boundary_lines.geoms) if hasattr(boundary_lines,'geoms') else [boundary_lines]
    perimeter=[]
    for line in lines:
        coords=np.asarray(line.coords)
        perimeter.append(np.column_stack([coords,terrain.sample(coords[:,0],coords[:,1])-terrain.pad_m+.5]))
    return x,y,z,colors,perimeter


def thin_track(track):
    # Downsample only for display; intersection used every native simulation point.
    ids=np.unique(np.r_[np.linspace(0,len(track)-1,min(100,len(track))).astype(int),np.argmax(track[:,3]),len(track)-1])
    return track[ids,1:4]


def plots_3d(out,report,boundary,terrain,groups,tracks,texture):
    x,y,z,colors,perimeter=scene_data(terrain,boundary,texture)
    report['rendered_terrain_patch']={'east_range_m':[-700,700],'north_range_m':[-700,700],
        'min_elevation_navd88_m':float(z.min()+terrain.pad_m),'max_elevation_navd88_m':float(z.max()+terrain.pad_m),
        'relief_m':float(np.ptp(z)),'render_grid_m':10,'vertical_exaggeration':1}
    fig=plt.figure(figsize=(16,9),facecolor='#f7f9fb')
    for i in range(2):
        ax=fig.add_subplot(1,2,i+1,projection='3d',computed_zorder=False)
        ax.plot_surface(x,y,z,facecolors=colors,rcount=141,ccount=141,linewidth=0,antialiased=False,shade=False,zorder=0)
        paths=[thin_track(t) for t in tracks[i]]
        ax.add_collection3d(Line3DCollection(paths,colors=COLORS[i],linewidths=.36,alpha=.18,zorder=2))
        for p in perimeter:ax.plot(*p.T,c='#26ed6d',lw=1.8,zorder=3)
        for inside in (True,False):
            g=[r for r in groups[i] if r['inside_green_area']==inside]
            ax.scatter([r['east_m'] for r in g],[r['north_m'] for r in g],[r['terrain_above_pad_m'] for r in g],
                       c=COLORS[i] if inside else '#ff4947',s=9 if inside else 22,marker='o' if inside else 'x',
                       edgecolors='#173047' if inside else None,linewidths=.25 if inside else 1,depthshade=False,zorder=4)
        ax.scatter([0],[0],[0],c='white',s=110,marker='*',edgecolors='#132f43',zorder=5)
        ax.set(xlim=(-700,700),ylim=(-700,700),zlim=(-40,900),xlabel='East of launch (m)',ylabel='North of launch (m)',zlabel='Height above pad (m)')
        ax.set_box_aspect((1400,1400,940));ax.view_init(elev=25,azim=-60)
        ax.set_xticks([-600,0,600]);ax.set_yticks([-600,0,600]);ax.set_zticks([0,400,800]);ax.tick_params(labelsize=8)
        ax.set_facecolor('#f7f9fb');c=report['configs'][i]
        fig.text(.25+.5*i,.85,f'{MOTORS[i]} · {c["completed"]} completed tracks\n{c["inside_percent"]:.1f}% inside the green area',fontsize=15,ha='center',va='center')
    fig.suptitle('URRG  |  Flight paths meet the real terrain',fontsize=23,fontweight='bold',y=.97,color='#132f43')
    fig.text(.5,.91,'True vertical scale (1×) · trajectories stop at their first descending ground intersection',ha='center',fontsize=12,color='#345064')
    fig.text(.5,.092,'Cyan: I500T · amber: J570W · red ×: outside the perimeter · white star: telemetry launch pad',ha='center',fontsize=10)
    fig.text(.5,.057,'Native paths extended below the pad plane before intersection; aborts omitted. Ground mesh shown every 10 m; contacts use the 2 m DEM.',ha='center',fontsize=9)
    fig.text(.5,.025,'Satellite texture: Esri World Imagery  |  Terrain: USGS 3DEP / NAVD88  |  No drogue; main at apogee + 1 s',ha='center',fontsize=9,color='#536777')
    fig.subplots_adjust(left=.005,right=.995,top=.83,bottom=.12,wspace=.015)
    fig.savefig(out/'terrain_tracks_3d.png',dpi=180);plt.close(fig)
    interactive_3d(out,report,terrain,groups,tracks,(x,y,z,colors,perimeter))
    (out/'terrain_summary.json').write_text(json.dumps(json_finite(report),indent=2,allow_nan=False)+'\n')


def interactive_3d(out,report,terrain,groups,tracks,scene):
    import plotly.graph_objects as go
    x,y,z,colors,perimeter=scene;n,m=x.shape
    nodes=np.arange(n*m).reshape(n,m);a=nodes[:-1,:-1].ravel();b=nodes[:-1,1:].ravel();c=nodes[1:,:-1].ravel();d=nodes[1:,1:].ravel()
    fig=go.Figure(go.Mesh3d(x=x.ravel(),y=y.ravel(),z=z.ravel(),i=np.r_[a,b],j=np.r_[b,d],k=np.r_[c,c],
        vertexcolor=['rgb(%d,%d,%d)'%tuple(v) for v in (colors.reshape(-1,3)*255).astype(int)],
        lighting=dict(ambient=1,diffuse=0,specular=0),flatshading=False,name='USGS terrain + satellite',hoverinfo='skip',showlegend=True))
    for i in range(2):
        joined=np.vstack([np.vstack([thin_track(t),[np.nan]*3]) for t in tracks[i]])
        fig.add_trace(go.Scatter3d(x=joined[:,0],y=joined[:,1],z=joined[:,2],mode='lines',line=dict(color=COLORS[i],width=1.6),
                                 opacity=.25,name=MOTORS[i]+' paths',legendgroup=MOTORS[i],hoverinfo='skip'))
        for inside in (True,False):
            g=[r for r in groups[i] if r['inside_green_area']==inside]
            custom=np.array([[r['case_id'],r['terrain_elevation_navd88_m'],r['landing_shift_m'],r['ground_wind_mps'],r['wind_from_deg']] for r in g],dtype=object)
            fig.add_trace(go.Scatter3d(x=[r['east_m'] for r in g],y=[r['north_m'] for r in g],z=[r['terrain_above_pad_m'] for r in g],mode='markers',
                marker=dict(size=3 if inside else 5,color=COLORS[i] if inside else '#ff514b',symbol='circle' if inside else 'x',line=dict(width=.4,color='#162c42')),
                name=MOTORS[i]+(' inside' if inside else ' outside'),legendgroup=MOTORS[i],customdata=custom,
                hovertemplate='%{customdata[0]}<br>East %{x:.1f} m; north %{y:.1f} m<br>Terrain %{customdata[1]:.2f} m NAVD88<br>Shift from flat landing %{customdata[2]:.2f} m<br>Mean wind %{customdata[3]:.2f} m/s from %{customdata[4]:.0f}°<extra>%{fullData.name}</extra>'))
    for j,p in enumerate(perimeter):
        fig.add_trace(go.Scatter3d(x=p[:,0],y=p[:,1],z=p[:,2]-.5,mode='lines',line=dict(color='#3cff69',width=5),name='Green-area boundary',legendgroup='boundary',showlegend=j==0,hoverinfo='skip'))
    fig.add_trace(go.Scatter3d(x=[0],y=[0],z=[0],mode='markers',marker=dict(color='white',size=7,line=dict(color='#152b42',width=2)),name='Telemetry launch pad',hovertemplate='18TUN2061530290<br>268.60 m NAVD88<extra></extra>'))
    axis=dict(backgroundcolor='#edf2f6',gridcolor='#d7e1e8',zerolinecolor='#d7e1e8')
    fig.update_layout(template='plotly_white',height=850,margin=dict(l=0,r=0,b=0,t=35),
        scene=dict(xaxis=dict(title='East of launch (m)',range=[-700,700],**axis),yaxis=dict(title='North of launch (m)',range=[-700,700],**axis),
                   zaxis=dict(title='Height above pad (m)',range=[-40,900],**axis),aspectmode='data',camera=dict(eye=dict(x=1.6,y=-2.0,z=1.2))),
        legend=dict(bgcolor='rgba(255,255,255,0.9)',x=.01,y=.99,groupclick='toggleitem'),
        updatemenus=[dict(type='buttons',direction='right',x=.01,y=1.05,buttons=[
            dict(label='Oblique · true scale',method='relayout',args=[{'scene.camera':dict(eye=dict(x=1.6,y=-2,z=1.2))}]),
            dict(label='Top down',method='relayout',args=[{'scene.camera':dict(eye=dict(x=0,y=0,z=2.7),up=dict(x=0,y=1,z=0))}])])])
    figure=fig.to_html(full_html=False,include_plotlyjs=True,config={'displaylogo':False,'responsive':True})
    cards=''.join(f'<div class="card"><b>{c["motor"]}{" · default" if c["default_motor"] else ""}</b><strong>{c["inside_percent"]:.1f}% inside</strong><span>{c["inside"]} / {c["completed"]} completed flights · {c["excluded_tumble_aborts"]} tumble aborts excluded</span></div>' for c in report['configs'])
    html='''<!doctype html><html><head><meta charset="utf-8"><title>URRG · 3D terrain landings</title><style>body{margin:0;background:#f7f9fb;color:#173247;font:16px system-ui}header,footer{max-width:1150px;margin:24px auto;padding:0 24px}h1{margin-bottom:8px}p{line-height:1.6;color:#496475}.cards{display:flex;gap:20px}.card{flex:1;background:white;border:1px solid #dce7ef;border-radius:12px;padding:18px}.card strong{display:block;font-size:28px;margin:8px 0}.card span{font-size:14px}a{color:#146b8b}</style></head><body><header><h1>URRG · Flight paths meet the terrain</h1><p>Drag to rotate, scroll to zoom, and click legend entries to show or hide paths. Hover over landing dots for terrain elevation, wind and displacement from the old flat-plane result. Vertical scale is 1×.</p><div class="cards">'''+cards+'</div></header>'+figure+'''<footer><p>Each completed path stops at its first descending intersection with the USGS 3DEP terrain. Native trajectories extend below the pad plane; intersections use a 2 m bilinear DEM. The displayed surface uses a 10 m grid. Launch pad: 18TUN2061530290, 42.70416777° N, 77.19029502° W. Terrain elevations are NAVD88.</p><p>No drogue; main at apogee + 1 s; 1 m vertical rail. Mean wind uniform 0–5 m/s, direction uniform 0–360°, turbulence intensity uniform 5–20%. These are assumed scenarios, not a launch-day weather forecast. Instantaneous gusts can exceed 5 m/s. No within-flight direction changes or wind shear.</p><p>Imagery: Esri, Maxar, Earthstar Geographics and GIS community. Elevation: <a href="'''+DEM_SOURCE+'''">USGS 3DEP</a>; 1 m Finger Lakes 2020 source at the pad, exported onto a 2 m grid. Bare-earth terrain excludes crops, trees and structures. Model and DEM uncertainty are not included in the percentages.</p><p><a href="terrain_landings_2d.png">2D landing map</a> · <a href="terrain_site_2d.png">Full site</a> · <a href="terrain_landings.csv">Landing data</a> · <a href="terrain_summary.json">Results and validation</a></p></footer></body></html>'''
    (out/'terrain_tracks_3d.html').write_text(html)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--flat-reference',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    report,boundary,terrain,groups,tracks=analyze(out,args.flat_reference)
    texture=basemap(out,boundary)
    plots_2d(out,report,boundary,groups,texture)
    plots_3d(out,report,boundary,terrain,groups,tracks,texture)
    plot_diagnostics(out,args.flat_reference,report,groups)
    print('Terrain landings, 2D satellite maps, and static + interactive 3D complete.',flush=True)


def plot_diagnostics(out, flat, report, groups):
    """Refresh every earlier Monte Carlo graph using terrain-corrected endpoints."""
    from recovery_plots import plot_randomized
    summary=json.loads((flat/'summary.json').read_text())
    for cfg,terrain_cfg in zip(summary['configs'],report['configs']):
        cfg['radius_m']=terrain_cfg['radius_m']
    fixed={r['case_id']:r for r in sum(groups,[])}
    rows=[fixed.get(r['case_id'],r) for r in load_rows(out/'extended_runs.csv')]
    args=SimpleNamespace(output=out,random_wind_max=5.,turbulence_min=.05,turbulence_max=.20,basemap=True,
        landing_surface_description='Landing points use first contact with USGS 3DEP terrain; 2 m elevation grid.')
    plot_randomized(args,summary,rows)


if __name__=='__main__':main()
