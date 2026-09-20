"""Partitioned thermal/char coupling, called by MAPDL only between solves.

Standard library only. All runtime files belong to this iteration. `prepare`
does not solve anything. `accept` checks actual converged MAPDL field exports.
"""
from pathlib import Path
import argparse
import csv
import json
import math
import os
import traceback
import hashlib
import sys

SIGMA = 5.670374419e-8
R = 8.314462618


def atomic(path, value):
    path=Path(path)
    temporary=path.with_suffix(path.suffix+'.new')
    temporary.write_text(value,encoding='utf-8')
    os.replace(temporary,path)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path,value):
    atomic(path,json.dumps(value,indent=2,allow_nan=False))


def fingerprint(c):
    return hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()


def validate_config(c):
    assert c['qualification']=='EXPLORATORY_NOT_CALIBRATED' or c['char_law']['calibrated']
    assert c['end_time_s']>0 and 0<c['minimum_dt_s']<=c['macro_dt_s']
    assert c['ranks']==10
    g=c['geometry']
    assert g['phenolic_radial_rows']>0 and g['faces_per_row']>0
    assert math.isclose(g['phenolic_outer_radius_m']-g['inner_radius_m'],
                        g['phenolic_thickness_m'],rel_tol=0,abs_tol=1e-12)
    assert math.isclose(g['outer_radius_m']-g['phenolic_outer_radius_m'],
                        g['aluminium_thickness_m'],rel_tol=0,abs_tol=1e-12)
    m=c['material']; law=c['char_law']; h=c['heating']; n=c['numerics']
    assert 0<m['char_reference_density_kg_m3']<m['virgin_reference_density_kg_m3']
    assert law['effective_endothermic_cost_J_kg']>0
    assert law['mode'] in ('effective_exploratory','species')
    assert law['pressure_Pa'] is None or law['pressure_Pa']>=0
    for key in ('exploratory_pressure_ratio','reactive_activity','reference_rate_kg_m2_s',
                'activation_energy_J_mol','pressure_exponent','mass_transfer_cap_kg_m2_s'):
        assert law[key]>=0,key
    assert law['reference_temperature_K']>0 and law['pressure_reference_Pa']>0
    assert 0<n['row_residual_mass_fraction']<.01
    assert 0<n['max_char_fraction_per_step']<=.25
    assert h['gas_temperature_C']>-273.15 and h['h0_W_m2_K']>0
    assert 0<=h['hot_effective_emissivity']<=1 and 0<=h['outer_emissivity']<=1
    if law['mode']=='species':
        assert law['pressure_Pa'] is not None,'Species model needs an explicit chamber pressure.'
        assert law['species'],'Species model needs supplied reactant mole fractions and kinetics.'
        assert sum(x['mole_fraction'] for x in law['species'])<=1+1e-12
        for s in law['species']:
            assert s['name'] in ('H2O','CO2','O2') and 0<=s['mole_fraction']<=1
            for key in ('reference_rate_kg_m2_s','activation_energy_J_mol',
                        'pressure_exponent','mass_transfer_cap_kg_m2_s'):
                assert s[key]>=0


def char_rate(T_C,law):
    """Carbon consumption flux, kg m^-2 s^-1; no conversion cutoff at 0.99.

    Each effective channel combines kinetics and mass-transfer resistance.
    Positive H_eff represents an endothermic effective removal cost only.
    Species mode is a configurable engineering closure, not equilibrium chemistry.
    """
    T=T_C+273.15
    if T<=0: raise ValueError('Nonphysical absolute temperature')
    p=law['pressure_Pa']
    ratio=p/law['pressure_reference_Pa'] if p is not None else law['exploratory_pressure_ratio']
    channels=law['species'] if law['mode']=='species' else [law]
    total=0.0
    for s in channels:
        activity=s.get('mole_fraction',law['reactive_activity'])
        if ratio<=0 or activity<=0: continue
        partial=ratio*activity
        exponent=-s['activation_energy_J_mol']/R*(1/T-1/law['reference_temperature_K'])
        kinetics=s['reference_rate_kg_m2_s']*math.exp(max(-700,min(100,exponent)))*partial**s['pressure_exponent']
        transport=s['mass_transfer_cap_kg_m2_s']*partial
        if kinetics>0 and transport>0:
            total+=1/(1/kinetics+1/transport)
    return total


