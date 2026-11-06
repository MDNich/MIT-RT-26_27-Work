"""Read native terminal-window files and independently reconcile energy, surface recession and remap."""
import argparse
import json
import math
from pathlib import Path
import re

import numpy as np

from continuous_heating_campaign import digest
from coupler import blowing,char_rate
from moving_surface_remap import remap
from ops import ROOT,TMP,atomic,disks,utc
from prepare_native_cf_tail import PACKAGE, PLAN, RHO, H, TEMP, dual, step_reference

JOBS=('tails204','tails404','tails402','tailb204','tailb404','tailb402')


def sources(job):
    manifest=json.loads((PACKAGE/'manifest.json').read_text())
    p=PACKAGE/(job+'.json')
    if digest(p)!=manifest['jobs'][job]: raise ValueError('Tail comparison has changed')
    e=json.loads(p.read_text())
    cfg=next(row['configuration'] for row in json.loads(PLAN.read_text())['cases']
             if row['case']==e['case'] and row['variant']=='fine')
    return e,cfg


def evaluate(e,cfg,steps,field,radial_history=None):
    n,ring,nn=e['n'],e['ringsize'],e['nodes']
    if steps.ndim!=2 or steps.shape[1]!=8 or not len(steps) or field.shape!=(nn*len(steps),4):
        raise ValueError('Incomplete native CF tail data')
    if not np.isfinite(steps).all() or not np.isfinite(field).all(): raise ValueError('Nonfinite native value')
    g=e['geometry']
    nt,ny=g['angular_divisions'],g['axial_divisions']
    scale=nt*math.sin(math.radians(g['angle_deg'])/nt)*g['length_m']
    angular=np.ones(nt+1);angular[[0,-1]]=.5
    axial=np.ones(ny+1);axial[[0,-1]]=.5
    weights=np.outer(angular,axial).ravel()/(nt*ny)
    heating=cfg['heating']; facet=e['facet_cos']
    last,ro=e['radius_m']
    t0=np.repeat(np.array(e['initial_nodal_C'])[:,None],ring,axis=1)
    trace=np.array(e['backing_trace']);ref=e['reference']
    times=[0.]+[v['time_s'] for v in ref]
    if radial_history is None:
        pairs=[]
        step_reference(cfg,n,e['dt'],e['initial_nodal_C'],trace,facet,last,ro,fields=pairs)
        radial_history=np.array([e['initial_nodal_C']]+[end.tolist() for _,end in pairs])
    if radial_history.shape!=(len(times),n+1): raise ValueError('Missing matched reference fields')
    hot_error=0.
    elapsed=mass_spent=energy_error=absolute_energy=max_map=max_field=max_spread=max_mass=0.
    original=RHO*.5*(ro-last)*(ro+last)
    for i,line in enumerate(steps):
        step,time,dt,native_dt,r,rnew,rate,outer=line
        if not (step==i+1 and dt>0. and dt<=e['dt']+1e-8 and abs(time-elapsed-dt)<2e-8 and
                abs(native_dt-dt)<1e-9 and abs(last-r)<8e-11 and r<rnew<=ro+8e-11):
            raise ValueError('Native radius/time is discontinuous')
        if abs(rnew-ro)<8e-11 and i==len(steps)-1: rnew=ro
        block=field[i*nn:(i+1)*nn]
        if not (np.all(block[:,0]==step) and np.array_equal(block[:,1],np.arange(1,nn+1))):
            raise ValueError('Wrong field node/step')
        begin,end=(block[:,j].reshape(n+1,ring) for j in (2,3))
        max_map=max(max_map,float(np.max(abs(begin-t0))))
        target_rate=char_rate(np.mean(begin[0]),cfg['char_law'])
        if abs(target_rate-rate)>2e-8*target_rate or abs(rnew-r-rate*dt/(RHO*facet))>1.5e-10:
            raise ValueError('Native kinetics or applied motion differs')
        bc=np.interp(time,trace[:,0],trace[:,1])
        if max(abs(end[-1]-bc))>1e-4: raise ValueError('Backing history differs')
        hot=float(end[0]@weights)
        # Compare at a common physical time and normalized remaining-wall depth.
        # The reference's last profile is retained if the native event is later.
        index=int(np.clip(np.searchsorted(times,time),1,len(times)-1))
        blend=np.clip((time-times[index-1])/(times[index]-times[index-1]),0.,1.)
        expected=(1.-blend)*radial_history[index-1]+blend*radial_history[index]
        max_field=max(max_field,float(np.max(abs(end-expected[:,None]))))
        hot_error=max(hot_error,abs(hot-expected[0]))
        max_spread=max(max_spread,float(np.ptp(end,axis=1).max()))
        film=blowing(heating['h0_W_m2_K'],rate,heating['gas_cp_J_kg_K'])
        qhot=(film*(heating['gas_temperature_C']-hot)-cfg['char_law']['effective_endothermic_cost_J_kg']*rate)*r/facet
        edges=dual(np.linspace(r,ro,n+1))
        vol=np.diff(edges)*(edges[:-1]+edges[1:])/2.
        hb,he=np.interp(begin,TEMP,H),np.interp(end,TEMP,H)
        added=dt*(qhot+outer/scale)
        energy_error+=abs(vol@((he-hb)@weights)-added)
        absolute_energy+=dt*(abs(qhot)+abs(outer/scale))
        mass_spent+=.5*(r+rnew)/facet*dt*rate
        max_mass=max(max_mass,abs(RHO*(ro-rnew)*(ro+rnew)/2.+mass_spent-original)/original)
        targets=np.array([ro]) if rnew==ro else dual(np.linspace(rnew,ro,n+1))
        transfer=remap(edges,he.T,targets)
        if np.max(abs(transfer.balance_residual))>1e-6: raise ValueError('Energy remap is unclosed')
        t0=np.interp(transfer.density.T,H,TEMP)
        elapsed,last=time,rnew
    limits=e['thresholds']
    energy=energy_error/max(absolute_energy,1.)
    event_error=abs(elapsed/e['reference_event_s']-1.)
    if (last!=ro or max_map>.02 or max_spread>.1 or max_mass>limits['mass_relative'] or
            energy>limits['energy_relative'] or event_error>limits['event_relative'] or max_field>limits['temperature_K']):
        raise ValueError(f'Tail thresholds failed: map {max_map:g}, spread {max_spread:g}, mass {max_mass:g}, '
                         f'energy {energy:g}, event {event_error:g}, hot field {max_field:g}')
    return dict(passed=True,remaining_time_s=elapsed,increment_count=len(steps),max_mass_relative=max_mass,
                absolute_energy_error_fraction=energy,event_relative=event_error,max_hot_error_K=hot_error,max_all_node_error_K=max_field,
                max_ring_spread_K=max_spread,max_remap_error_K=max_map)


