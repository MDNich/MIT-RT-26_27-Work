"""URRG main-only recovery dispersion using the supplied MIT OpenRocket model.

Rocket-file defaults are retained except for explicitly selected wind uncertainty.
--wind-speed sets a fixed mean; --random-wind-max samples mean speed uniformly
from zero to that value, direction uniformly over 360 degrees, and turbulence
intensity uniformly between --turbulence-min and --turbulence-max. Stratified
random draws cover these distributions, with paired weather across motors.
Native OpenRocket pink noise varies speed during each flight. The speed cap is
on the MEAN: instantaneous gusts can exceed it. Rocket and recovery are unchanged.
The original high-altitude approximation is archived in urrg_no_drogue_20261011/.

Requires numpy, matplotlib, pyproj, mgrs, Java 17+, and a compatible MIT OpenRocket
fat JAR (this design uses the custom tabctrltrapezoidfinset component).
Example:
  python montecarlo_recovery.py --openrocket-jar /path/to/swing-24.12.RC.01-all.jar
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor

import mgrs
import numpy as np
from pyproj import Geod
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DEFAULT_ORK = HERE.parent / 'simulation_work/generic/openrocket/OpenRocket2026/2627_official/20267.demonstrator.iteration3.ork'
DEFAULT_MGRS = '18TUN2061530290'
# USGS 3DEP point query at the supplied MGRS location, retrieved 2026-10-11.
URRG_ELEVATION_M = 268.603118896
ELEVATION_SOURCE = 'https://epqs.nationalmap.gov/v1/json?x=-77.19029501648315&y=42.70416776971639&units=Meters&wkid=4326&includeDate=False'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def site():
    lat, lon = mgrs.MGRS().toLatLon(DEFAULT_MGRS)
    return {'name': 'URRG', 'mgrs': DEFAULT_MGRS, 'latitude_deg': lat,
            'longitude_deg': lon, 'elevation_m': URRG_ELEVATION_M,
            'elevation_source': ELEVATION_SOURCE}


def read_design(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('rocket.ork'))
    chutes = root.findall('.//parachute')
    if len(chutes) != 1:
        raise ValueError('Expected the supplied main-only design with exactly one parachute.')
    chute = chutes[0]
    if chute.findtext('deployevent') != 'apogee' or float(chute.findtext('deploydelay')) != 1:
        raise ValueError('This analysis expects main deployment at apogee + 1 s.')
    motors = {e.attrib['configid']: e.findtext('designation') for e in root.findall('.//motormount/motor')}
    default_id = next(e.attrib['configid'] for e in root.findall('./rocket/motorconfiguration') if e.attrib.get('default') == 'true')
    configs = []
    for i, sim in enumerate(root.findall('./simulations/simulation')[:2]):
        cond = sim.find('conditions')
        wind = cond.find("wind[@model='average']")
        if cond.findtext('windmodeltype') != 'Average':
            raise ValueError('This runner expects the source average-wind model.')
        cfg = cond.findtext('configid')
        configs.append({'index': i, 'name': sim.findtext('name'), 'motor': motors[cfg],
                        'default_motor': cfg == default_id,
                        'rail_length_m': float(cond.findtext('launchrodlength')),
                        'rail_angle_deg': float(cond.findtext('launchrodangle')),
                        'mean_wind_mps': float(wind.findtext('speed')),
                        'wind_std_mps': float(wind.findtext('standarddeviation')),
                        'wind_from_deg': float(np.degrees(float(wind.findtext('direction')))),
                        'timestep_s': float(cond.findtext('timestep'))})
    return root, configs, {'diameter_m': float(chute.findtext('diameter')),
                          'cd': float(chute.findtext('cd')),
                          'deployment_event': 'apogee', 'deployment_delay_s': 1.0}


def write_site_copy(source, output, root, launch):
    # Cached results are invalid at a new site. Preserve all design/default fields.
    for sim in root.findall('./simulations/simulation'):
        cond = sim.find('conditions')
        for tag, value in [('launchlatitude', launch['latitude_deg']),
                           ('launchlongitude', launch['longitude_deg']),
                           ('launchaltitude', launch['elevation_m'])]:
            cond.find(tag).text = str(value)
        for data in sim.findall('flightdata'):
            sim.remove(data)
        sim.set('status', 'notsimulated')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in original.namelist():
            z.writestr(name, data if name == 'rocket.ork' else original.read(name))


def override_wind(root, configs, speed):
    """Change mean wind while retaining direction and turbulence intensity."""
    for cfg in configs:
        intensity = cfg['wind_std_mps'] / cfg['mean_wind_mps']
        cfg['mean_wind_mps'] = speed
        cfg['wind_std_mps'] = intensity * speed
    for cond in root.findall('./simulations/simulation/conditions'):
        wind = cond.find("wind[@model='average']")
        old_speed = float(wind.findtext('speed'))
        intensity = float(wind.findtext('standarddeviation')) / old_speed
        wind.find('speed').text = str(speed)
        wind.find('standarddeviation').text = str(intensity * speed)
        cond.find('windaverage').text = str(speed)
        cond.find('windturbulence').text = str(intensity)


def json_finite(value):
    """Represent unavailable results from aborted simulations as JSON null."""
    if isinstance(value, dict):
        return {k: json_finite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_finite(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_cases(path, configs, n, seed, wind_max=None, turbulence_min=.05, turbulence_max=.20):
    # Independently permuted strata provide uniform marginal coverage without
    # adding visual jitter or rotating simulated landing coordinates afterward.
    rng = np.random.default_rng(seed)
    draws = np.column_stack([(rng.permutation(n) + rng.random(n)) / n for _ in range(3)])
    weather = np.column_stack([draws[:, 0] * (wind_max or 0), draws[:, 1] * 360,
                              turbulence_min + draws[:, 2] * (turbulence_max-turbulence_min)])
    with path.open('w', newline='') as f:
        out = csv.writer(f)
        out.writerow(['case_id', 'simulation_index', 'ground_wind_mps', 'cloud_wind_mps',
                      'wind_from_deg', 'turbulence', 'seed', 'elevation_m'])
        for cfg in configs:
            w = cfg['mean_wind_mps']
            intensity = cfg['wind_std_mps'] / w if w else 0
            for trial in range(n):
                speed, direction, ti = weather[trial] if wind_max is not None else (w, cfg['wind_from_deg'], intensity)
                out.writerow([f'mc_{cfg["index"]}_{trial:04}', cfg['index'], speed, speed,
                              direction, ti, seed + trial, URRG_ELEVATION_M])
            # Matched steady-wind cases check location effects and repeatability.
            for label, elevation in [('steady_urrg', URRG_ELEVATION_M), ('steady_sealevel', 0.0)]:
                out.writerow([label, cfg['index'], w, w, cfg['wind_from_deg'], 0, seed, elevation])


def run_engine(args, cases, results, launch):
    jar = args.openrocket_jar.resolve()
    if not jar.is_file():
        raise FileNotFoundError(jar)
    jhome = Path(args.java_home) if args.java_home else None
    javac = str(jhome / 'bin/javac') if jhome else shutil.which('javac')
    java = str(jhome / 'bin/java') if jhome else shutil.which('java')
    if not javac or not java:
        raise RuntimeError('Java and javac are required; pass --java-home.')
    receipt = {'source_ork': str(args.ork.resolve()), 'source_ork_sha256': digest(args.ork),
               'engine_jar': str(jar), 'engine_jar_sha256': digest(jar),
               'trials_per_motor': args.trials, 'first_seed': args.seed,
               'wind_speed_override_mps': args.wind_speed,
               'random_wind_max_mps': args.random_wind_max,
               'turbulence_intensity_range': [args.turbulence_min, args.turbulence_max],
               'cases_sha256': digest(cases), 'java_runner_sha256': digest(HERE/'RecoveryBatch.java'),
               'sampling': ('Latin hypercube, independent uniform marginals, paired weather across motors'
                            if args.random_wind_max is not None else 'Fixed mean weather, varying pink-noise seeds'),
               'workers': args.workers}
    (args.output/'run_manifest.json').write_text(json.dumps(receipt, indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='urrg-recovery-') as build:
        subprocess.run([javac, '-cp', str(jar), '-d', build, str(HERE / 'RecoveryBatch.java')], check=True)
        cmd = [java, '-Xmx2g', '-Djava.awt.headless=true', '-cp', os.pathsep.join([build, str(jar)]),
               'RecoveryBatch', str(args.ork.resolve())]
        coords = [str(launch['latitude_deg']), str(launch['longitude_deg']), str(launch['elevation_m'])]
        def run_part(index, case_path, result_path):
            with (args.output / f'engine_{index}.log').open('w') as log:
                subprocess.run(cmd + [str(case_path), str(result_path)] + coords,
                               stdout=log, stderr=log, check=True)
        with cases.open() as f:
            reader = csv.DictReader(f)
            fields, inputs = reader.fieldnames, list(reader)
        workers = min(args.workers, len(inputs))
        parts = []
        for i in range(workers):
            case_path, result_path = Path(build)/f'cases_{i}.csv', Path(build)/f'runs_{i}.csv'
            with case_path.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader(); writer.writerows(inputs[i::workers])
            parts.append((i, case_path, result_path))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_part, *part) for part in parts]
            for future in futures:
                future.result()
        # Preserve input order and reject missing/duplicate output records.
        outputs = {}
        for _, _, result_path in parts:
            with result_path.open() as f:
                reader = csv.DictReader(f)
                output_fields = reader.fieldnames
                for row in reader:
                    key = (row['case_id'], row['simulation_index'])
                    if key in outputs: raise ValueError(f'Duplicate result: {key}')
                    outputs[key] = row
        if len(outputs) != len(inputs): raise ValueError('Incomplete engine output')
        with results.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=output_fields)
            writer.writeheader()
            writer.writerows(outputs[(row['case_id'], row['simulation_index'])] for row in inputs)


def read_results(path, launch):
    with path.open() as f:
        rows = list(csv.DictReader(f))
    geod = Geod(ellps='WGS84')
    for r in rows:
        for key in r.keys() - {'case_id', 'ground_hit', 'warnings'}:
            r[key] = float(r[key])
        r['ground_hit'] = r['ground_hit'] == 'true'
        # Use geodesic offsets in true metres, never add ground metres to EPSG:3857.
        az = np.degrees(np.arctan2(r['east_m'], r['north_m']))
        lon, lat, _ = geod.fwd(launch['longitude_deg'], launch['latitude_deg'], az, r['radius_m'])
        r['longitude_deg'] = lon if r['ground_hit'] else None
        r['latitude_deg'] = lat if r['ground_hit'] else None
    with path.with_name('landing_coordinates.csv').open('w', newline='') as f:
        out = csv.DictWriter(f, fieldnames=list(rows[0]))
        out.writeheader(); out.writerows(rows)
    return rows


def stats(values):
    q = np.percentile(values, [0, 2.5, 5, 50, 95, 97.5, 100])
    return dict(zip(['min', 'p2_5', 'p5', 'median', 'p95', 'p97_5', 'max'], map(float, q)))


def finished_samples(rows, index):
    return [r for r in rows if r['simulation_index'] == index and r['case_id'].startswith('mc_')
            and r['ground_hit'] and np.isfinite(r['radius_m']) and np.isfinite(r['deployment_time_s'])]


def wind_description(args, configs):
    if args.random_wind_max is not None:
        return (f'Mean wind uniform 0–{args.random_wind_max:g} m/s; direction uniform 0–360°; '
                f'turbulence intensity uniform {args.turbulence_min:.0%}–{args.turbulence_max:.0%}.')
    cfg = configs[0]
    return (f'Mean wind {cfg["mean_wind_mps"]:g} m/s FROM {cfg["wind_from_deg"]:g}°; '
            f'pink-noise standard deviation {cfg["wind_std_mps"]:g} m/s.')


def summarize(args, configs, parachute, launch, rows):
    manifest = args.output/'run_manifest.json'
    receipt = json.loads(manifest.read_text()) if manifest.exists() else {
        'source_ork': str(args.ork.resolve()), 'source_ork_sha256': digest(args.ork),
        'engine_jar': str(args.openrocket_jar.resolve()), 'engine_jar_sha256': digest(args.openrocket_jar)}
    summary = {'launch_site': launch, **receipt, 'trials_per_motor': args.trials,
               'first_seed': args.seed, 'parachute': parachute, 'wind_speed_override_mps': args.wind_speed,
               'weather_description': wind_description(args, configs),
               'uncertainty_scope': ('Uniform scenario distributions for mean wind, direction and turbulence intensity; '
                    'native speed turbulence within flights. Same weather draws across motors. No wind shear or '
                    'within-flight direction changes; all design parameters fixed.' if args.random_wind_max is not None else
                    'Only OpenRocket pink-noise wind realizations; all design and mean weather settings fixed.'),
               'configs': []}
    for cfg in configs:
        trials = [r for r in rows if r['simulation_index'] == cfg['index'] and r['case_id'].startswith('mc_')]
        valid = finished_samples(rows, cfg['index'])
        item = dict(cfg, complete_trials=len(valid), incomplete_trials=len(trials)-len(valid),
                    percentile_scope='Conditional on simulations reaching landing with main deployment',
                    incomplete_reasons=sorted({r['warnings'] for r in trials if r not in valid}))
        if args.random_wind_max is not None:
            item['nominal_source_wind'] = {key: item.pop(key) for key in
                                           ['mean_wind_mps', 'wind_std_mps', 'wind_from_deg']}
        if valid:
            item['radius_m'] = stats([r['radius_m'] for r in valid])
            item['apogee_m'] = stats([r['apogee_m'] for r in valid])
            item['descent_time_s'] = stats([r['flight_time_s']-r['apogee_time_s'] for r in valid])
            item['vertical_landing_mps'] = stats([r['vertical_landing_mps'] for r in valid])
            item['landing_mass_kg'] = float(np.median([r['landing_mass_kg'] for r in valid]))
            item['representative_trial'] = min(valid, key=lambda r: abs(r['radius_m']-item['radius_m']['median']))
        item['sampled_weather'] = {name: stats([r[name] for r in trials])
                                   for name in ['ground_wind_mps', 'wind_from_deg', 'turbulence']}
        item['checks'] = [r for r in rows if r['simulation_index'] == cfg['index'] and not r['case_id'].startswith('mc_')]
        summary['configs'].append(item)
    (args.output / 'summary.json').write_text(json.dumps(json_finite(summary), indent=2, allow_nan=False)+'\n')
    lines = ['URRG — no drogue; main at apogee + 1 second',
             f'Site: {DEFAULT_MGRS}, {launch["latitude_deg"]:.8f}, {launch["longitude_deg"]:.8f}, {URRG_ELEVATION_M:.2f} m MSL.',
             'Rocket defaults retained: one 1.92024 m main, Cd 0.68; vertical 1 m rail; ISA atmosphere.',
             f'{args.trials} fresh OpenRocket flights per motor; seed {args.seed} onward.',
             'Wind: ' + wind_description(args, configs),
             ('Mean wind is capped; instantaneous gusts can exceed it. These are assumed scenarios, not a weather forecast.'
              if args.random_wind_max is not None else 'Uncertainty is within-flight turbulence; mean weather is fixed.'), '']
    for item in summary['configs']:
        lines += [f'{item["motor"]}' + (' (default motor)' if item['default_motor'] else ''),
                  f'  Landed / finished: {item["complete_trials"]}/{item["complete_trials"]}.',
                  f'  Excluded incomplete simulations: {item["incomplete_trials"]} (out of {args.trials} attempted).']
        if item['incomplete_trials']:
            lines += ['  No all-trials 95% landing radius can be claimed; percentiles below apply ONLY to completed flights.',
                      '  Reasons: ' + '; '.join(item['incomplete_reasons'])]
        if 'radius_m' not in item:
            lines += ['  No landing-distance estimate: no trial reached landing.', '']
            continue
        r = item['radius_m']
        lines += [f'  Median distance from pad: {r["median"]:.1f} m.',
                  f'  Central 95% interval: {r["p2_5"]:.1f}–{r["p97_5"]:.1f} m.',
                  f'  95th-percentile radius centred on launch: {r["p95"]:.1f} m.',
                  f'  Observed minimum–maximum: {r["min"]:.1f}–{r["max"]:.1f} m.',
                  f'  Median apogee AGL: {item["apogee_m"]["median"]:.1f} m.',
                  f'  Median apogee-to-ground time: {item["descent_time_s"]["median"]:.1f} s.',
                  f'  Median vertical touchdown speed: {item["vertical_landing_mps"]["median"]:.2f} m/s.', '']
    lines += ['Interpretation and limits:',
              'Distances are horizontal radii from the launch point; they are not footprint diameters.',
              summary['uncertainty_scope'],
              'Percentiles describe the specified numerical scenarios, not real-world containment confidence.',
              'Main inflation is idealized by OpenRocket. No chute failure, mass/Cd uncertainty, terrain landing height, or wind forecast is sampled.',
              'Incomplete runs are excluded from landing statistics and reported explicitly. A model abort is not a predicted landing or a quantified physical failure probability.',
              'The original script had a 110,000 ft apogee, inconsistent altitude units, a 105 m/s rail speed and cloud wind applied over the entire descent.',
              'Those assumptions were replaced by the supplied rocket model and user-confirmed file defaults.',
              f'Elevation source: {ELEVATION_SOURCE}',
              'OpenRocket wind convention: https://openrocket.readthedocs.io/en/latest/setup/preferences.html',
              'Launch-rail abort limitation: https://github.com/openrocket/openrocket/issues/3183',
              'The URRG .ork copy contains the site and nominal settings, with cached flight results cleared. Individual Monte Carlo weather inputs are in cases.csv.']
    (args.output / 'results.txt').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[:28]))
    return summary


def scatter_landing_zoom(ax, samples, color, compact=False):
    """Plot actual positions with explicitly different east/north axis units."""
    east = np.array([r['east_m'] for r in samples])
    north_mm = 1000 * np.array([r['north_m'] for r in samples])
    ax.scatter(east, north_mm, s=12 if compact else 30, color=color,
               alpha=.75, edgecolors='#172b40', linewidths=.25)
    ax.set_facecolor('white')
    ax.set_xlabel('East of launch (m)', fontsize=7 if compact else 10)
    ax.set_ylabel('North (mm; magnified)', fontsize=7 if compact else 10)
    ax.tick_params(labelsize=6 if compact else 9)
    ax.locator_params(axis='both', nbins=4 if compact else 6)
    ax.margins(.12)
    ax.grid(alpha=.16)
    if compact:
        ax.set_title('Landing points · unequal axis scales', fontsize=7, pad=3)
    for spine in ax.spines.values():
        spine.set_color(color)


def plot(args, summary, rows):
    if args.random_wind_max is not None:
        from recovery_plots import plot_randomized
        plot_randomized(args, summary, rows)
        return
    colors = ['#167c80', '#c15d22']
    first = summary['configs'][0]
    wind_label = f'{first["mean_wind_mps"]:g} m/s wind from east · {first["wind_std_mps"]:g} m/s turbulence · 1 m vertical rail'
    completion_label = 'Landed / finished — ' + ' · '.join(
        f'{c["motor"]}: {c["complete_trials"]}/{c["complete_trials"]}' for c in summary['configs'])
    excluded_label = 'Excluded incomplete runs — ' + ' · '.join(
        f'{c["motor"]}: {c["incomplete_trials"]}' for c in summary['configs'])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), constrained_layout=True)
    for ax, cfg, color in zip(axes, summary['configs'], colors):
        if 'radius_m' not in cfg:
            ax.set_axis_off()
            ax.set_title(cfg['motor'], fontsize=13)
            ax.text(.5,.5, 'No finished simulations\n\nNo landing-distance estimate\n\nModel abort at rail exit',
                    transform=ax.transAxes, ha='center', va='center', fontsize=13)
            continue
        samples = [r for r in rows if r['simulation_index']==cfg['index'] and r['case_id'].startswith('mc_') and r['ground_hit']]
        radius = cfg['radius_m']['p95']
        ax.scatter([r['east_m'] for r in samples], [r['north_m'] for r in samples], s=8, alpha=.6, color=color, linewidths=.2, edgecolors='#172b40', label='Individual landings')
        ax.scatter([0], [0], marker='+', s=150, color='#172b40', linewidth=2, label='Launch point', zorder=5)
        ax.add_patch(plt.Circle((0, 0), radius, fill=False, color=color, linestyle='--', linewidth=1.5, label=f'Completed-flight 95% radius: {radius:.0f} m'))
        limit = radius*1.15
        ax.set(xlim=(-limit,limit), ylim=(-limit,limit), aspect='equal', xlabel='East of launch (m)', ylabel='North of launch (m)')
        r = cfg['radius_m']
        ax.set_title(f'{cfg["motor"]}'+(' · default motor' if cfg['default_motor'] else '')+f'\nMedian {r["median"]:.0f} m | central 95%: {r["p2_5"]:.0f}–{r["p97_5"]:.0f} m', fontsize=11)
        ax.grid(alpha=.18); ax.legend(loc='upper right', fontsize=8)
        zoom = ax.inset_axes([.12, .09, .50, .24], zorder=8)
        scatter_landing_zoom(zoom, samples, color, compact=True)
    fig.suptitle('URRG landing distance · no drogue, main at apogee + 1 s', fontsize=15, fontweight='bold')
    fig.supxlabel(f'{wind_label}\n{completion_label}\n{excluded_label}. Percentiles use finished flights only.', fontsize=9)
    fig.savefig(args.output / 'landing_footprint.png', dpi=190)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
    for ax, cfg, color in zip(axes, summary['configs'], colors):
        samples = [r for r in rows if r['simulation_index']==cfg['index'] and r['case_id'].startswith('mc_') and r['ground_hit']]
        if not samples:
            ax.set_axis_off()
            ax.text(.5, .5, f'{cfg["motor"]}\nNo finished simulations', transform=ax.transAxes, ha='center')
            continue
        scatter_landing_zoom(ax, samples, color)
        count = len(samples)
        ax.set_title(f'{cfg["motor"]}'+(' · default motor' if cfg['default_motor'] else '')+
                     f'\n{count}/{count} landed / finished · median {cfg["radius_m"]["median"]:.0f} m', fontsize=12)
    fig.suptitle(f'URRG Monte Carlo landings · {first["mean_wind_mps"]:g} m/s wind\nOne point per finished flight', fontsize=15, fontweight='bold')
    fig.supxlabel('Actual coordinates; no artificial jitter. Unequal scales: east in metres, north in millimetres.\n'
                  f'Wind direction fixed from east; north–south spread is magnified. {excluded_label}.', fontsize=9)
    fig.savefig(args.output/'landing_scatter.png', dpi=190)
    plt.close(fig)
    features = []
    geod = Geod(ellps='WGS84')
    launch = summary['launch_site']
    features.append({'type':'Feature', 'properties':{'name':'URRG launch', 'MGRS':DEFAULT_MGRS},
                     'geometry':{'type':'Point', 'coordinates':[launch['longitude_deg'], launch['latitude_deg']]}})
    for cfg in summary['configs']:
        if 'radius_m' not in cfg:
            continue
        ring = [list(geod.fwd(launch['longitude_deg'],launch['latitude_deg'],az,cfg['radius_m']['p95'])[:2]) for az in np.linspace(0,360,181)]
        ring[-1]=ring[0]
        features.append({'type':'Feature','properties':{'motor':cfg['motor'],'radius_p95_m':cfg['radius_m']['p95'],
                        'complete_trials':cfg['complete_trials'],'incomplete_trials':cfg['incomplete_trials'],
                        'scope':'Conditional on completed simulations; wind realizations only'},'geometry':{'type':'Polygon','coordinates':[ring]}})
    (args.output/'landing_radii.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}, indent=2)+'\n')
    if args.basemap and any('radius_m' in c for c in summary['configs']):
        import contextily as ctx
        # Azimuthal equidistant projection: radii are real distances from launch.
        crs = f'+proj=aeqd +lat_0={launch["latitude_deg"]} +lon_0={launch["longitude_deg"]} +datum=WGS84 +units=m'
        fig, ax = plt.subplots(figsize=(9, 9), constrained_layout=True)
        limit = max(c['radius_m']['p95'] for c in summary['configs'] if 'radius_m' in c) * 1.65
        ax.set(xlim=(-limit, limit), ylim=(-limit, limit), aspect='equal')
        ctx.add_basemap(ax, crs=crs, source=ctx.providers.Esri.WorldImagery, zoom=17,
                        attribution_size=6)
        for cfg, color in zip(summary['configs'], ['#52e4ec', '#ffb860']):
            if 'radius_m' not in cfg:
                continue
            samples = [r for r in rows if r['simulation_index']==cfg['index'] and r['case_id'].startswith('mc_') and r['ground_hit']]
            radius = cfg['radius_m']['p95']
            ax.add_patch(plt.Circle((0, 0), radius, fill=False, color=color, linestyle='--', linewidth=2,
                                    label=f'{cfg["motor"]}: conditional 95% radius {radius:.0f} m'))
            ax.scatter([r['east_m'] for r in samples], [r['north_m'] for r in samples], s=8, color=color, edgecolors='#172b40', linewidths=.2, zorder=4)
            index = summary['configs'].index(cfg)
            zoom = ax.inset_axes([.085 + .49*index, .085, .34, .19], zorder=8)
            scatter_landing_zoom(zoom, samples, color, compact=True)
            zoom.set_title(f'{cfg["motor"]} landing points · unequal scales', fontsize=7, pad=3)
        ax.scatter([0], [0], marker='+', s=170, color='white', linewidth=3, zorder=5, label='URRG launch point')
        ax.set_title(f'URRG · main only, apogee + 1 s\n{wind_label}', fontsize=13)
        ax.set(xlabel='East of launch (m)', ylabel='North of launch (m)')
        ax.legend(loc='upper right', facecolor='#172b40', labelcolor='white', framealpha=.9, fontsize=9)
        ax.text(.02, .98, 'N ↑', transform=ax.transAxes, va='top', color='white', fontsize=14,
                bbox={'facecolor':'#172b40','alpha':.8,'edgecolor':'none'})
        fig.supxlabel(f'{completion_label}\n{excluded_label}. Circles describe finished flights only.', fontsize=9)
        fig.savefig(args.output/'landing_satellite.png', dpi=190)
        plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--ork', type=Path, default=DEFAULT_ORK)
    p.add_argument('--openrocket-jar', type=Path, required=True)
    p.add_argument('--java-home')
    p.add_argument('--trials', type=int, default=100)
    p.add_argument('--seed', type=int, default=20261011)
    weather = p.add_mutually_exclusive_group()
    weather.add_argument('--wind-speed', type=float, help='Override mean wind in m/s; preserve direction and turbulence intensity.')
    weather.add_argument('--random-wind-max', type=float, help='Sample mean wind uniformly from zero to this speed, with random direction and turbulence.')
    p.add_argument('--turbulence-min', type=float, default=.05)
    p.add_argument('--turbulence-max', type=float, default=.20)
    p.add_argument('--workers', type=int, default=1, help='Number of independent Java workers.')
    p.add_argument('--output', type=Path)
    p.add_argument('--analyze-only', action='store_true', help='Regenerate summaries and plots from existing runs.csv.')
    p.add_argument('--basemap', action='store_true', help='Also download an Esri satellite basemap (requires contextily and rasterio).')
    args=p.parse_args()
    if args.trials < 1: p.error('--trials must be positive')
    if not 1 <= args.workers <= 8: p.error('--workers must be between 1 and 8')
    if not 0 <= args.turbulence_min <= args.turbulence_max <= 1:
        p.error('Require 0 <= turbulence-min <= turbulence-max <= 1')
    if args.random_wind_max is not None and (not np.isfinite(args.random_wind_max) or args.random_wind_max <= 0):
        p.error('--random-wind-max must be finite and positive')
    if args.wind_speed is not None and (not np.isfinite(args.wind_speed) or args.wind_speed < 0):
        p.error('--wind-speed must be finite and nonnegative')
    suffix = '' if args.wind_speed is None else f'_wind{args.wind_speed:g}ms'
    if args.random_wind_max is not None: suffix = f'_randomwind0to{args.random_wind_max:g}ms'
    if args.output is None:
        args.output = HERE/('urrg_no_drogue_20261011'+suffix)
    args.output=args.output.resolve(); args.output.mkdir(parents=True, exist_ok=True)
    if args.analyze_only and (args.output/'run_manifest.json').exists():
        receipt = json.loads((args.output/'run_manifest.json').read_text())
        args.trials = receipt.get('trials_per_motor', args.trials)
        args.seed = receipt.get('first_seed', args.seed)
        args.wind_speed = receipt.get('wind_speed_override_mps', args.wind_speed)
        args.random_wind_max = receipt.get('random_wind_max_mps', args.random_wind_max)
        args.turbulence_min, args.turbulence_max = receipt.get('turbulence_intensity_range', [args.turbulence_min, args.turbulence_max])
    copy=args.output/(args.ork.stem.removesuffix('.URRG')+'.URRG.ork')
    # A source file may be moved after the solver loads it; the saved scenario
    # and preflight hashes allow analysis to finish without changing the design.
    design = copy if args.analyze_only and copy.exists() else args.ork
    root,configs,chute=read_design(design)
    if args.wind_speed is not None:
        override_wind(root, configs, args.wind_speed)
    launch=site()
    if copy.resolve()==args.ork.resolve(): raise ValueError('Refusing to replace source .ork.')
    if not args.analyze_only:
        write_site_copy(args.ork,copy,root,launch)
    cases=args.output/'cases.csv'; results=args.output/'runs.csv'
    if not args.analyze_only:
        write_cases(cases,configs,args.trials,args.seed,args.random_wind_max,args.turbulence_min,args.turbulence_max)
        print(f'Running {args.trials} flights per motor at URRG. {wind_description(args, configs)} Other defaults retained.', flush=True)
        run_engine(args,cases,results,launch)
    rows=read_results(results,launch)
    for cfg in configs:
        actual=sum(r['simulation_index']==cfg['index'] and r['case_id'].startswith('mc_') for r in rows)
        if actual != args.trials: raise ValueError(f'Expected {args.trials} trials, found {actual}.')
    summary=summarize(args,configs,chute,launch,rows)
    plot(args,summary,rows)


if __name__=='__main__':
    main()