def blowing(h0,gflux,cp):
    b=max(gflux,0)*cp/h0
    if b<1e-7: return h0*(1-b/2+b*b/12)
    if b>700: return 0.0
    return h0*b/math.expm1(b)


def face_temperature(f,temperatures,initial):
    return sum(temperatures.get(str(n),initial) for n in f['nodes'])/4


def initial_state(mesh,c):
    rho=c['material']['virgin_reference_density_kg_m3']
    return dict(config_sha256=fingerprint(c),index=0,time_s=0.0,layer=0,alpha={},temperatures={},char_consumed={},
                mass_initial_kg=sum(e['volume']*rho for e in mesh['elements'].values() if e['mat']==1),
                gas_cumulative_kg=0.0,char_cumulative_kg=0.0,residual_ejected_kg=0.0,
                removed_mesh_energy_J=0.0,energy_integrals={},gas_rate_kg_s=0.0,
                radial_flux={},status='PREPARED_NOT_STARTED',pending_kills=[],warnings=[])


def prepare_step(mesh,c,s):
    h=c['heating']; m=c['material']; n=c['numerics']
    layer=s['layer']; row=mesh['rows'][layer]
    area=sum(f['area'] for f in row)
    hfilm=blowing(h['h0_W_m2_K'],(s['gas_rate_kg_s']+s.get('char_rate_kg_s',0.))/area,h['gas_cp_J_kg_K'])
    dt=min(c['macro_dt_s'],c['end_time_s']-s['time_s'])
    commands=['ALLSEL,ALL','FDELE,ALL,HEAT','ESEL,S,TYPE,,1,4',
              'SFEDELE,ALL,ALL,CONV','ALLSEL,ALL']
    # Re-apply only newly pending row removals after restoring a converged DB.
    # Existing dead rows already belong to that restart DB.
    for eid in s['pending_kills']: commands.append(f'EKILL,{eid}')
    commands+=['ESEL,S,TYPE,,1,4','ESEL,R,LIVE']
    forces={}; faces=[]
    totals=dict(hot_radiation_W=0.,outer_radiation_W=0.,ablation_sink_W=0.,char_rate_kg_s=0.)
    for f in row:
        eid=str(f['element']); T=face_temperature(f,s['temperatures'],c['initial_temperature_C'])
        alpha=s['alpha'].get(eid,0.)
        consumed=s['char_consumed'].get(eid,0.)
        char_total=m['char_reference_density_kg_m3']*f['volume']
        char_available=max(alpha*char_total-consumed,0.)
        qconv=hfilm*(h['gas_temperature_C']-T)
        qrad=h['hot_effective_emissivity']*SIGMA*((h['radiative_temperature_C']+273.15)**4-(T+273.15)**4)
        # Conduction estimate comes from the previous converged row flux.
        # Pyrolysis and gas sensible sinks already act inside UserMatTh.
        qcond=s['radial_flux'].get(eid,0.)
        energy_cap=max(qconv+qrad-qcond,0.)/c['char_law']['effective_endothermic_cost_J_kg']
        flux=min(alpha*char_rate(T,c['char_law']),energy_cap,
                 char_available/(dt*f['area']),n['max_char_fraction_per_step']*char_total/(dt*f['area']))
        char_power=flux*f['area']*c['char_law']['effective_endothermic_cost_J_kg']
        extra=qrad*f['area']-char_power
        for nid in f['nodes']: forces[nid]=forces.get(nid,0.)+extra/4
        commands += [f'SFE,{f["element"]},{f["face"]},CONV,0,{hfilm:.16e}',
                     f'SFE,{f["element"]},{f["face"]},CONV,2,{h["gas_temperature_C"]:.16e}']
        faces.append(dict(element=f['element'],area=f['area'],T_C=T,h=hfilm,
                          char_rate=flux*f['area'],char_available=char_available,
                          qconv=qconv,qrad=qrad,qcond_est=qcond))
        totals['hot_radiation_W']+=qrad*f['area']
        totals['ablation_sink_W']+=char_power
        totals['char_rate_kg_s']+=flux*f['area']
    for f in mesh['outer']:
        T=face_temperature(f,s['temperatures'],c['initial_temperature_C'])
        qrad=h['outer_emissivity']*SIGMA*((h['ambient_temperature_C']+273.15)**4-(T+273.15)**4)
        for nid in f['nodes']: forces[nid]=forces.get(nid,0.)+qrad*f['area']/4
        commands += [f'SFE,{f["element"]},{f["face"]},CONV,0,{h["outer_h_W_m2_K"]:.16e}',
                     f'SFE,{f["element"]},{f["face"]},CONV,2,{h["ambient_temperature_C"]:.16e}']
        totals['outer_radiation_W']+=qrad*f['area']
    commands+=['ALLSEL,ALL']+[f'F,{nid},HEAT,{val:.16e}' for nid,val in sorted(forces.items())]
    commands+=['ALLSEL,ALL']
    p=dict(index=s['index']+1,layer=layer,start=s['time_s'],target=s['time_s']+dt,dt=dt,
           area=area,faces=faces,forces=forces,totals=totals,
           loaded_hot_faces=len(row),loaded_outer_faces=len(mesh['outer']),
           loaded_hot_nodes=len(set(n for f in row for n in f['nodes'])))
    expected_nodes=(c['geometry']['axial_divisions']+1)*(c['geometry']['angular_divisions']+1)
    assert p['loaded_hot_faces']==c['geometry']['faces_per_row']
    assert p['loaded_hot_nodes']==expected_nodes
    assert math.isclose(sum(forces.values()),totals['hot_radiation_W']+totals['outer_radiation_W']-totals['ablation_sink_W'],abs_tol=1e-10)
    return p,'\n'.join(commands)+'\n'