def fixture(job):
    e,cfg=sources(job)
    g=e['geometry']
    scale=g['angular_divisions']*math.sin(math.radians(g['angle_deg'])/g['angular_divisions'])*g['length_m']
    raw=[]
    history=step_reference(cfg,e['n'],e['dt'],e['initial_nodal_C'],np.array(e['backing_trace']),e['facet_cos'],*e['radius_m'],fields=raw)
    r=e['radius_m'][0]
    steps,fields=[],[]
    for i,(h,(before,after)) in enumerate(zip(history,raw),1):
        steps.append([i,h['time_s'],h['dt_s'],h['dt_s'],r,h['hot_radius_m'],h['rate_kg_m2_s'],h['back_power_W_per_rad_m']*scale])
        r=h['hot_radius_m']
        fields.append(np.column_stack((np.full(e['nodes'],i),np.arange(1,e['nodes']+1),
                                       np.repeat(before,e['ringsize']),np.repeat(after,e['ringsize']))))
    # Match the finite-width APDL exports used by the real deck.
    steps=np.array([[float(f'{v:.9E}') for v in line] for line in steps])
    field=np.concatenate(fields)
    ref=np.array([e['initial_nodal_C']]+[b.tolist() for _,b in raw])
    result=evaluate(e,cfg,steps,field,ref)
    for name,col,change in [('energy',7,1.),('rate',6,.001),('clock',2,.01)]:
        bad=steps.copy();bad[len(bad)//2,col]+=change
        try: evaluate(e,cfg,bad,field,ref)
        except ValueError: continue
        raise RuntimeError(f'Tail reader accepted damaged {name}')
    return result


def audit(job,run):
    e,cfg=sources(job)
    receipt=json.loads((run/'guest_terminal.json').read_text(encoding='utf-8-sig'))
    assert receipt['job']==job and receipt['exit_code']==0 and receipt['guest_input_sha256'].lower()==e['deck_sha256']
    assert digest(run/(job+'.inp'))==e['deck_sha256']
    files=[job+'.out','tail_steps.txt','tail_field.txt']
    for f in files: assert digest(run/f)==receipt['guest_sha256'][f].lower()
    log=(run/files[0]).read_text(errors='replace')
    assert 'IRIS_CF_TAIL_EXHAUSTED' in log and 'RUN COMPLETED' in log
    for kind in ('WARNING','ERROR'):
        assert re.findall(rf'NUMBER OF {kind}\s+MESSAGES ENCOUNTERED=\s*(\d+)',log)==['0'] and f'*** {kind} ***' not in log
    for key,pat in [('Number of processes requested',r'1\b'),('Number of threads per process requested',r'10\b'),
                    ('Total number of cores requested',r'10\s*\(Shared Memory Parallel\)')]:
        assert re.search(key+r'\s*:\s*'+pat,log)
    result=evaluate(e,cfg,np.loadtxt(run/files[1]),np.loadtxt(run/files[2]))
    result.update(utc=utc(),files={f:digest(run/f) for f in files},terminal_sha256=digest(run/'guest_terminal.json'),
                  comparison_sha256=digest(PACKAGE/(job+'.json')),scope=e['scope'].split('; no native result')[0])
    atomic(ROOT/'validation'/('native_cf_terminal_window_'+job+'.json'),result)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('fixture',))
    parser.parse_args()
    disks()
    result={job:fixture(job) for job in JOBS}
    atomic(ROOT/'validation/cf_tail_reader_fixtures.json',dict(scope='Synthetic histories only, no native output.',
           preflight=result,source_sha256=digest(Path(__file__)),manifest_sha256=digest(PACKAGE/'manifest.json')))
