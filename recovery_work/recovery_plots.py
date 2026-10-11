"""Scientific figures for the randomized-weather OpenRocket recovery study."""
import json

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from pyproj import Geod

COLORS = ['#167c80', '#c15d22']


def plot_randomized(args, summary, rows):
    configs = summary['configs']
    samples = [[r for r in rows if r['simulation_index'] == cfg['index']
                and r['case_id'].startswith('mc_') and r['ground_hit']
                and np.isfinite(r['radius_m']) and np.isfinite(r['deployment_time_s'])]
               for cfg in configs]
    trials = [[r for r in rows if r['simulation_index'] == cfg['index']
               and r['case_id'].startswith('mc_')] for cfg in configs]
    weather = (f'Mean wind 0–{args.random_wind_max:g} m/s · direction 0–360° · '
               f'turbulence intensity {args.turbulence_min:.0%}–{args.turbulence_max:.0%}')
    complete = 'Landed / finished: ' + ' · '.join(
        f'{c["motor"]} {c["complete_trials"]}/{c["complete_trials"]}' for c in configs)
    excluded = 'Excluded incomplete: ' + ' · '.join(
        f'{c["motor"]} {c["incomplete_trials"]}' for c in configs)
    footer = f'{complete}  |  {excluded}\nLanding statistics use completed flights only. Assumed weather distributions; no forecast.'
    limit = max([r['radius_m'] for group in samples for r in group] + [10]) * 1.10
    speed_norm = Normalize(0, args.random_wind_max)
    turbulence_norm = Normalize(100*args.turbulence_min, 100*args.turbulence_max)

    def values(group, key):
        return np.array([r[key] for r in group])

    def title(cfg):
        return cfg['motor'] + (' · default motor' if cfg['default_motor'] else '')

    def save(fig, name, heading, note=footer):
        fig.suptitle(heading, fontsize=16, fontweight='bold')
        fig.supxlabel(note, fontsize=9)
        fig.savefig(args.output/name, dpi=190)
        plt.close(fig)

    def pad_axes(ax):
        ax.set(xlim=(-limit, limit), ylim=(-limit, limit), aspect='equal',
               xlabel='East of launch (m)', ylabel='North of launch (m)')
        ax.axhline(0, color='#64748b', lw=.5, alpha=.3)
        ax.axvline(0, color='#64748b', lw=.5, alpha=.3)
        ax.scatter([0], [0], marker='+', s=150, color='#172b40', linewidth=2, zorder=6,
                   label='Launch point')
        ax.grid(alpha=.16)

    fig, axes = plt.subplots(1, 2, figsize=(13, 7), layout='constrained')
    for ax, cfg, group, color in zip(axes, configs, samples, COLORS):
        pad_axes(ax)
        ax.scatter(values(group, 'east_m'), values(group, 'north_m'), s=17,
                   alpha=.65, color=color, linewidths=.25, edgecolors='white',
                   label='One point per landing', zorder=4)
        if group:
            r = cfg['radius_m']
            ax.add_patch(plt.Circle((0, 0), r['p95'], fill=False, color=color,
                                   linestyle='--', linewidth=1.8,
                                   label=f'95th-percentile radius: {r["p95"]:.0f} m'))
            ax.set_title(f'{title(cfg)}\nMedian {r["median"]:.0f} m · central 95% {r["p2_5"]:.0f}–{r["p97_5"]:.0f} m', fontsize=12)
        else:
            ax.set_title(f'{title(cfg)}\nNo completed landings')
        ax.legend(loc='upper right', fontsize=8, framealpha=.95)
    save(fig, 'landing_footprint.png', 'URRG · randomized-wind landing footprint\n'+weather)

    fig, axes = plt.subplots(1, 2, figsize=(13, 7), layout='constrained')
    for ax, cfg, group in zip(axes, configs, samples):
        pad_axes(ax)
        points = ax.scatter(values(group, 'east_m'), values(group, 'north_m'),
                            c=values(group, 'ground_wind_mps'), norm=speed_norm,
                            cmap='viridis', s=23, alpha=.85, linewidths=.2,
                            edgecolors='white', zorder=4)
        ax.set_title(title(cfg), fontsize=13)
    fig.colorbar(points, ax=axes, shrink=.75, label='Sampled mean wind (m/s)')
    save(fig, 'landing_scatter.png', 'URRG · every completed landing, coloured by wind speed\nEqual metre scales on both axes; actual simulated coordinates')

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout='constrained')
    bins = np.linspace(0, limit, 25)
    for cfg, group, color in zip(configs, samples, COLORS):
        if not group: continue
        radii = values(group, 'radius_m')
        axes[0].hist(radii, bins=bins, weights=np.full(len(group), 100/len(group)),
                     histtype='step', linewidth=2, color=color, label=cfg['motor'])
        axes[1].step(np.sort(radii), 100*np.arange(1, len(group)+1)/len(group),
                     where='post', color=color, linewidth=2,
                     label=f'{cfg["motor"]} · 95% radius {cfg["radius_m"]["p95"]:.0f} m')
    axes[0].set(xlabel='Distance from launch (m)', ylabel='Completed landings per bin (%)', title='Landing-distance distribution')
    axes[1].set(xlabel='Radius from launch (m)', ylabel='Completed landings inside radius (%)',
                ylim=(0, 101), title='Cumulative landing distance')
    axes[1].axhline(95, color='#64748b', ls='--', lw=1)
    for ax in axes:
        ax.legend(fontsize=9); ax.grid(alpha=.18)
    save(fig, 'landing_distributions.png', 'URRG · distribution of landing distances\n'+weather)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout='constrained')
    for ax, cfg, group in zip(axes, configs, samples):
        points = ax.scatter(values(group, 'ground_wind_mps'), values(group, 'radius_m'),
                            c=100*values(group, 'turbulence'), norm=turbulence_norm,
                            cmap='plasma', s=19, alpha=.8, linewidths=0)
        ax.set(xlabel='Sampled mean wind (m/s)', ylabel='Distance from launch (m)',
               xlim=(0, args.random_wind_max), ylim=(0, limit), title=title(cfg))
        ax.grid(alpha=.18)
    fig.colorbar(points, ax=axes, shrink=.8, label='Sampled turbulence intensity (%)')
    save(fig, 'landing_vs_wind.png', 'URRG · how sampled wind affects landing distance')

    # Show inputs for all attempts, including weather that caused solver aborts.
    paired = trials[0]
    fig = plt.figure(figsize=(14, 5.5), layout='constrained')
    ax = fig.add_subplot(1, 3, 1, projection='polar')
    counts, edges = np.histogram(np.radians(values(paired, 'wind_from_deg')), bins=np.linspace(0, 2*np.pi, 17))
    ax.bar((edges[:-1]+edges[1:])/2, counts, width=np.diff(edges)*.9, color='#426886', alpha=.8)
    ax.set_theta_zero_location('N'); ax.set_theta_direction(-1)
    ax.set_title('Wind direction FROM\nNumber of sampled flights', pad=20)
    ax.set_xticks(np.arange(8)*np.pi/4, ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
    ax = fig.add_subplot(1, 3, 2)
    ax.hist(values(paired, 'ground_wind_mps'), bins=np.linspace(0, args.random_wind_max, 11), color='#426886', edgecolor='white')
    ax.set(xlabel='Mean wind (m/s)', ylabel='Number of sampled flights', title='Uniform mean speed')
    ax.grid(axis='y', alpha=.15)
    ax = fig.add_subplot(1, 3, 3)
    ax.hist(100*values(paired, 'turbulence'), bins=np.linspace(100*args.turbulence_min, 100*args.turbulence_max, 11), color='#426886', edgecolor='white')
    ax.set(xlabel='Turbulence intensity (%)', ylabel='Number of sampled flights', title='Uniform turbulence intensity')
    ax.grid(axis='y', alpha=.15)
    save(fig, 'wind_inputs.png', 'URRG · sampled weather inputs',
         f'{len(paired)} weather samples, each simulated with both motors. Stratified uniform sampling; native pink-noise speed variation within flights.\n'
         'Direction and mean speed are fixed within each flight and across altitude. Instantaneous gusts can exceed the mean-speed cap.')

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout='constrained')
    for ax, cfg, group, attempted, color in zip(axes, configs, samples, trials, COLORS):
        completed_ids = {r['case_id'] for r in group}
        incomplete = [r for r in attempted if r['case_id'] not in completed_ids]
        ax.hist([values(group, 'ground_wind_mps'), values(incomplete, 'ground_wind_mps')],
                bins=np.linspace(0, args.random_wind_max, 11), stacked=True,
                color=[color, '#b6bec8'], edgecolor='white', label=['Finished', 'Excluded incomplete'])
        ax.set(xlabel='Sampled mean wind (m/s)', ylabel='Number of attempted simulations', title=title(cfg))
        ax.legend(); ax.grid(axis='y', alpha=.16)
    save(fig, 'simulation_completion.png', 'URRG · completed and excluded simulations by wind speed',
         f'{complete}  |  {excluded}\nThe 1 m rail is unchanged. Solver abort counts are not a quantified physical failure probability.')

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    metrics = [('apogee_m', 'Apogee above launch (m)'), ('descent_time_s', 'Apogee-to-ground time (s)'),
               ('vertical_landing_mps', 'Vertical touchdown speed (m/s)'), ('deployment_speed_mps', 'Speed at main deployment (m/s)')]
    for ax, (key, label) in zip(axes.flat, metrics):
        metric_values = [(values(group, 'flight_time_s')-values(group, 'apogee_time_s')
                          if key == 'descent_time_s' else values(group, key)) for group in samples]
        combined = np.concatenate(metric_values)
        edges = np.histogram_bin_edges(combined, bins=32)
        for cfg, group, data, color in zip(configs, samples, metric_values, COLORS):
            if not group: continue
            ax.hist(data, bins=edges, weights=np.full(len(group), 100/len(group)), histtype='step',
                    color=color, linewidth=1.8, label=cfg['motor'])
        ax.set(xlabel=label, ylabel='Completed flights per bin (%)')
        ax.legend(fontsize=9); ax.grid(alpha=.16)
    save(fig, 'flight_metrics.png', 'URRG · simulated flight and recovery metrics\nNo drogue · main at apogee + 1 s · unchanged 1 m rail')

    launch = summary['launch_site']
    features = [{'type': 'Feature', 'properties': {'name': 'URRG launch', 'MGRS': launch['mgrs']},
                 'geometry': {'type': 'Point', 'coordinates': [launch['longitude_deg'], launch['latitude_deg']]}}]
    geod = Geod(ellps='WGS84')
    for cfg, group in zip(configs, samples):
        if not group: continue
        ring = [list(geod.fwd(launch['longitude_deg'], launch['latitude_deg'], az, cfg['radius_m']['p95'])[:2])
                for az in np.linspace(0, 360, 181)]
        ring[-1] = ring[0]
        features.append({'type': 'Feature', 'properties': {'motor': cfg['motor'], 'radius_p95_m': cfg['radius_m']['p95'],
                         'complete_trials': len(group), 'incomplete_trials': cfg['incomplete_trials'],
                         'scope': 'Conditional on completed simulations under the sampled weather assumptions'},
                         'geometry': {'type': 'Polygon', 'coordinates': [ring]}})
        for r in group:
            features.append({'type': 'Feature', 'properties': {'motor': cfg['motor'], 'case_id': r['case_id'],
                             'mean_wind_mps': r['ground_wind_mps'], 'wind_from_deg': r['wind_from_deg'],
                             'turbulence': r['turbulence'], 'radius_m': r['radius_m']},
                             'geometry': {'type': 'Point', 'coordinates': [r['longitude_deg'], r['latitude_deg']]}})
    (args.output/'landing_radii.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, indent=2)+'\n')

    if args.basemap and any(samples):
        import contextily as ctx
        crs = f'+proj=aeqd +lat_0={launch["latitude_deg"]} +lon_0={launch["longitude_deg"]} +datum=WGS84 +units=m'
        fig, ax = plt.subplots(figsize=(10, 10), layout='constrained')
        ax.set(xlim=(-limit, limit), ylim=(-limit, limit), aspect='equal',
               xlabel='East of launch (m)', ylabel='North of launch (m)')
        ctx.add_basemap(ax, crs=crs, source=ctx.providers.Esri.WorldImagery, zoom=17, attribution_size=6)
        for cfg, group, color in zip(configs, samples, ['#52e4ec', '#ffb860']):
            if not group: continue
            radius = cfg['radius_m']['p95']
            ax.add_patch(plt.Circle((0, 0), radius, fill=False, color=color, linestyle='--', linewidth=2,
                                   label=f'{cfg["motor"]} · conditional 95% radius {radius:.0f} m'))
            ax.scatter(values(group, 'east_m'), values(group, 'north_m'), s=17, color=color,
                       edgecolors='#172b40', linewidths=.3, alpha=.85, zorder=4)
        ax.scatter([0], [0], marker='+', s=200, color='white', linewidth=3, zorder=5, label='URRG launch point')
        ax.legend(loc='upper right', facecolor='#172b40', labelcolor='white', framealpha=.95, fontsize=9)
        ax.text(.02, .98, 'N ↑', transform=ax.transAxes, va='top', color='white', fontsize=14,
                bbox={'facecolor': '#172b40', 'alpha': .8, 'edgecolor': 'none'})
        save(fig, 'landing_satellite.png', 'URRG · simulated landings on satellite imagery\n'+weather)
