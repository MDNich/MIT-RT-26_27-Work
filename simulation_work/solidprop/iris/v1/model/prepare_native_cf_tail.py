"""Prepare late CF liner FE checks from the audited near-pure-char state.

The fixed interface temperature comes from the reacting CF solution. At the
gas face the native nodal field drives char kinetics, gas blowing, heat input
and physical recession. Each new mesh receives conservative nodal enthalpies.
The package contains only the final part of exposure, not a whole-motor run.
"""
import argparse
import json
import math
from pathlib import Path
import tempfile

import numpy as np
from scipy.linalg import solve_banded

from continuous_heating_campaign import digest
from coupler import R, blowing, char_rate
from moving_surface_remap import remap
from moving_surface_thermochemistry import sensible
from ops import ROOT, atomic, disks
from prepare_model import create_mesh
from radial_model import TABLE

PACKAGE=ROOT/'configs/native_verification/cf_tail_char_smp10_r2'
AUDIT=ROOT/'validation/cf_backing_audit.json'
PLAN=ROOT/'configs/cf_backing_campaign.json'
RHO=600.
# Keep all original knots. Additional enthalpy points resolve the tabulated cp
# primitive while remaining below the 100-point MAPDL material-table limit.
TEMP=np.unique(np.r_[TABLE[:,0],np.arange(40.,2476.,40.)])
H=RHO*sensible(TEMP)[:,1]
COND=np.interp(TEMP,TABLE[:,0],TABLE[:,2])
assert len(TEMP)<100


def dual(r):
    """Annular partitions whose volumes equal the row sums of linear FE shape functions."""
    a,b=r[:-1],r[1:]
    split=np.sqrt(a*a+(b-a)*(2*a+b)/3.)
    return np.r_[r[0],split,r[-1]]


def step_reference(case,n,dtlim,start_temp,wall,geom,ri,ro,fields=None):
    h=case['heating']; law=case['char_law']
    r=np.linspace(ri,ro,n+1)
    t=np.array(start_temp)
    history=[]
    elapsed=0.
    for _ in range(4000):
        # Each fresh uniformly heated sector has transverse edge length equal
        # to its live radial pitch. The stored quantities are per radian and metre.
        pitch=(ro-r[0])/n
        geom=math.cos(pitch/(2*ro))
        old=t
        j=char_rate(old[0],law)
        film=blowing(h['h0_W_m2_K'],j,h['gas_cp_J_kg_K'])
        v=j/(RHO*geom)
        dt=min(dtlim,(ro-r[0])/v)
        exhausted=(ro-r[0])/v<=dtlim
        hot=ro if exhausted else r[0]+dt*v
        old_dual=dual(r)
        vol=np.diff(old_dual)*(old_dual[:-1]+old_dual[1:])/2.
        hold=np.interp(old,TEMP,H)
        surface= r[0]/geom
        t=old.copy()
        interface=np.interp(elapsed+dt,wall[:,0],wall[:,1])
        for _ in range(40):
            href=np.interp(t,TEMP,H)
            idx=np.clip(np.searchsorted(TEMP,t,side='right')-1,0,len(H)-2)
            cvol=np.diff(H)[idx]/np.diff(TEMP)[idx]
            k=np.interp(.5*(t[:-1]+t[1:]),TEMP,COND)
            g=k*(r[:-1]+r[1:])/(2.*geom**2*np.diff(r))
            q=np.r_[surface*(film*(h['gas_temperature_C']-t[0])-j*law['effective_endothermic_cost_J_kg']),g*(t[:-1]-t[1:])]
            res=vol*(href-hold)/dt+np.diff(np.r_[q,0.])
            res[-1]=t[-1]-interface
            # Late thin elements amplify one floating-point temperature ulp
            # into a finite face-flow residual through their large conductance.
            roundoff=12.*np.spacing(max(abs(t)))*(np.r_[0.,g[:-1]]+g)
            tolerance=2e-8*vol[:-1]*cvol[:-1]/dt+roundoff
            if np.all(abs(res[:-1])<tolerance) and abs(res[-1])<1e-9: break
            mat=np.zeros((3,n+1))
            mat[1]=vol*cvol/dt
            mat[1,0]+=surface*film
            mat[1,:-1]+=g;mat[1,1:]+=g
            mat[1,-1]=1.;mat[0,1:]=-g;mat[2,:-1]=-g;mat[2,-2]=0.
            t+=solve_banded((1,1),mat,-res)
        else: raise ValueError(f'Reference heat solve failed at {elapsed:g} s, width {ro-r[0]:g} m, residual {max(abs(res[:-1]*dt)/(vol[:-1]*cvol[:-1])):g} K, dt {dt:g}, range {min(t):g}--{max(t):g} C')
        time1=elapsed+dt
        # The constrained-face flux accounts for storage of its outer half-cell.
        power_back = vol[-1]*(href[-1]-hold[-1])/dt-q[-1]
        rnext=np.array([ro]) if exhausted else np.linspace(hot,ro,n+1)
        transferred=remap(old_dual,href,rnext if exhausted else dual(rnext))
        stored=float(sum(transferred.cell_integrals))
        swept=float(transferred.removed_integrals)
        budget=stored+swept-vol@hold-dt*(q[0]+power_back)
        if abs(budget)>2e-6*max(1.,abs(dt*q[0]),abs(dt*power_back)): raise ValueError('Reference energy budget failed')
        if fields is not None: fields.append((old.copy(),t.copy()))
        history.append(dict(time_s=time1,hot_radius_m=float(hot),dt_s=dt,rate_kg_m2_s=j,
                     step_start_C=float(old[0]),step_end_C=float(t[0]),back_C=interface,
                     removed_H_J_per_rad_m=swept,back_power_W_per_rad_m=power_back,energy_error_J_per_rad_m=budget))
        if exhausted: return history
        t=np.interp(transferred.density,H,TEMP)
        r,elapsed=rnext,time1
    raise ValueError('Reference exceeded planned steps')


