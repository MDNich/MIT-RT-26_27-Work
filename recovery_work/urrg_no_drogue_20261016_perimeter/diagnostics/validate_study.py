"""Validate the saved URRG perimeter run without rerunning the flight engine."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from matplotlib.path import Path as PlotPath
from pyproj import Geod
from shapely.geometry import Point

out = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(out.parent))
from recovery_perimeter import load_perimeter
summary = json.loads((out/'summary.json').read_text())
receipt = json.loads((out/'run_manifest.json').read_text())
report = json.loads((out/'perimeter_summary.json').read_text())
rows = list(csv.DictReader((out/'runs.csv').open()))
landings = list(csv.DictReader((out/'landing_containment.csv').open()))
assert len(rows) == 2*summary['trials_per_motor']+4
assert len({(r['case_id'],r['simulation_index']) for r in rows}) == len(rows)
assert hashlib.sha256((out/'perimeter_mgrs.txt').read_bytes()).hexdigest() == receipt['perimeter_sha256']
b = load_perimeter(out/'perimeter_mgrs.txt', summary['launch_site'])
p = b['polygon']
assert p.is_valid and len(b['codes']) == 1000 and not p.interiors
xy = np.asarray(p.exterior.coords)
assert np.array_equal(xy[0],xy[-1]) and len(xy) == 1001
assert p.covers(Point(xy[0]))
assert not p.covers(Point(p.bounds[0]-10,p.bounds[1]-10))
for code, position in zip(b['codes'],xy[:-1]):
    assert code.startswith('18TUN')
    np.testing.assert_allclose(position, [300000+int(code[5:10]),4700000+int(code[10:])],rtol=0,atol=1e-5)
grid = np.rint(xy).astype(np.int64)
shoelace = .5*abs(np.sum(grid[:-1,0]*grid[1:,1]-grid[1:,0]*grid[:-1,1]))
assert abs(shoelace-p.area)<.01
geod = Geod(ellps='WGS84');site = summary['launch_site']
flags = []
local = []
for r in landings:
    assert r['case_id'].startswith('mc_') and r['ground_hit']=='True'
    lon,lat = float(r['longitude_deg']),float(r['latitude_deg'])
    point = Point(b['to_utm'].transform(lon,lat))
    inside = r['inside_green_area']=='True'
    assert inside == p.covers(point)
    distance = point.distance(p.boundary)
    assert abs(distance-float(r['distance_to_boundary_m']))<1e-6
    assert abs(geod.inv(site['longitude_deg'],site['latitude_deg'],lon,lat)[2]-float(r['radius_m']))<1e-5
    flags.append(inside);local.append([float(r['east_m']),float(r['north_m'])])
# Independent winding-rule implementation in the actual map projection.
np.testing.assert_array_equal(PlotPath(np.vstack([b['local'],b['local'][0]])).contains_points(local),flags)
for item,cfg in zip(report['configs'],summary['configs']):
    records = [r for r in landings if r['motor']==item['motor']]
    inside = sum(r['inside_green_area']=='True' for r in records)
    attempts = [r for r in rows if r['case_id'].startswith('mc_') and int(r['simulation_index'])==cfg['index']]
    assert len(attempts)==summary['trials_per_motor']
    assert len(records)==cfg['complete_trials']==item['completed_flights']
    assert inside==item['inside_green_area']
    assert len(records)-inside==item['outside_green_area']
    assert abs(100*inside/len(records)-item['inside_percent'])<1e-10
    assert len(attempts)-len(records)==item['excluded_incomplete']
    assert all('tumble under thrust' in r['warnings'] for r in attempts if r['ground_hit']=='false')
    delays=[float(r['deployment_time_s'])-float(r['apogee_time_s']) for r in records]
    assert max(abs(np.asarray(delays)-1))<cfg['timestep_s']+.001
prior = out.parent/'urrg_no_drogue_20261011_randomwind0to5ms'
assert (out/'cases.csv').read_bytes()==(prior/'cases.csv').read_bytes()
old={(r['case_id'],r['simulation_index']):r for r in csv.DictReader((prior/'runs.csv').open())}
maximum_difference=0
for r in rows:
    ref=old[(r['case_id'],r['simulation_index'])]
    for key in r:
        if key in {'case_id','ground_hit','warnings'}:
            assert r[key]==ref[key]
        else:
            a,z=float(r[key]),float(ref[key])
            assert np.isclose(a,z,atol=1e-8,rtol=0,equal_nan=True),(r['case_id'],key,a,z)
            if np.isfinite(a) and np.isfinite(z):maximum_difference=max(maximum_difference,abs(a-z))
validation={'passed':True,'attempted_flights':2*summary['trials_per_motor'],'completed_landings_classified':len(landings),'perimeter_points':len(b['codes']),'polygon_area_m2_independent_shoelace':shoelace,'grid_conversion_validated':True,'independent_map_projection_classifications_match':True,'aborts_and_controls_excluded_from_denominator':True,'all_rerun_results_match_previous_study':True,'maximum_numeric_difference_from_previous_study':maximum_difference,'case_inputs_sha256':receipt['cases_sha256'],'perimeter_sha256':receipt['perimeter_sha256']}
(out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps(validation,indent=2))
