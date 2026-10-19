"""Classify real simulated landings against an ordered MGRS perimeter."""
import csv
import hashlib
import json
from pathlib import Path

import mgrs
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PlotPolygon
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, Polygon, mapping
from shapely.validation import explain_validity


def load_perimeter(path, launch):
    path = Path(path)
    codes = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(codes) < 3:
        raise ValueError('At least three ordered MGRS perimeter points are required.')
    converter = mgrs.MGRS()
    lonlat = []
    for i, code in enumerate(codes, 1):
        try:
            lat, lon = converter.toLatLon(code)
        except Exception as exc:
            raise ValueError(f'Invalid perimeter MGRS point on row {i}: {code}') from exc
        lonlat.append((lon, lat))
    # URRG lies in UTM 18N. This metre-based projection preserves the supplied
    # MGRS grid coordinates and avoids Web Mercator distance distortion.
    to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32618', always_xy=True)
    xy = [to_utm.transform(lon, lat) for lon, lat in lonlat]
    polygon = Polygon(xy)  # closes last-to-first, without sorting the vertices
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Invalid perimeter polygon: '+explain_validity(polygon))
    crs = f'+proj=aeqd +lat_0={launch["latitude_deg"]} +lon_0={launch["longitude_deg"]} +datum=WGS84 +units=m'
    to_local = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
    local = np.array([to_local.transform(lon, lat) for lon, lat in lonlat])
    pad = Point(to_utm.transform(launch['longitude_deg'], launch['latitude_deg']))
    return {'polygon': polygon, 'lonlat': lonlat, 'local': local, 'crs': crs,
            'to_utm': to_utm, 'codes': codes,
            'metadata': {'source': str(path.resolve()),
                         'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'point_count': len(codes), 'utm_crs': 'EPSG:32618',
                         'area_m2': polygon.area, 'area_km2': polygon.area/1e6,
                         'launch_inside': bool(polygon.covers(pad)),
                         'launch_to_boundary_m': pad.distance(polygon.boundary),
                         'boundary_rule': 'Connect points in file order; close last to first. Boundary counts as inside.',
                         'coordinate_convention': 'MGRS grid-cell southwest corner; same convention as the telemetry launch preset.'}}


