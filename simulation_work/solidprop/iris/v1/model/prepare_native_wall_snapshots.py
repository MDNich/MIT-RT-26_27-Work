"""Seal four native short thermal windows on actual, independently audited moving-wall fields.

At 30 s freeze geometry, chemistry rates, capacity, conductivity and net surface
flows. Solve only conduction and storage for a further 0.05 s. This isolates
the native thermal solve from the separate moving-char geometry benchmark.
"""
import argparse
import json
import math
from pathlib import Path
import tempfile

import numpy as np
from scipy.linalg import solve_banded

from continuous_heating_campaign import digest
from moving_surface_boundary import solve_face
from moving_surface_conduction import thermal_geometry
from moving_surface_remap import remap
from moving_surface_thermochemistry import REFERENCE_C, recover_temperature, sensible
from moving_surface_transient import Wall
from ops import ROOT, atomic, disks
from prepare_model import create_mesh
from radial_model import R, SIGMA, TABLE

PACKAGE=ROOT/'configs/native_verification/motor_snapshots_30s_smp10'
PLAN=ROOT/'configs/moving_surface_campaign.json'
AUDIT=ROOT/'validation/moving_surface_campaign_audit.json'


def reference(edges,k,volcap,qgen,qin,qout,initial,facet,dt,steps,lumped):
    # Assemble a separate linear radial FE system using exact integration of
    # r N_i N_j and r N_i. The chord-face normal gradient is scaled by 1/facet.
    n=len(edges)
    cap=np.zeros((3,n));conduct=np.zeros((3,n));load=np.zeros(n)
    for i,(a,b) in enumerate(zip(edges[:-1],edges[1:])):
        dr=b-a
        stiff=k[i]*(a+b)/(2.*dr*facet**2)
        diagonal=volcap[i]*dr*np.array([3*a+b,a+3*b])/12.
        off=volcap[i]*dr*(a+b)/12.
        if lumped:
            diagonal+=off
            off=0.
        cap[1,i:i+2]+=diagonal;cap[0,i+1]=cap[2,i]=off
        conduct[1,i:i+2]+=stiff;conduct[0,i+1]=conduct[2,i]=-stiff
        load[i:i+2]+=qgen[i]*dr*np.array([2*a+b,a+2*b])/6.
    load[0]+=qin*edges[0]/facet
    load[-1]-=qout*edges[-1]/facet
    mat=cap/dt+conduct
    t=initial.copy()
    history=[]
    for _ in range(steps):
        rhs=cap[1]*t
        rhs[:-1]+=cap[0,1:]*t[1:]
        rhs[1:]+=cap[2,:-1]*t[:-1]
        t=solve_banded((1,1),mat,rhs/dt+load)
        history.append(t.tolist())
    weight=cap[1].copy()
    weight[:-1]+=cap[2,:-1];weight[1:]+=cap[0,1:]
    budget=abs(weight@(t-initial)-sum(load)*dt*steps)
    assert budget<1e-5*max(1.,abs(sum(load)*dt*steps))
    return history,float(budget)


