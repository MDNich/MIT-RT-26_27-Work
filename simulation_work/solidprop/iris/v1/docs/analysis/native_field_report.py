"""Native baseline temperature maps from accepted checkpoint fields only."""
import gzip
import hashlib
import json
import numpy as np
import matplotlib.pyplot as plt


def corrected_fields(root,out,captured,runs):
    if not runs:return ''
    data=[]
    for run in runs:
        cfg=run['configuration'];g=cfg['geometry']
        assert cfg.get('native_reaction_temperature')=='midpoint'
        nph=g['phenolic_radial_rows'];nc=g['aluminium_radial_rows']
        plane=(g['angular_divisions']+1)*(g['axial_divisions']+1)
        runtime=root/'ansystmp/runs'/run['name']
        times=[0.];temperatures=[[cfg['initial_temperature_C']]*(nph+nc+1)]
        removed=[0.];hashes=[]
        for index,a in enumerate(run['history'],1):
            assert a['native_load_step']==index and a['native_substep']==1
            path=runtime/'checkpoints'/f'state_{index:06d}.json.gz'
            with gzip.open(path,'rt') as f:s=json.load(f)
            values=[float(np.mean([s['temperatures'][str(1+j*plane+k)] for k in range(plane)])) for j in range(nph+nc+1)]
            # Mask only rows already inactive during this solve, not a pending kill.
            values[:a['rows_removed']]=[None]*a['rows_removed']
            times.append(a['time_s']);temperatures.append(values)
            removed.append(a['rows_removed']*g['phenolic_thickness_m']*1000/nph)
            hashes.append(dict(index=index,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        x=np.r_[np.linspace(0,1000*g['phenolic_thickness_m'],nph+1),
                np.linspace(1000*g['phenolic_thickness_m'],1000*(g['outer_radius_m']-g['inner_radius_m']),nc+1)[1:]]
        data.append(dict(runtime=run['name'],case=run['case'],through_s=run['accepted_time_s'],
            config_sha256=run['config_sha256'],depth_mm=x.tolist(),time_s=times,
            temperature_C=temperatures,removed_depth_mm=removed,
            phenolic_thickness_mm=1000*g['phenolic_thickness_m'],checkpoint_hashes=hashes))
    path=out/'native_corrected_fields.json'
    path.write_text(json.dumps(dict(qualification='Accepted corrected-midpoint ANSYS fields; null denotes inactive nodes; no future states',cases=data),separators=(',',':'),allow_nan=False)+'\n')
    captured.append(dict(file=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    fig,axes=plt.subplots(len(data),2,figsize=(8.4,min(9.6,2.6*len(data)+.6)),squeeze=False,constrained_layout=True)
    for panels,d in zip(axes,data):
        T=np.array(d['temperature_C'],dtype=float)
        for ax,heating_only in zip(panels,[True,False]):
            mesh=ax.pcolormesh(d['depth_mm'],d['time_s'],np.ma.masked_invalid(T),
                shading='nearest',cmap='inferno',vmin=22,vmax=1600,rasterized=True)
            ax.axvline(d['phenolic_thickness_mm'],color='white',ls='--',lw=.8)
            ax.plot(d['removed_depth_mm'],d['time_s'],color='#23e5e5',lw=.8)
            ax.set(xlabel='Depth from original bore [mm]',ylabel='Time [s]',
                ylim=(0,min(7,d['through_s']) if heating_only else d['through_s']),
                title=d['case'].replace('_',' ').title().replace('Cf','CF')+(': heating' if heating_only else ': full history'))
    fig.colorbar(mesh,ax=axes,label=r'Temperature [$^\circ$C]',shrink=.85)
    fig.suptitle('Corrected native fields; dashed casing interface, cyan removed depth')
    fig.savefig(out/'native_corrected_temperature_maps.pdf',dpi=220)
    fig.savefig(out/'native_corrected_temperature_maps.png',dpi=180);plt.close(fig)
    return r'''\subsection{Corrected native temperature fields}
Each map uses accepted corrected-midpoint ANSYS checkpoints only. The left panel resolves the imposed seven-second heating interval; the right panel shows the full accepted history, including heat soak and cooling. The dashed line marks the casing interface, while cyan marks the depth already removed during the solve. Inactive nodes are masked. Temperatures are radial-station averages of the small uniform sector; these are computed fields, not measurements.
\begin{figure}[H]\centering\includegraphics[width=\textwidth,height=.76\textheight,keepaspectratio]{../analysis/native_corrected_temperature_maps.pdf}\caption{Corrected native temperature fields with a common scale. No time beyond an accepted checkpoint is shown.}\end{figure}'''


def create(root,out,captured):
    cases=['sustainer_al','sustainer_cf','booster_al','booster_cf'];data=[]
    for case in cases:
        name=case+'_baseline7_n20_dt0125';record=root/'validation'/('accepted_'+name+'.json')
        if not record.exists():return ''
        accepted=json.loads(record.read_text())
        if not accepted['passed'] or accepted['time_s']!=7:return ''
        runtime=root/'ansystmp/runs'/name;cfg=json.loads((runtime/'config.json').read_text());g=cfg['geometry']
        nph=g['phenolic_radial_rows'];nc=g['aluminium_radial_rows'];plane=(g['angular_divisions']+1)*(g['axial_divisions']+1);nf=g['faces_per_row']
        times=[0.];temps=[[cfg['initial_temperature_C']]*(nph+nc+1)];alpha=[[0.]*nph];fronts=[0.];hashes=[]
        for index in range(1,accepted['accepted_steps']+1):
            p=runtime/'checkpoints'/f'state_{index:06d}.json.gz'
            with gzip.open(p,'rt') as f:s=json.load(f)
            times.append(s['time_s'])
            temps.append([float(np.mean([s['temperatures'][str(1+j*plane+k)] for k in range(plane)])) for j in range(nph+nc+1)])
            a=[float(np.mean([s['alpha'][str(1+j*nf+k)] for k in range(nf)])) for j in range(nph)]
            alpha.append(a);front=s['layer']
            while front<nph and a[front]>=.98:front+=1
            fronts.append(front*g['phenolic_thickness_m']*1000/nph)
            hashes.append(dict(index=index,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        x=np.r_[np.linspace(0,1000*g['phenolic_thickness_m'],nph+1),np.linspace(1000*g['phenolic_thickness_m'],1000*(g['outer_radius_m']-g['inner_radius_m']),nc+1)[1:]]
        data.append(dict(case=case,runtime=name,config_sha256=hashlib.sha256((runtime/'config.json').read_bytes()).hexdigest(),
            depth_mm=x.tolist(),phenolic_thickness_mm=1000*g['phenolic_thickness_m'],time_s=times,
            temperature_C=np.round(temps,6).tolist(),mean_conversion=np.round(alpha,8).tolist(),
            conversion98_upper_cell_depth_mm=fronts,checkpoint_hashes=hashes))
        captured.append(dict(file=str(record.relative_to(root)),sha256=hashlib.sha256(record.read_bytes()).hexdigest()))
    path=out/'native_baseline_fields.json'
    path.write_text(json.dumps(dict(qualification='Native accepted 20-row baseline fields for visualization; temperature rounded to six decimal places and conversion to eight; original checkpoints govern audits',cases=data),separators=(',',':'))+'\n')
    fig,axes=plt.subplots(2,2,figsize=(8.4,5.7),constrained_layout=True)
    for ax,d in zip(axes.flat,data):
        mesh=ax.pcolormesh(d['depth_mm'],d['time_s'],d['temperature_C'],shading='gouraud',cmap='inferno',vmin=22,vmax=1200,rasterized=True)
        ax.axvline(d['phenolic_thickness_mm'],color='white',ls='--',lw=.8)
        ax.plot(d['conversion98_upper_cell_depth_mm'],d['time_s'],color='#23e5e5',lw=1.)
        ax.set(title=d['case'].replace('_',' ').title().replace('Cf','CF'),xlabel='Depth from original bore [mm]',ylabel='Exposure time [s]',ylim=(0,7))
    fig.colorbar(mesh,ax=axes,label=r'Temperature [$^\circ$C]',shrink=.85)
    fig.suptitle('Historical inherited-routine baselines; dashed interface, cyan conversion front')
    fig.savefig(out/'native_baseline_temperature_maps.pdf',dpi=220)
    fig.savefig(out/'native_baseline_temperature_maps.png',dpi=180);plt.close(fig)
    captured.append(dict(file=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return r'''\subsection{Native temperature fields over the baseline exposure}
These historical maps use every accepted checkpoint of the four original twenty-row native baselines, which used the inherited reaction-temperature expression. They are not predictions of the corrected midpoint model. Temperatures are averaged over each radial station of the uniform sector and interpolated for display. The dashed line marks the liner--casing interface. The cyan line is the upper-cell edge of the contiguous 98-percent conversion front; it is neither recession nor burnthrough. All four coarse baselines retain every liner row through seven seconds, despite nonzero gas and char losses.
\begin{figure}[H]\centering\includegraphics[width=\textwidth]{../analysis/native_baseline_temperature_maps.pdf}\caption{Native ANSYS baseline temperature fields, with a common temperature scale. These coarse-mesh fields are accepted numerical states; the recession discretization still requires the refined comparisons.}\end{figure}'''
