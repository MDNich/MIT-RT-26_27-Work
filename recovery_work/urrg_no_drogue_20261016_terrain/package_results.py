"""Package the final map gallery and scientific provenance."""
from pathlib import Path
import csv,hashlib,json,shutil,zipfile
out=Path(__file__).resolve().parent
report=json.loads((out/'terrain_summary.json').read_text())
source=out.parent
manifest=json.loads((out/'run_manifest.json').read_text())
manifest['trajectory_export']['origin_shift']='Only below 30 m in main-chute descent; physical position and world altitude preserved.'
manifest['analysis_sources']={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ['RecoveryBatch.java','montecarlo_recovery.py','recovery_perimeter.py','recovery_terrain.py','recovery_plots.py','requirements-recovery.txt']}
manifest['terrain_dem_sha256']=report['dem_sha256']
manifest['flat_reference_runs_sha256']=hashlib.sha256((source/'urrg_no_drogue_20261016_perimeter/runs.csv').read_bytes()).hexdigest()
(out/'run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
lines=['URRG — terrain-intersected Monte Carlo recovery','Generated 2026-10-16','',
'Launch: telemetry UI URRG preset, 18TUN2061530290.',
'42.70416776971639 N, -77.19029501648315 E. Pad elevation 268.603 m NAVD88.',
'Preserved original-study iteration3 rocket; no drogue; main at apogee + 1 s; 1 m vertical rail.',
'500 trials per motor. Mean wind uniform 0–5 m/s, direction 0–360°, turbulence intensity 5–20%.',
'Stratified uniform inputs paired across motors; seed 20261011 onward. Native pink-noise speed turbulence.',
'Instantaneous gusts can exceed 5 m/s. No within-flight direction changes or vertical wind shear.',
'','Results (completed flights only; tumble aborts excluded):']
for c in report['configs']:
 lines.extend([f"{c['motor']}: {c['inside']}/{c['completed']} inside = {c['inside_percent']:.4f}%; {c['outside']} outside; {c['excluded_tumble_aborts']} aborts excluded.",
   f"  Median radius {c['radius_m']['median']:.2f} m; central 95% interval {c['radius_m']['p2_5']:.2f}–{c['radius_m']['p97_5']:.2f} m; 95th-percentile radius {c['radius_m']['p95']:.2f} m.",
   f"  Largest shift from the prior flat-plane landing: {c['horizontal_change_from_flat_m']['max']:.3f} m."])
lines.extend(['','Terrain method:',report['intersection_method'],
'Native simulator trajectories continue to a virtual floor 20 m below the pad. The numerical origin is shifted only below 30 m during main descent, preserving physical position, world altitude, velocity and original ascent/deployment events.',
'Every complete path is cut at its first descending terrain contact, including landings on ground below pad elevation. Contact positions are not just old endpoints draped onto terrain.',
'USGS 3DEP bare-earth DEM, 2 m export with bilinear resampling; 1 m Finger Lakes 2020 source at pad; NAVD88.',
'Trajectory launch height aligned to DEM pad elevation. Green area connects the 1000 supplied MGRS points in file order, closed last-to-first, with no convex hull or reordering.',
'Contact calculations use all native trace points and 2 m DEM samples. 3D rendering uses a 10 m ground mesh and up to 101 display points per flight. The exact contact is always retained. Vertical exaggeration = 1.',
'','Validation:',
'All 973 completed trajectories intersect the terrain; all 27 aborted trajectories are excluded.',
'Apogee, apogee time, launch-rail speed and deployment time exactly match the original flat runs at stored precision.',
'Independent bilinear interpolation, MGRS polygon decoding and point-in-polygon checks agree. Saved path endpoints match landing coordinates.',
'Maximum horizontal difference at the old flat plane is 0.0443 m, attributable to track interpolation versus the original clipped final integration step.',
'Green-area classifications are unchanged by terrain correction; one J570W landing is within 1 m of the supplied boundary.',
'Numerical root residuals are not DEM accuracy estimates.',
'','Interpretation:',
'Percentages describe these assumed numerical scenarios conditional on completed simulations, not a measured launch-day probability.',
'Bare-earth DEM excludes crops, trees and structures. DEM, wind-profile, rocket mass/Cd and parachute-opening uncertainty are not sampled.',
'Imagery acquisition date is not determined; 2026-10-16 is the retrieval date. Satellite imagery and parcel outlines are different sources; only the supplied perimeter is drawn.',
'','Files:',
'index.html — gallery of all 11 final figures, with the interactive 3D link.',
'terrain_landings_2d.png — motor-by-motor satellite map; terrain_site_2d.png — full enclosed site.',
'terrain_tracks_3d.png — static 3D comparison; terrain_tracks_3d.html — standalone interactive 3D, works offline.',
'terrain_landings.csv / .geojson — all 973 terrain-corrected landing locations.',
'cases.csv — all 1000 weather inputs; extended_runs.csv — raw virtual-floor diagnostics, NOT actual landing positions.',
'traces/ — full native tracks, including paths below actual ground; terrain_tracks/ — all 973 tracks cut at ground contact.',
'run_manifest.json, terrain_summary.json, validation.json — inputs, sources, methods and checks.',
'All eight earlier Monte Carlo diagnostic figures have been regenerated using corrected terrain landings.',
'','Sources:',report['dem_source'],'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
'Imagery credit: Esri, Maxar, Earthstar Geographics and GIS community. Elevation: USGS 3DEP.',
'','Reproduction:',
'Use the requirements-recovery.txt environment and the MIT OpenRocket engine JAR matching run_manifest.json (custom fin type required).',
'Run rerun_trajectories.py for native traces, then recovery_terrain.py --output <this folder> --flat-reference <previous flat folder>.',
'Cached DEM and satellite rasters make rendering independent of live data changes. The live .ork changed after the original study; this run uses the preserved rocket copy packaged here.',
])
(out/'results.txt').write_text('\n'.join(lines)+'\n')
figures=[('terrain_landings_2d.png','Terrain-corrected landings · 2D satellite'),('terrain_tracks_3d.png','Flight paths and terrain · 3D'),('terrain_site_2d.png','Full enclosed recovery area'),('landing_footprint.png','Landing footprint and 95th-percentile radius'),('landing_scatter.png','Landings coloured by mean wind'),('landing_satellite.png','Landing cloud and radius over satellite imagery'),('landing_distributions.png','Landing-distance distribution'),('landing_vs_wind.png','Landing distance versus wind'),('wind_inputs.png','Sampled wind and turbulence'),('simulation_completion.png','Completed and aborted simulations'),('flight_metrics.png','Flight metrics')]
rows=''.join(f'<tr><td>{c["motor"]}</td><td>{c["inside"]}/{c["completed"]}</td><td>{c["inside_percent"]:.2f}%</td><td>{c["excluded_tumble_aborts"]}</td></tr>' for c in report['configs'])
sections=''.join(f'<section><h2>{title}</h2><a href="{path}"><img src="{path}" alt="{title}" loading="lazy"></a></section>' for path,title in figures)
html='''<!doctype html><html><head><meta charset="utf-8"><title>URRG · Terrain recovery results</title><style>body{max-width:1200px;margin:35px auto;padding:0 24px;color:#173247;background:#f7f9fb;font:16px system-ui}p{line-height:1.6}table{border-collapse:collapse}td,th{text-align:left;padding:12px 24px;border-bottom:1px solid #cddbe5}section{background:white;border-radius:12px;padding:20px;margin:30px 0}img{width:100%;height:auto}a{color:#126e8a}h2{font-size:21px}.button{display:inline-block;padding:12px 20px;color:white;background:#176e84;text-decoration:none;border-radius:8px}</style></head><body><h1>URRG · Terrain-corrected recovery</h1><p>500 trials per motor, no drogue, main at apogee + 1 second, 1 m rail. Mean wind 0–5 m/s, direction 0–360°, turbulence intensity 5–20%. Each completed trajectory stops at its first descending intersection with USGS terrain.</p><p><a class="button" href="terrain_tracks_3d.html">Open interactive 3D</a></p><table><tr><th>Motor</th><th>Inside / finished</th><th>Inside</th><th>Excluded tumble aborts</th></tr>'''+rows+'''</table><p>These percentages are conditional on simulations that finished. The ground across the simulated landing points spans 267.0–274.4 m NAVD88. Terrain correction moves the endpoints by at most 4.2 m and does not change which side of the supplied boundary they fall on. All views use true scale.</p><p><a href="terrain_landings.csv">Landing coordinates</a> · <a href="terrain_landings.geojson">GeoJSON</a> · <a href="results.txt">Methods and results</a> · <a href="validation.json">Validation</a></p>'''+sections+'''<p>Imagery: Esri World Imagery. Elevation: <a href="https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer">USGS 3DEP</a>, bare-earth model exported at 2 m. Launch coordinates from the telemetry UI preset; perimeter from the supplied MGRS file.</p></body></html>'''
(out/'index.html').write_text(html)
# Compact deliverable: every graph, interactive map, table and provenance; full
# native/trimmed tracks and geospatial rasters remain in the workspace folder.
archive=source/'URRG_terrain_2D_3D_results.zip'
files=[out/path for path,_ in figures]+[out/name for name in ['index.html','terrain_tracks_3d.html','terrain_landings.csv','terrain_landings.geojson','terrain_summary.json','validation.json','results.txt','cases.csv','extended_runs.csv','run_manifest.json','perimeter_mgrs.txt','dem_request.json','dem_identify_pad.json','imagery_source.json','20267.demonstrator.iteration3.URRG.ork']]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for path in files:
  assert path.is_file(),path
  z.write(path,path.name)
 for name in ['RecoveryBatch.java','montecarlo_recovery.py','recovery_perimeter.py','recovery_terrain.py','recovery_plots.py','requirements-recovery.txt']:
  z.write(source/name,'source/'+name)
 z.writestr('BUNDLE_CONTENTS.txt','This compact bundle contains all 11 final figures, the standalone interactive 3D view, coordinates, model inputs, provenance and source code. Open index.html. Full native tracks, terrain-trimmed tracks, DEM and imagery rasters remain in the original workspace output folder. Reproduction also requires the hash-matched MIT engine, baseline runs and cached rasters described in results.txt.\n')
print('Gallery and compact results bundle ready:',archive,round(archive.stat().st_size/1e6,1),'MB')