def read_rows(path):
    values={}
    for line in Path(path).read_text().splitlines():
        p=line.split()
        if not p: continue
        nums=[float(x.replace('D','E')) for x in p]
        if not all(math.isfinite(x) for x in nums): raise ValueError('Nonfinite solver output')
        key=str(int(nums[0]))
        if key in values: raise ValueError('Duplicate solver output ID '+key)
        values[key]=nums[1:]
    return values


def accept_step(mesh,c,s,p,temperatures,fields,energy,time):
    if abs(time-p['target'])>1e-8: raise ValueError('Solved time does not match target')
    if time<=s['time_s']: raise ValueError('Solved time did not advance')
    m=c['material']; n=c['numerics']; rv=m['virgin_reference_density_kg_m3']; rc=m['char_reference_density_kg_m3']
    # Every active solid must have an export; dead solids must not reappear.
    dead={str(f['element']) for row in mesh['rows'][:p['layer']] for f in row}
    expected=set(mesh['elements'])-dead
    if set(fields)!=expected or set(energy)!=expected: raise ValueError('Missing, duplicate or resurrected solid fields')
    if any(len(v)!=4 for v in fields.values()) or any(len(v)!=5 for v in energy.values()):
        raise ValueError('Truncated solver fields')
    used_nodes={str(nid) for f in mesh['rows'][p['layer']]+mesh['outer'] for nid in f['nodes']}
    if not used_nodes.issubset(temperatures): raise ValueError('Missing exposed-face nodal temperatures')
    s=json.loads(json.dumps(s))
    pyro_power=gas_power=0.; gas_delta=0.; live_mesh_mass=0.
    for eid,e in mesh['elements'].items():
        if e['mat']!=1 or eid in dead: continue
        a,gas,gsens,qz=fields[eid]
        old=s['alpha'].get(eid,0.)
        if a<-1e-8 or a>1+1e-8 or a<old-1e-7: raise ValueError('Invalid/descending pyrolysis state '+eid)
        a=min(1.,max(0.,a)); rho=rv-(rv-rc)*a
        gas_delta+=(rv-rc)*(a-old)*e['volume']
        pyro_power+=rho*m['pyrolysis_enthalpy_J_kg']*(a-old)/p['dt']*e['volume']
        gas_power+=rho*gsens*e['volume']
        live_mesh_mass+=rho*e['volume']
        s['alpha'][eid]=a
        s['radial_flux'][eid]=qz
    for f in p['faces']:
        eid=str(f['element']); delta=f['char_rate']*p['dt']
        s['char_consumed'][eid]=s['char_consumed'].get(eid,0.)+delta
        allowed=rc*mesh['elements'][eid]['volume']*s['alpha'][eid]
        if s['char_consumed'][eid]>allowed+1e-14: raise ValueError('Carbon consumption exceeds produced char')
    s['gas_cumulative_kg']+=gas_delta
    s['char_cumulative_kg']+=p['totals']['char_rate_kg_s']*p['dt']
    pending_char=sum(s['char_consumed'].get(eid,0.) for eid in expected if mesh['elements'][eid]['mat']==1)
    remaining=live_mesh_mass-pending_char
    mass_residual=s['mass_initial_kg']-remaining-s['gas_cumulative_kg']-s['char_cumulative_kg']-s['residual_ejected_kg']
    if abs(mass_residual)>max(1e-13,1e-6*s['mass_initial_kg']): raise ValueError('Phe0 mass balance not closed')
    cap,gen,conv,hfx,rad=[sum(v[i] for v in energy.values()) for i in range(5)]
    nodal=sum(float(x) for x in p['forces'].values())
    energy_residual=cap+conv+rad-hfx-gen-nodal
    scale=max(abs(cap),abs(conv)+abs(rad),abs(hfx)+abs(gen)+abs(nodal),1e-6)
    erel=abs(energy_residual)/scale
    row=mesh['rows'][p['layer']]
    hot_actual=-sum(energy[str(f['element'])][2] for f in row)
    hot_expected=sum(f['area']*p['faces'][i]['h']*(c['heating']['gas_temperature_C']-
                     face_temperature(f,temperatures,c['initial_temperature_C'])) for i,f in enumerate(row))
    hrel=abs(hot_actual-hot_expected)/max(abs(hot_expected),1e-6)
    if hrel>n['hot_power_relative_tolerance']: raise ValueError('Actual hot-side convection absent or mismatched: '+str(hrel))
    if erel>n['energy_relative_tolerance'] and n['stop_on_balance_error']:
        raise ValueError('Thermal energy audit failed: '+str(erel))
    s['temperatures']=temperatures
    s['gas_rate_kg_s']=gas_delta/p['dt']
    s['char_rate_kg_s']=p['totals']['char_rate_kg_s']
    tchange=max(abs(face_temperature(f,temperatures,c['initial_temperature_C'])-p['faces'][i]['T_C']) for i,f in enumerate(row))
    warnings=[]
    if tchange>n['coupling_temperature_warning_K']: warnings.append('COUPLING_DT_REFINEMENT_REQUIRED')
    # Quantify storage removed by topology. Its energy leaves with the killed
    # FE cell; it is not silently counted as an ablation heat sink again.
    row_remaining=sum((rv-(rv-rc)*s['alpha'][str(f['element'])])*f['volume']-
                      s['char_consumed'].get(str(f['element']),0.) for f in row)
    row_initial=rv*sum(f['volume'] for f in row)
    s['pending_kills']=[]
    killed=0
    if row_remaining<=n['row_residual_mass_fraction']*row_initial:
        s['pending_kills']=[f['element'] for f in row]
        s['residual_ejected_kg']+=max(row_remaining,0.)
        s['layer']+=1; killed=len(row)
        # A quadrature diagnostic, not a conservative enthalpy remap. The
        # legacy FE law uses cp(T,alpha)*dT, not d[cp(T,alpha)*T].
        for f in row:
            a=s['alpha'][str(f['element'])]
            T=sum(temperatures[str(nid)] for nid in mesh['elements'][str(f['element'])]['nodes'])/8
            hv,hc=sensible_enthalpy(T,c['initial_temperature_C'])
            s['removed_mesh_energy_J']+=(rv-(rv-rc)*a)*f['volume']*((1-a)*hv+a*hc)
    s['index']=p['index']; s['time_s']=time
    nrows=c['geometry']['phenolic_radial_rows']
    dr=c['geometry']['phenolic_thickness_m']/nrows
    scale=c['geometry']['full_ring_scale_factor']
    s['status']='PHENOLIC_CONSUMED' if s['layer']==nrows else ('COMPLETED_HORIZON' if time>=c['end_time_s']-1e-10 else 'RUNNING')
    s['warnings']=warnings
    for name,value in dict(storage_W=cap,body_source_W=gen,convection_out_W=conv,
                           nodal_net_W=nodal,ablation_sink_W=p['totals']['ablation_sink_W'],
                           hot_radiation_W=p['totals']['hot_radiation_W'],
                           outer_radiation_W=p['totals']['outer_radiation_W'],
                           pyrolysis_sink_est_W=pyro_power,gas_sensible_sink_est_W=gas_power).items():
        s['energy_integrals'][name.replace('_W','_J')]=s['energy_integrals'].get(name.replace('_W','_J'),0.)+value*p['dt']
    removed_initial_mass=sum(
        m['virgin_reference_density_kg_m3']*f['volume']
        for deleted_row in mesh['rows'][:s['layer']] for f in deleted_row)
    alpha_values=[s['alpha'][str(f['element'])] for f in row]
    record=dict(time_s=time,dt_s=p['dt'],layer_solved=p['layer'],rows_removed=p['layer'],rows_scheduled=s['layer'],
                hot_radius_m=c['geometry']['inner_radius_m']+p['layer']*dr,
                phenolic_initial_thickness_m=c['geometry']['phenolic_thickness_m'],
                phenolic_removed_thickness_m=s['layer']*dr,
                phenolic_remaining_thickness_m=max(c['geometry']['phenolic_thickness_m']-s['layer']*dr,0.0),
                phenolic_removed_initial_mass_sector_kg=removed_initial_mass,
                phenolic_removed_initial_mass_full_ring_kg=removed_initial_mass*scale,
                hot_faces=p['loaded_hot_faces'],hot_nodes=p['loaded_hot_nodes'],area_m2=p['area'],
                Ts_mean_C=sum(f['area']*face_temperature(f,temperatures,c['initial_temperature_C']) for f in row)/p['area'],
                alpha_mean=sum(s['alpha'][str(f['element'])]*f['volume'] for f in row)/sum(f['volume'] for f in row),
                alpha_min=min(alpha_values),
                h_W_m2_K=p['faces'][0]['h'],hot_power_expected_W=hot_expected,hot_power_actual_W=hot_actual,
                hot_power_relative_error=hrel,storage_W=cap,body_generation_W=gen,
                convection_out_W=conv,nodal_net_W=nodal,ablation_sink_W=p['totals']['ablation_sink_W'],
                hot_radiation_W=p['totals']['hot_radiation_W'],outer_radiation_W=p['totals']['outer_radiation_W'],
                energy_residual_W=energy_residual,energy_relative_error=erel,
                gas_cumulative_kg=s['gas_cumulative_kg'],gas_cumulative_full_ring_kg=s['gas_cumulative_kg']*scale,
                char_cumulative_kg=s['char_cumulative_kg'],char_cumulative_full_ring_kg=s['char_cumulative_kg']*scale,
                solid_remaining_kg=max(remaining-row_remaining,0.) if killed else remaining,
                solid_remaining_full_ring_kg=(max(remaining-row_remaining,0.) if killed else remaining)*scale,
                subcell_mass_still_in_FE_kg=pending_char,residual_ejected_kg=s['residual_ejected_kg'],
                mass_residual_kg=mass_residual,elements_scheduled_for_removal=killed,
                topology_sensible_energy_scheduled_est_J=s['removed_mesh_energy_J'],
                max_coupling_temperature_change_K=tchange,status=s['status'],warning=';'.join(warnings))
    return s,record