def generate(row,receipt):
    cfg=row['configuration']; name=row['case']
    src=ROOT/'validation/moving_surface_cases'/f"{row['tag']}.json"
    assert digest(src)==receipt['records'][row['tag']]['record_sha256']
    data=json.loads(src.read_text())
    prof=next(p for p in data['profiles'] if abs(p['time_s']-30.)<1e-8)
    point=next(p for p in data['history'] if abs(p['time_s']-30.)<1e-8)
    w=Wall(cfg,row['n'],row['nc'])
    e=np.array(prof['liner_edges_m']); ri,rp,ro=e[0],e[-1],w.outer
    n,nc=80,20
    layer=np.linspace(ri,rp,n+1); case_edges=np.linspace(rp,ro,nc+1)
    edges=np.r_[layer[:-1],case_edges]
    mids,vols,_=thermal_geometry(e,np.ones(len(e)-1))
    v,c,t=(np.array(prof[x]) for x in ('liner_virgin_kg_per_rad_m','liner_char_kg_per_rad_m','liner_temperature_C'))
    hv,hc=sensible(t).T
    fields=np.array([v,c,v*hv+c*hc])
    bulk=(1.-w.chem.char_yield)*v*333.*np.exp(-64081./(R*(t+273.15)))
    face=solve_face(t[0],v[0]/vols[0],c[0]/vols[0],ri,mids[0],sum(bulk)/ri,cfg)
    transfer=remap(e,fields/vols,layer)
    assert max(abs(transfer.balance_residual))<1e-8
    v,c,h=transfer.cell_integrals
    t= recover_temperature(v,c,h)
    vol=np.diff(layer)*(layer[1:]+layer[:-1])/2.
    yield_char=w.chem.char_yield
    alpha=c/(c+yield_char*v)
    k=(1.-alpha)*np.interp(t,TABLE[:,0],TABLE[:,1])+alpha*np.interp(t,TABLE[:,0],TABLE[:,2])
    cap=(v*np.interp(t,TABLE[:,0],TABLE[:,3])+c*np.interp(t,TABLE[:,0],TABLE[:,4]))/vol
    hv,hc=sensible(t).T
    loss=v/vol*333.*np.exp(-64081./(R*(t+273.15)))
    sink=loss*(w.chem.pyrolysis_J_per_kg_virgin+(1.-yield_char)*w.chem.gas_cp_J_kg_K*(t-REFERENCE_C)+yield_char*hc-hv)
    case_mid,_,_=thermal_geometry(w.case_edges,np.ones(row['nc']))
    tc=np.array(prof['casing_cell_C'])
    coarse_centre,_,_=thermal_geometry(case_edges,np.ones(nc))
    cp_case=w.casing(np.interp(coarse_centre,case_mid,tc))[1]
    qgen=np.r_[-sink,np.zeros(nc)]
    conductivity=np.r_[k,np.full(nc,w.case_k)]
    cap=np.r_[cap,cfg['material']['aluminium_density_kg_m3']*cp_case]
    initial=np.interp(edges,np.r_[ri,mids,rp,case_mid,ro],
                      np.r_[face.temperature_C,prof['liner_temperature_C'],point['interface_C'],tc,point['outer_C']])
    bc=cfg['heating']; tout=point['outer_C']; amb=bc['ambient_temperature_C']
    qout=bc['outer_h_W_m2_K']*(tout-amb)+bc['outer_emissivity']*SIGMA*((tout+273.15)**4-(amb+273.15)**4)
    qin=face.conduction_into_solid_W_m2
    g=dict(cfg['geometry'],inner_radius_m=ri,phenolic_thickness_m=rp-ri,phenolic_radial_rows=n,aluminium_radial_rows=nc)
    mesh,nodes,elements=create_mesh(dict(geometry=g,mesh_measure_convention='straight_sided_hex'))
    ring=(g['angular_divisions']+1)*(g['axial_divisions']+1)
    faces=g['angular_divisions']*g['axial_divisions']
    facet=math.cos(math.radians(g['angle_deg'])/(2*g['angular_divisions']))
    h_cons,bal=reference(edges,conductivity,cap,qgen,qin,qout,initial,facet,.005,10,False)
    h_lump,bal_l=reference(edges,conductivity,cap,qgen,qin,qout,initial,facet,.005,10,True)
    lines=['! Frozen thermal response of an audited 30 s Iris field. SMP 10.','/CLEAR,START','/PREP7','ET,1,SOLID278','TYPE,1']
    for i,(k_i,vc) in enumerate(zip(conductivity,cap),1):
        # Density = 1 is purely a factorization of volumetric heat capacity.
        lines += [f'MP,KXX,{i},{k_i:.16g}',f'MP,DENS,{i},1',f'MP,C,{i},{vc:.16g}']
    lines += [f'N,{nid},{x:.16g},{y:.16g},{z:.16g}' for nid,x,y,z in nodes]
    for eid,_,ids in elements:
        if (eid-1)%faces==0: lines.append(f'MAT,{1+(eid-1)//faces}')
        lines.append('EN,'+','.join(map(str,[eid,*ids])))
    lines+=['FINISH','/SOLU','ANTYPE,TRANS','TRNOPT,FULL','LUMPM,OFF','AUTOTS,OFF','KBC,1','NSUBST,10,10,10','TIME,.05']
    lines += [f'IC,{nid},TEMP,{initial[(nid-1)//ring]:.16g}' for nid,_,_,_ in nodes]
    for eid,_,_ in elements:
        q=qgen[(eid-1)//faces]
        if q:
            vals=','.join([f'{q:.14g}']*4)
            lines += [f'BFE,{eid},HGEN,1,{vals}',f'BFE,{eid},HGEN,5,{vals}']
    loads={}
    for group,flux in ((mesh['rows'][0],qin),(mesh['outer'],-qout)):
        for f in group:
            for nid in f['nodes']: loads[nid]=loads.get(nid,0.)+flux*f['area']/4.
    lines += [f'F,{nid},HEAT,{power:.16g}' for nid,power in sorted(loads.items())]
    lines+=['OUTRES,ALL,ALL','SOLVE','FINISH','/POST1','*CFOPEN,snap_field,txt','*DO,JJ,1,10','SET,1,JJ',
            '*GET,STIME,ACTIVE,0,SET,TIME',f'*DO,KK,1,{len(nodes)}','*GET,STEMP,NODE,KK,TEMP',
            '*VWRITE,JJ,KK,STIME,STEMP','(2(F9.0,1X),2(E24.16,1X))','*ENDDO','*ENDDO','*CFCLOSE',
            'FINISH','/COM,IRIS_FROZEN_SNAPSHOT_COMPLETE','/EXIT,NOSAVE']
    out=dict(case=name,source_sha256=digest(src),source_time_s=prof['time_s'],initial_hot_radius_m=ri,
        liner_radial_cells=n,casing_radial_cells=nc,nodes=len(nodes),elements=len(elements),ring_nodes=ring,
        initial_nodal_ring_C=initial.tolist(),consistent_expected_C=h_cons,lumped_diagnostic_C=h_lump,
        reference_energy_error_J_per_rad_m=[bal,bal_l],hot_conductive_flux_W_m2=qin,outer_loss_W_m2=qout,
        criterion_max_nodal_error_K=.25,comparison='Primary consistent-capacity reference. Review a discrepancy; '
        'the lumped diagnostic cannot replace the primary acceptance gate.',input_energy_J_per_sector=.05*(
        sum(loads.values())+sum(qgen[(i-1)//faces]*mesh['elements'][str(i)]['volume'] for i,_,_ in elements)))
    return '\n'.join(lines)+'\n',out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('prepare','verify-input'))
    action=p.parse_args().action
    disks()
    receipt=json.loads(AUDIT.read_text()); plan=json.loads(PLAN.read_text())
    assert receipt['plan_sha256']==digest(PLAN)
    if action=='prepare' and PACKAGE.exists(): raise FileExistsError('Snapshot package is sealed')
    with tempfile.TemporaryDirectory(dir=PACKAGE.parent) as d:
        stage=Path(d)/'snapshots'
        stage.mkdir()
        jobs={}
        for row in plan['cases']:
            if row['n']!=640 or row['dt']!=.02: continue
            case=row['case']; deck,expected=generate(row,receipt)
            path=stage/f'{case}.inp';path.write_text(deck,encoding='ascii')
            expected['deck_sha256']=digest(path)
            atomic(stage/f'{case}.json',expected)
            jobs[case]=digest(stage/f'{case}.json')
        assert len(jobs)==4
        atomic(stage/'manifest.json',dict(plan_sha256=digest(PLAN),audit_sha256=digest(AUDIT),jobs=jobs,
            prepared_only=True,ten_core_smp=True,scope='Frozen continuous-heating field at 30 s, 0.05 s perturbation. '
            'No motion or state evolution during the window. Diagnostic only, no native lifetime.'))
        if action=='prepare': stage.rename(PACKAGE)
        else:
            for path in stage.iterdir(): assert path.read_bytes()==(PACKAGE/path.name).read_bytes()
    print('Four frozen 30 s sector inputs and independent nodal/energy references verified.')


if __name__=='__main__': main()