def analyze_perimeter(args, summary, rows, boundary):
    polygon = boundary['polygon']
    report = {**boundary['metadata'], 'launch_site': summary['launch_site'],
              'weather': summary['weather_description'],
              'denominator': 'Completed Monte Carlo flights with main deployment; aborts and control flights excluded.',
              'configs': []}
    landing_rows = []
    groups = []
    for cfg in summary['configs']:
        samples = [r for r in rows if r['simulation_index'] == cfg['index']
                   and r['case_id'].startswith('mc_') and r['ground_hit']
                   and np.isfinite(r['radius_m']) and np.isfinite(r['deployment_time_s'])]
        classified = []
        for r in samples:
            point = Point(boundary['to_utm'].transform(r['longitude_deg'], r['latitude_deg']))
            inside = bool(polygon.covers(point))
            distance = point.distance(polygon.boundary)
            result = dict(r, motor=cfg['motor'], inside_green_area=inside,
                          distance_to_boundary_m=distance,
                          signed_boundary_clearance_m=distance if inside else -distance)
            classified.append(result)
        count = sum(r['inside_green_area'] for r in classified)
        item = {'motor': cfg['motor'], 'default_motor': cfg['default_motor'],
                'inside_green_area': count, 'outside_green_area': len(samples)-count,
                'completed_flights': len(samples), 'excluded_incomplete': cfg['incomplete_trials'],
                'inside_percent': 100*count/len(samples) if samples else None,
                'closest_landing_to_boundary_m': min((r['distance_to_boundary_m'] for r in classified), default=None),
                'landings_within_1m_of_boundary': sum(r['distance_to_boundary_m'] <= 1 for r in classified)}
        report['configs'].append(item)
        groups.append(classified)
        landing_rows.extend(classified)
    (args.output/'perimeter_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    if landing_rows:
        with (args.output/'landing_containment.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(landing_rows[0]))
            writer.writeheader(); writer.writerows(landing_rows)
    with (args.output/'perimeter_coordinates.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['point_number', 'mgrs', 'longitude_deg', 'latitude_deg', 'utm_easting_m', 'utm_northing_m'])
        for i, (code, (lon, lat)) in enumerate(zip(boundary['codes'], boundary['lonlat']), 1):
            writer.writerow([i, code, lon, lat, *boundary['to_utm'].transform(lon, lat)])
    launch = summary['launch_site']
    features = [{'type': 'Feature', 'properties': {'name': 'URRG green area', **boundary['metadata']},
                 'geometry': mapping(Polygon(boundary['lonlat']))},
                {'type': 'Feature', 'properties': {'name': 'Telemetry UI launch pad', 'mgrs': launch['mgrs']},
                 'geometry': {'type': 'Point', 'coordinates': [launch['longitude_deg'], launch['latitude_deg']]}}]
    for r in landing_rows:
        features.append({'type': 'Feature',
                         'properties': {key: r[key] for key in ['motor', 'case_id', 'inside_green_area',
                                         'ground_wind_mps', 'wind_from_deg', 'turbulence', 'signed_boundary_clearance_m']},
                         'geometry': {'type': 'Point', 'coordinates': [r['longitude_deg'], r['latitude_deg']]}})
    (args.output/'perimeter_landings.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, indent=2)+'\n')
    lines = ['\nGreen-area containment — ordered MGRS perimeter',
             f'{len(boundary["codes"])} points; polygon area {polygon.area/1e6:.3f} km².',
             f'Telemetry launch point: {launch["mgrs"]}; {boundary["metadata"]["launch_to_boundary_m"]:.1f} m from nearest boundary.',
             report['denominator']]
    for c in report['configs']:
        rate = f'{c["inside_percent"]:.2f}%' if c['inside_percent'] is not None else 'unavailable'
        lines.append(f'{c["motor"]}: {c["inside_green_area"]}/{c["completed_flights"]} inside ({rate}); '
                     f'{c["outside_green_area"]} outside; {c["excluded_incomplete"]} incomplete excluded.')
    lines.append('The percentage describes the assumed wind scenarios and this numerical model, not measured launch-day probability.')
    (args.output/'containment_results.txt').write_text('\n'.join(lines).lstrip()+'\n')
    with (args.output/'results.txt').open('a') as f:
        f.write('\n'.join(lines)+'\n')
    print('\n'.join(lines), flush=True)
    plot_containment(args, summary, report, groups, boundary)
    return report


def plot_containment(args, summary, report, groups, boundary):
    local = boundary['local']
    limit = max([r['radius_m'] for group in groups for r in group]+[100])*1.2
    excluded = 'Excluded tumble/incomplete runs: ' + ' · '.join(
        f'{c["motor"]} {c["excluded_incomplete"]}' for c in report['configs'])
    weather = (f'Mean wind 0–{args.random_wind_max:g} m/s · directions 0–360° · '
               f'turbulence intensity {args.turbulence_min:.0%}–{args.turbulence_max:.0%}'
               if args.random_wind_max is not None else summary['weather_description'])
    footer = f'{excluded}. Percentages use finished flights only.\nMain at apogee + 1 s · 1 m vertical rail · assumed weather scenarios'

    def add_landings(ax, group, *, dark=False):
        ax.add_patch(PlotPolygon(local, closed=True, facecolor='#51bd6d', alpha=.23,
                                 edgecolor='none', zorder=2))
        ring = np.vstack([local, local[0]])
        ax.plot(ring[:,0], ring[:,1], color='#61ed84' if dark else '#147735', lw=2,
                label='Green-area boundary', zorder=3)
        for inside, color, marker, label in [(True, '#71f5ad' if dark else '#087f59', 'o', 'Inside green area'),
                                             (False, '#ff806b' if dark else '#ce442f', 'x', 'Outside green area')]:
            selected = [r for r in group if r['inside_green_area'] == inside]
            ax.scatter([r['east_m'] for r in selected], [r['north_m'] for r in selected],
                       s=19 if inside else 30, marker=marker, c=color, alpha=.85,
                       linewidths=.35 if inside else 1.2,
                       edgecolors='#14352c' if inside else None, zorder=5, label=label)
        ax.scatter([0], [0], marker='+', s=170, c='white' if dark else '#152e43',
                   linewidths=2.8, zorder=7, label='Telemetry launch pad')
        ax.set(aspect='equal', xlabel='East of launch (m)', ylabel='North of launch (m)')

    fig, axes = plt.subplots(1, 2, figsize=(13, 7.5), layout='constrained')
    for ax, c, group in zip(axes, report['configs'], groups):
        add_landings(ax, group)
        ax.set(xlim=(-limit,limit), ylim=(-limit,limit))
        ax.grid(alpha=.16)
        rate = f'{c["inside_percent"]:.1f}%' if c['inside_percent'] is not None else 'N/A'
        ax.set_title(f'{c["motor"]}'+(' · default motor' if c['default_motor'] else '')+
                     f'\n{c["inside_green_area"]}/{c["completed_flights"]} inside · {rate}', fontsize=13)
        ax.legend(loc='upper right', fontsize=8, framealpha=.95)
    fig.suptitle('URRG · landings inside the supplied perimeter\n'+weather, fontsize=16, fontweight='bold')
    fig.supxlabel(footer, fontsize=9)
    fig.savefig(args.output/'green_area_landings.png', dpi=190)
    plt.close(fig)

    if not args.basemap:
        return
    import contextily as ctx
    fig, axes = plt.subplots(1, 2, figsize=(14, 8), layout='constrained')
    for ax, c, group in zip(axes, report['configs'], groups):
        ax.set(xlim=(-limit,limit), ylim=(-limit,limit))
        ctx.add_basemap(ax, crs=boundary['crs'], source=ctx.providers.Esri.WorldImagery, zoom=17, attribution_size=5)
        add_landings(ax, group, dark=True)
        ax.set(xlim=(-limit,limit), ylim=(-limit,limit))
        rate = f'{c["inside_percent"]:.1f}%' if c['inside_percent'] is not None else 'N/A'
        ax.set_title(f'{c["motor"]}'+(' · default motor' if c['default_motor'] else '')+
                     f'\n{c["inside_green_area"]}/{c["completed_flights"]} inside · {rate}', fontsize=13)
        ax.legend(loc='upper right', fontsize=8, facecolor='#172b40', labelcolor='white', framealpha=.95)
        ax.text(.02,.98,'N ↑', transform=ax.transAxes, va='top', color='white', fontsize=13,
                bbox={'facecolor':'#172b40','alpha':.8,'edgecolor':'none'})
    fig.suptitle('URRG · green-area boundary and simulated landings\n'+weather, fontsize=16, fontweight='bold')
    fig.supxlabel(footer, fontsize=9)
    fig.savefig(args.output/'green_area_satellite.png', dpi=190)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 11), layout='constrained')
    low, high = local.min(axis=0), local.max(axis=0)
    margin = .08*max(high-low)
    ax.set(xlim=(low[0]-margin,high[0]+margin), ylim=(low[1]-margin,high[1]+margin))
    ctx.add_basemap(ax, crs=boundary['crs'], source=ctx.providers.Esri.WorldImagery, zoom=16, attribution_size=6)
    add_landings(ax, [r for group in groups for r in group], dark=True)
    ax.set(xlim=(low[0]-margin,high[0]+margin), ylim=(low[1]-margin,high[1]+margin))
    ax.legend(loc='lower right', fontsize=10, facecolor='#172b40', labelcolor='white', framealpha=.95)
    ax.text(.02,.98,'N ↑', transform=ax.transAxes, va='top', color='white', fontsize=16,
            bbox={'facecolor':'#172b40','alpha':.8,'edgecolor':'none'})
    fig.suptitle(f'URRG · complete enclosed green area\n{len(boundary["codes"]):,} ordered MGRS points · {boundary["metadata"]["area_km2"]:.3f} km²',
                 fontsize=17, fontweight='bold')
    fig.supxlabel('Both motor landing clouds shown. Launch pad: '+summary['launch_site']['mgrs']+'\n'+footer, fontsize=9)
    fig.savefig(args.output/'green_area_overview.png', dpi=190)
    plt.close(fig)
