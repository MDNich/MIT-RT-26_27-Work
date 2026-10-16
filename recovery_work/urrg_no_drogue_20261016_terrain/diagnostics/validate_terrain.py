"""Independent checks of exported intersections, coordinates and containment."""
from pathlib import Path
import csv,json,sys
import numpy as np
import rasterio
from pyproj import Transformer
from matplotlib.path import Path as PolygonPath
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from recovery_terrain import first_contact

out=Path(__file__).resolve().parents[1]
report=json.loads((out/'terrain_summary.json').read_text())
rows=list(csv.DictReader((out/'terrain_landings.csv').open()))
lat,lon=report['launch_site']['latitude_deg'],report['launch_site']['longitude_deg']
crs=f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m'
to_utm=Transformer.from_crs(crs,32618,always_xy=True)
to_geo=Transformer.from_crs(crs,4326,always_xy=True)
codes=(out/'perimeter_mgrs.txt').read_text().splitlines()
# Independent MGRS digit decoding for this 18TUN grid square.
vertices=np.array([(300000+int(s[5:10]),4700000+int(s[10:15])) for s in codes if s])
polygon=PolygonPath(np.vstack([vertices,vertices[0]]))
with rasterio.open(out/'usgs_3dep_dem_2m.tif') as ds:
 dem=ds.read(1);transform=ds.transform
max_error=0;max_geographic_error=0
for r in rows:
 east,north=float(r['east_m']),float(r['north_m'])
 ux,uy=to_utm.transform(east,north)
 col,row=~transform*(ux,uy);col-=.5;row-=.5
 c,q=int(np.floor(col)),int(np.floor(row));fx,fy=col-c,row-q
 # Explicit bilinear interpolation, independent of scipy sampler used in analysis.
 expected=(1-fy)*((1-fx)*float(dem[q,c])+fx*float(dem[q,c+1]))+fy*((1-fx)*float(dem[q+1,c])+fx*float(dem[q+1,c+1]))
 max_error=max(max_error,abs(expected-float(r['terrain_above_pad_m'])-report['terrain_pad_elevation_navd88_m']))
 assert bool(polygon.contains_point((ux,uy)))==(r['inside_green_area']=='True')
 glon,glat=to_geo.transform(east,north)
 max_geographic_error=max(max_geographic_error,abs(glon-float(r['longitude_deg'])),abs(glat-float(r['latitude_deg'])))
 tr=np.genfromtxt(out/'terrain_tracks'/f"{r['case_id']}_sim{int(float(r['simulation_index']))}.csv.gz",delimiter=',',skip_header=1)
 np.testing.assert_allclose(tr[-1,:4],[float(r['flight_time_s']),east,north,float(r['terrain_above_pad_m'])],atol=1e-8,rtol=0)
 assert np.all(np.diff(tr[:,0])>=0)
class Slope:
 pad_m=0
 def sample(self,x,y):return .05*np.asarray(x)
tr=np.array([[0,0,0,0,0],[1,0,0,100,0],[2,50,0,50,-70],[3,60,0,-20,-70]],float)
hit,_,err=first_contact(tr,Slope())
np.testing.assert_allclose(hit,tr[2]+(47.5/70.5)*(tr[3]-tr[2]),atol=1e-10)
assert max_error<1e-6 and max_geographic_error<1e-10
for i,cfg in enumerate(report['configs']):
 group=[r for r in rows if int(float(r['simulation_index']))==i]
 assert len(group)==cfg['completed'] and sum(r['inside_green_area']=='True' for r in group)==cfg['inside']
result={'passed':True,'intersections_checked':len(rows),'max_independent_bilinear_residual_m':max_error,
        'max_geographic_roundtrip_error_degrees':max_geographic_error,
        'independent_mgrs_polygon_classifications_agree':True,'analytic_sloping_plane_test_passed':True,
        'all_saved_track_endpoints_match_landing_table':True,'simulation_validation':report['validation']}
(out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