def table_apdl(name,x,y):
    lines=[f'*DIM,{name},TABLE,{len(x)},1,1']
    for i,(a,b) in enumerate(zip(x,y),1):
        lines.extend((f'{name}({i},0)={a:.16g}',f'{name}({i},1)={b:.16g}'))
    return lines


def build(item,d,n,dt,job):
    cfg=item['configuration']
    event=d['events']['first_1000C'][1]
    p=next(p for p in d['profiles'] if p['time_s']==event)
    e=np.array(p['liner_edges_m']); v=np.array(p['liner_virgin_kg_per_rad_m']); c=np.array(p['liner_char_kg_per_rad_m'])
    virgin_fraction=float(v.sum()/(v+c).sum())
    local=float(max(v/(v+c)))
    assert local<3e-5 and virgin_fraction<6e-6
    ri,ro=e[0],e[-1]
    r=np.linspace(ri,ro,n+1)
    original_volume=np.diff(e)*(e[:-1]+e[1:])/2.
    # Represent the specified pure residue. Quantify the energy/mass difference
    # from the donor's small residual virgin inventory and nonlinear material table.
    dens=np.interp(p['liner_temperature_C'],TEMP,H)
    transferred=remap(e,dens,dual(r))
    start=np.interp(transferred.density,H,TEMP)
    w=np.array([(row['time_s']-event,row['interface_C']) for row in d['history'] if row['time_s']>=event])
    assert np.all(np.diff(w[:,0])>0.) and w[0,0]==0.
    g=cfg['geometry'].copy()
    g.update(inner_radius_m=ri,outer_radius_m=ro,phenolic_outer_radius_m=(ri+ro)/2.,
             phenolic_thickness_m=(ro-ri)/2.,aluminium_thickness_m=(ro-ri)/2.,
             phenolic_radial_rows=n//2,aluminium_radial_rows=n//2)
    nt,ny=g['angular_divisions'],g['axial_divisions']
    pitch=(ro-ri)/n
    g.update(angle_deg=math.degrees(nt*pitch/ro),length_m=ny*pitch)
    ring=(nt+1)*(ny+1)
    mesh,nodes,elements=create_mesh(dict(geometry=g,mesh_measure_convention='straight_sided_hex'))
    facet=math.cos(math.radians(g['angle_deg'])/(2*nt))
    law,h=cfg['char_law'],cfg['heating']
    assert h['hot_effective_emissivity']==0 and law['mode']=='effective_exploratory'
    ref=step_reference(cfg,n,dt,start,w,facet,ri,ro)
    partial=law['reactive_activity']*law['pressure_Pa']/law['pressure_reference_Pa']
    lines=['! Iris terminal CF char window, prescribed backing trace, live gas-side kinetics.',
           '/CLEAR,START','/PREP7','ET,1,SOLID278','KEYOPT,1,15,1','KEYOPT,1,13,1','TYPE,1','MAT,1']
    for i,(tt,hh,kk) in enumerate(zip(TEMP,H,COND),1):
        lines.extend([f'MPTEMP,{i},{tt:.16g}',f'MPDATA,ENTH,1,{i},{hh:.16g}',f'MPDATA,KXX,1,{i},{kk:.16g}'])
    lines += [f'N,{idx},{x:.16g},{y:.16g},{z:.16g}' for idx,x,y,z in nodes]
    connectivity = ['EN,'+','.join(map(str,[eid,*ids])) for eid,_,ids in elements]
    lines+=['FINISH',f'RN={n}',f'NRING={ring}',f'RSTART={ri:.16g}',f'REND={ro:.16g}',f'FCOS={facet:.16g}',
        f'DTLIM={dt}',f'JFAC={law["reference_rate_kg_m2_s"]*partial**law["pressure_exponent"]:.16g}',
        f'JCAP={law["mass_transfer_cap_kg_m2_s"]*partial:.16g}',f'EOVER={law["activation_energy_J_mol"]/R:.16g}',
        f'TREFK={law["reference_temperature_K"]:.16g}',f'HCOST={law["effective_endothermic_cost_J_kg"]:.16g}',
        f'HBASE={h["h0_W_m2_K"]:.16g}',f'TG={h["gas_temperature_C"]:.16g}',f'GCP={h["gas_cp_J_kg_K"]:.16g}',
        f'*DIM,TN,ARRAY,{len(nodes)}',f'*DIM,HV,ARRAY,{len(nodes)}',f'*DIM,XXOLD,ARRAY,{n+2}',
        f'*DIM,XXNEW,ARRAY,{n+2}',f'*DIM,HPREF,ARRAY,{ring*(n+2)}',f'*DIM,HNEW,ARRAY,{ring*(n+2)}',f'*DIM,DXR,ARRAY,{ring}',f'*DIM,YN,ARRAY,{ring}']
    lines+=table_apdl('HTAB',TEMP,H)+table_apdl('TTAB',H,TEMP)+table_apdl('BCURVE',w[:,0],w[:,1])
    for j,_,_,_ in nodes[:ring]:
        it,iy=divmod(j-1,ny+1)
        lines += [f'DXR({j})={it-nt/2}',f'YN({j})={iy}']
    for i,t in enumerate(start):
        lines += ['*DO,JR,1,NRING',f'TN({i}*NRING+JR)={t:.16g}','*ENDDO']
    lines+=['RPOS=RSTART','ELTIME=0',f'*DO,ISTEP,1,{math.ceil(2*ref[-1]["time_s"]/dt)+5}',
            'PITCH=(REND-RPOS)/RN','DTH=PITCH/REND','FCOS=COS(DTH/2)',
            'TSFACE=0','*DO,JR,1,NRING','TSFACE=TSFACE+TN(JR)/NRING','*ENDDO',
            'JK=JFAC*EXP(-EOVER*(1/(TSFACE+273.15)-1/TREFK))','JACT=1/(1/JK+1/JCAP)',
            'BB=JACT*GCP/HBASE','HACT=HBASE*BB/(EXP(BB)-1)','TLOAD=TG-JACT*HCOST/HACT',
            f'VFACE=JACT/({RHO}*FCOS)','DTNOW=DTLIM','RNEW=RPOS+VFACE*DTNOW','*IF,RNEW,GE,REND,THEN',
            'DTNOW=(REND-RPOS)/VFACE','RNEW=REND','*ENDIF','TEND=ELTIME+DTNOW',
            'TSOURCE=TEND',f'*IF,TSOURCE,GT,{w[-1,0]:.16g},THEN',f'TSOURCE={w[-1,0]:.16g}','*ENDIF','TBACK=BCURVE(TSOURCE)','/PREP7','*IF,ISTEP,GT,1,THEN','EDELE,ALL','*ENDIF',
            '*DO,IR,0,RN','RLOC=RPOS+(REND-RPOS)*IR/RN','*DO,JR,1,NRING','ND=IR*NRING+JR',
            'THETA=DXR(JR)*DTH','NMODIF,ND,RLOC*SIN(THETA),YN(JR)*PITCH,RLOC*COS(THETA)',
            '*ENDDO','*ENDDO',*connectivity,'FINISH',
            '/SOLU','ANTYPE,TRANS,NEW','THOPT,FULL','TRNOPT,FULL','TINTP,,,,1','KBC,1',
            'AUTOTS,OFF','NSUBST,1,1,1','TIME,DTNOW','NEQIT,60','*DO,ND,1,RN*NRING',
            'IC,ND,TEMP,TN(ND)','*ENDDO','*DO,JR,1,NRING','ND=RN*NRING+JR',
            'IC,ND,TEMP,TN(ND)','D,ND,TEMP,TBACK','*ENDDO']
    for f in mesh['rows'][0]:
        eid=f['element']
        lines.extend((f'SFE,{eid},5,CONV,0,HACT',f'SFE,{eid},5,CONV,2,TLOAD'))
    lines+=['OUTRES,ALL,LAST','SOLVE','FINISH','/POST1','SET,LAST','*GET,STIME,ACTIVE,0,SET,TIME',
            'RFHEAT=0','*DO,JR,1,NRING','ND=RN*NRING+JR','*GET,RFN,NODE,ND,RF,HEAT','RFHEAT=RFHEAT+RFN','*ENDDO',
            '*CFOPEN,tail_field,txt,,APPEND','*DO,ND,1,(RN+1)*NRING','*GET,TNEND,NODE,ND,TEMP',
            'HV(ND)=HTAB(TNEND)','TNBEG=TN(ND)','*VWRITE,ISTEP,ND,TNBEG,TNEND','(2(F8.0,1X),2(E22.14,1X))',
            '*ENDDO','*CFCLOSE','*CFOPEN,tail_steps,txt,,APPEND','*VWRITE,ISTEP,TEND,DTNOW,STIME,RPOS,RNEW,JACT,RFHEAT',
            '(F5.0,1X,F13.9,2(1X,E15.9),2(1X,F14.12),1X,E17.10,1X,E19.11)','*CFCLOSE','FINISH','*IF,RNEW,GE,REND,THEN','*EXIT','*ENDIF',
            '! Conserve enthalpy in each nodal annular control volume, independently on each transverse ray.',
            'XXOLD(1)=0.5*RPOS**2','XXNEW(1)=0.5*RNEW**2','XXOLD(RN+2)=0.5*REND**2','XXNEW(RN+2)=0.5*REND**2',
            '*DO,IR,1,RN','DR=(REND-RPOS)/RN','RA=RPOS+(IR-1)*DR','XXOLD(IR+1)=0.5*RA**2+DR*(3*RA+DR)/6',
            'DR=(REND-RNEW)/RN','RA=RNEW+(IR-1)*DR','XXNEW(IR+1)=0.5*RA**2+DR*(3*RA+DR)/6','*ENDDO',
            '*DO,IB,1,RN+1','*DO,JR,1,NRING','II=(IB-1)*NRING+JR',
            'HPREF(II+NRING)=HPREF(II)+(XXOLD(IB+1)-XXOLD(IB))*HV(II)','*ENDDO','*ENDDO',
            'JSCAN=1','*DO,IR,1,RN+2','*DO,IB,JSCAN,RN+1','JSCAN=IB',
            'SCANDEL=(XXNEW(IR)-XXOLD(IB+1))/((REND-RPOS)*REND)','*IF,SCANDEL,LE,0,THEN','*EXIT','*ENDIF','*ENDDO',
            '*DO,JR,1,NRING','II=(JSCAN-1)*NRING+JR','JJ=(IR-1)*NRING+JR',
            'HNEW(JJ)=HPREF(II)+(XXNEW(IR)-XXOLD(JSCAN))*HV(II)','*ENDDO','*ENDDO',
            '*DO,IR,1,RN+1','*DO,JR,1,NRING','JJ=(IR-1)*NRING+JR',
            'HMEAN=(HNEW(JJ+NRING)-HNEW(JJ))/(XXNEW(IR+1)-XXNEW(IR))',
            'TN(JJ)=TTAB(HMEAN)','*ENDDO','*ENDDO','RPOS=RNEW','ELTIME=TEND','*ENDDO',
            '*IF,RNEW,GE,REND,THEN','/COM,IRIS_CF_TAIL_EXHAUSTED','*ENDIF','/EXIT,NOSAVE']
    return '\n'.join(lines)+'\n',dict(job=job,start_s=event,independent_full_event_s=d['events']['exhaustion'][1],
        transverse_geometry='One axial and circumferential edge per live radial pitch. Per-step polygon area used for reaction and boundary heat.',radius_m=[ri,ro],facet_cos=facet,n=n,dt=dt,nodes=len(nodes),ringsize=ring,geometry=g,
        initial_nodal_C=start.tolist(),backing_trace=w.tolist(),reference=ref,
        reference_event_s=ref[-1]['time_s'],initial_donor_virgin_mass_fraction=virgin_fraction,
        largest_donor_virgin_mass_fraction=local,initial_reference_density_kg_m3=RHO,
        relative_pure_char_mass_change=float(RHO*sum(original_volume)/(sum(v)+sum(c))-1.),
        relative_initial_enthalpy_change=float((original_volume@dens)/np.sum(np.column_stack([v,c])*sensible(np.array(p['liner_temperature_C'])))-1.),
        thresholds=dict(event_relative=.01,temperature_K=2.,mass_relative=2e-6,energy_relative=.005),
        scope='CF end window only. Prescribed casing interface from independent donor, fixed terminal trace if needed; '
        'pure char replaces trace virgin content. Live FE consumption and surface motion; no native result yet.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','verify-input'))
    args=parser.parse_args()
    disks()
    if args.action=='prepare' and PACKAGE.exists(): raise FileExistsError('Tail package sealed')
    audit=json.loads(AUDIT.read_text())
    assert audit['plan_sha256']==digest(PLAN)
    jobs={}
    with tempfile.TemporaryDirectory(dir=PACKAGE.parent) as temp:
        stage=Path(temp)/'stage'; stage.mkdir()
        for item in json.loads(PLAN.read_text())['cases']:
            if item['variant']!='fine': continue
            name=item['case']; path=ROOT/'validation/cf_backing_cases'/(item['tag']+'.json')
            assert digest(path)==audit['records'][item['tag']]['sha256']
            d=json.loads(path.read_text())
            for n,dt in ((20,.04),(40,.04),(40,.02)):
                job=f"tail{name[0]}{n}{round(dt*100)}"
                deck,expected=build(item,d,n,dt,job)
                p=stage/(job+'.inp');p.write_text(deck,encoding='ascii')
                expected.update(deck_sha256=digest(p),donor_sha256=digest(path),case=name)
                dest=stage/(job+'.json');atomic(dest,expected);jobs[job]=digest(dest)
        assert len(jobs)==6
        atomic(stage/'manifest.json',dict(audit_sha256=digest(AUDIT),jobs=jobs,prepared_only=True,
               scope='Two CF near-pure-char terminal windows, three independently solved numerical comparisons each.'))
        if args.action=='prepare': stage.rename(PACKAGE)
        else:
            for p in stage.iterdir(): assert p.read_bytes()==(PACKAGE/p.name).read_bytes()
    print('Six CF terminal-window decks and independent FE references checked.')


if __name__=='__main__': main()