def heat_capacity(T):
    table=[(26.85,900,800),(326.85,1100,900),(626.85,1300,1000),
           (776.85,1300,1250),(926.85,1300,1550),(1226.85,1300,1950),
           (1426.85,1300,2060),(1926.85,1300,2085),(2476.85,1300,2090)]
    if T<=table[0][0]: return table[0][1:]
    for a,b in zip(table,table[1:]):
        if T<=b[0]:
            f=(T-a[0])/(b[0]-a[0]); return tuple(a[i]+f*(b[i]-a[i]) for i in (1,2))
    return table[-1][1:]


def sensible_enthalpy(T,T0):
    if T<T0:
        return tuple(-x for x in sensible_enthalpy(T0,T))
    knots=[T0]+[t for t in (26.85,326.85,626.85,776.85,926.85,1226.85,1426.85,1926.85,2476.85) if T0<t<T]+[T]
    return tuple(sum((heat_capacity(a)[i]+heat_capacity(b)[i])*(b-a)/2 for a,b in zip(knots,knots[1:])) for i in (0,1))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['initialize','prepare','accept','validate'])
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    args=ap.parse_args(); root=args.root.resolve()
    c=load(root/'config.json'); validate_config(c); mesh=load(root/'mesh_map.json')
    if args.action=='validate':
        assert len(mesh['rows'])==c['geometry']['phenolic_radial_rows']
        assert all(len(r)==c['geometry']['faces_per_row'] for r in mesh['rows'])
        print('CONFIG_AND_MESH_VALID_NO_SOLVE'); return
    if args.action=='initialize':
        if (root/'state.json').exists(): raise RuntimeError('Existing run state preserved: use a new run directory.')
        save(root/'state.json',initial_state(mesh,c)); return
    s=load(root/'state.json')
    if s['config_sha256']!=fingerprint(c):
        raise ValueError('Configuration changed after initialization; create a new run, do not mix states.')
    if args.action=='prepare':
        stop=(root/'PAUSE_REQUESTED').exists() or s['time_s']>=c['end_time_s']-1e-10 or s['layer']>=c['geometry']['phenolic_radial_rows']
        if stop:
            if (root/'PAUSE_REQUESTED').exists():
                s['status']='PAUSED_AT_CHECKPOINT'; save(root/'state.json',s)
            atomic(root/'step_control.inp','V0_OK=1\nV0_DONE=1\n'); return
        p,commands=prepare_step(mesh,c,s)
        save(root/'pending.json',p)
        atomic(root/'apply_loads.inp',commands)
        atomic(root/'step_control.inp',f'V0_OK=1\nV0_DONE=0\nV0_INDEX={p["index"]}\nV0_PREVIOUS={s["index"]}\nV0_TARGET={p["target"]:.16e}\nV0_DT={p["dt"]:.16e}\n')
    else:
        p=load(root/'pending.json')
        time=float((root/'observed_time.txt').read_text().strip())
        temp={k:v[0] for k,v in read_rows(root/'node_temperatures.txt').items()}
        new,record=accept_step(mesh,c,s,p,temp,read_rows(root/'element_fields.txt'),read_rows(root/'energy_fields.txt'),time)
        # One immutable audit record per accepted state. CSV is derived from these.
        checkpoints=root/'checkpoints'; checkpoints.mkdir(exist_ok=True)
        # Compress state snapshots; audit records remain directly readable.
        import gzip
        dest=checkpoints/f'state_{new["index"]:06d}.json.gz'
        temporary=dest.with_suffix('.new')
        with gzip.open(temporary,'wt',encoding='utf-8') as stream: json.dump(new,stream,allow_nan=False)
        os.replace(temporary,dest)
        save(checkpoints/f'audit_{new["index"]:06d}.json',record)
        save(root/'state.json',new)
        rows=[load(p) for p in sorted(checkpoints.glob('audit_*.json'))]
        import io
        buf=io.StringIO(); writer=csv.DictWriter(buf,fieldnames=list(record)); writer.writeheader(); writer.writerows(rows)
        atomic(root/c['output']['history_file'],buf.getvalue())
        atomic(root/'accepted.inp','V0_OK=1\n')


if __name__=='__main__':
    try: main()
    except Exception:
        # Missing success marker makes MAPDL stop before another SOLVE.
        trace=traceback.format_exc()
        print(trace)
        args_root=Path(sys.argv[sys.argv.index('--root')+1]) if '--root' in sys.argv else Path(__file__).resolve().parent
        atomic(args_root/'coupler_error.txt',trace)
        raise
