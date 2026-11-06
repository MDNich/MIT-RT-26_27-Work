"""Seal nonuniform moving-char verification decks; native execution is separate.

The exact steady logarithm is specified only at the outer boundary and for the
initial field. A manufactured bulk-gas law supplies convection and char
reaction on the free inner boundary, which advances from the solved field.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile

from scipy.integrate import quad

from coupler import R, blowing, char_rate
from ops import ROOT, atomic, disks
from prepare_model import create_mesh

EARLIER=ROOT/'configs/native_verification/moving_char_log_smp10_r3'
PACKAGE=ROOT/'configs/native_verification/moving_char_log_smp10_r4'
PARENT=ROOT/'configs/moving_surface_campaign.json'
RI,RO,T0,SLOPE=.04,.0406,1150.,-1500.
RHO,K,CP=600.,.60,1500.
NT,NY,ANGLE,LENGTH=2,2,.0116,8.1e-6


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(cfg,n,dt):
    g=cfg['geometry'].copy()
    # Both material blocks in the mesh utility receive the same pure-char
    # material here. The split merely supplies a common sector generator.
    g.update(inner_radius_m=RI,phenolic_outer_radius_m=(RI+RO)/2,outer_radius_m=RO,
             phenolic_thickness_m=(RO-RI)/2,aluminium_thickness_m=(RO-RI)/2,
             phenolic_radial_rows=n//2,aluminium_radial_rows=n//2,angular_divisions=NT,
             axial_divisions=NY,angle_deg=ANGLE,length_m=LENGTH)
    mesh,nodes,elements=create_mesh(dict(geometry=g,mesh_measure_convention='straight_sided_hex'))
    ring=(NT+1)*(NY+1)
    geom=math.cos(math.radians(ANGLE)/(2*NT))
    law,h=cfg['char_law'],cfg['heating']
    assert law['mode']=='effective_exploratory'
    partial=law['reactive_activity']*law['pressure_Pa']/law['pressure_reference_Pa']
    jref=law['reference_rate_kg_m2_s']*partial**law['pressure_exponent']
    cap=law['mass_transfer_cap_kg_m2_s']*partial
    cost=law['effective_endothermic_cost_J_kg']
    def exact_temp(r):
        return T0+SLOPE*math.log(r/RI)
    def exact_time(r):
        return quad(lambda x: RHO*geom/char_rate(exact_temp(x),law),RI,r,epsabs=1e-12)[0]
    def supply(r):
        # The radial coordinate changes by one unit over a chord-normal
        # distance cos(half facet angle). Use that normal gradient.
        ts=exact_temp(r)
        j=char_rate(ts,law)
        film=blowing(h['h0_W_m2_K'],j,h['gas_cp_J_kg_K'])
        return ts+(j*cost-K*SLOPE/(geom*r))/film
    stop=exact_time(RO)
    job=f'mvchar{n}'
    endflag='IRIS_MOVING_CHAR_FINISHED'
    lines=['! Iris manufactured continuously heated moving-char sector. SMP 10.',
        '! Only actual native outputs can establish an FE result.','/CLEAR,START','/PREP7',
        'ET,1,SOLID278',f'MP,KXX,1,{K}',f'MP,DENS,1,{RHO}',f'MP,C,1,{CP}','TYPE,1','MAT,1']
    lines += [f'N,{i},{x:.16g},{y:.16g},{z:.16g}' for i,x,y,z in nodes]
    connectivity = ['EN,'+','.join(map(str,[eid,*ids])) for eid,_,ids in elements]
    lines += ['FINISH',f'RN={n}',f'RINGN={ring}',f'RSTART={RI}',f'REND={RO}',f'TSTART={T0}',
        f'TGRAD={SLOPE}',f'RHOCHAR={RHO}',f'KCHAR={K}',f'FCOS={geom:.16g}',
        f'DTLIM={dt}',f'JFAC={jref:.16g}',f'JCAP={cap:.16g}',f'EOVER={law["activation_energy_J_mol"]/R:.16g}',
        f'TREFK={law["reference_temperature_K"]:.16g}',f'HCOST={cost:.16g}',f'HBASE={h["h0_W_m2_K"]:.16g}',
        f'GASCP={h["gas_cp_J_kg_K"]:.16g}',f'*DIM,TN,ARRAY,{len(nodes)}',f'*DIM,TOLD,ARRAY,{len(nodes)}',
        f'*DIM,DXR,ARRAY,{ring}',f'*DIM,DZR,ARRAY,{ring}',f'*DIM,YN,ARRAY,{ring}']
    for idx,x,y,z in nodes[:ring]:
        lines+= [f'DXR({idx})={x/RI:.16g}',f'DZR({idx})={z/RI:.16g}',f'YN({idx})={y:.16g}']
    lines+=['RPOS=RSTART','ELTIME=0','*DO,IR,0,RN','RLOC=RSTART+(REND-RSTART)*IR/RN',
        '*DO,JR,1,RINGN','TN(IR*RINGN+JR)=TSTART+TGRAD*LOG(RLOC/RSTART)','*ENDDO','*ENDDO',
        f'*DO,ISTEP,1,{math.ceil(2*stop/dt)+6}',
        '! Manufactured bulk temperature depends on position. Char rate and film',
        '! for the actual FE step use the mapped face temperature from that step start.',
        'TEX=TSTART+TGRAD*LOG(RPOS/RSTART)','JK=JFAC*EXP(-EOVER*(1/(TEX+273.15)-1/TREFK))',
        'JE=1/(1/JK+1/JCAP)','BB=JE*GASCP/HBASE','HE=HBASE*BB/(EXP(BB)-1)',
        'TG=TEX+(JE*HCOST-KCHAR*TGRAD/(FCOS*RPOS))/HE','TSFACE=0',
        '*DO,JR,1,RINGN','TSFACE=TSFACE+TN(JR)/RINGN','*ENDDO',
        'JK=JFAC*EXP(-EOVER*(1/(TSFACE+273.15)-1/TREFK))','JACT=1/(1/JK+1/JCAP)',
        'BB=JACT*GASCP/HBASE','HACT=HBASE*BB/(EXP(BB)-1)',
        '! Affine tangent to net inward flux at the mapped, solved surface temperature.',
        'DJDT=JACT*(1-JACT/JCAP)*EOVER/(TSFACE+273.15)**2',
        'DHDT=HACT*(1/BB-EXP(BB)/(EXP(BB)-1))*GASCP/HBASE*DJDT',
        'HTAN=HACT+HCOST*DJDT-DHDT*(TG-TSFACE)',
        'TLOAD=TSFACE+(HACT*(TG-TSFACE)-JACT*HCOST)/HTAN','VFACE=JACT/(RHOCHAR*FCOS)',
        'DTNOW=DTLIM','DTLEFT=(REND-RPOS)/VFACE',
        '! Share the penultimate interval to retain a well-shaped positive last mesh.',
        '*IF,DTLEFT,GT,DTLIM,THEN','*IF,DTLEFT,LT,1.8*DTLIM,THEN',
        'DTNOW=DTLEFT/2','*ENDIF','*ENDIF','RNEW=RPOS+VFACE*DTNOW','*IF,RNEW,GE,REND,THEN',
        'DTNOW=(REND-RPOS)/VFACE','RNEW=REND','*ENDIF',
        '/PREP7','*IF,ISTEP,GT,1,THEN','EDELE,ALL','*ENDIF',
        '! Modify all unloaded nodes before rebuilding and shape-checking any brick.',
        '*DO,IR,0,RN','RLOC=RPOS+(REND-RPOS)*IR/RN','*DO,JR,1,RINGN',
        'INODE=IR*RINGN+JR','NMODIF,INODE,RLOC*DXR(JR),YN(JR),RLOC*DZR(JR)','*ENDDO','*ENDDO',*connectivity,
        'FINISH','/SOLU','ANTYPE,TRANS,NEW','TRNOPT,FULL','KBC,1','AUTOTS,OFF','NSUBST,1,1,1','TIME,DTNOW',
        '*DO,IR,0,RN-1','*DO,JR,1,RINGN','INODE=IR*RINGN+JR','IC,INODE,TEMP,TN(INODE)','*ENDDO','*ENDDO',
        '*DO,JR,1,RINGN','INODE=RN*RINGN+JR','D,INODE,TEMP,TSTART+TGRAD*LOG(REND/RSTART)','*ENDDO']
    for face in mesh['rows'][0]:
        elem=face['element']
        lines+= [f'SFE,{elem},5,CONV,0,HTAN',f'SFE,{elem},5,CONV,2,TLOAD']
    lines+=['OUTRES,ALL,LAST','SOLVE','FINISH','/POST1','SET,LAST','*GET,STIME,ACTIVE,0,SET,TIME',
        'ELTIME=ELTIME+DTNOW','*CFOPEN,moving_steps,txt,,APPEND',
        '*VWRITE,ISTEP,ELTIME,DTNOW,STIME,RPOS,RNEW,JACT,TSFACE',
        '(F5.0,1X,F13.9,2(1X,E15.9),2(1X,F14.12),1X,E17.10,1X,F15.9)','*CFCLOSE','*CFOPEN,moving_field,txt,,APPEND','*DO,IR,0,RN',
        'RLOC=RPOS+(REND-RPOS)*IR/RN','*DO,JR,1,RINGN','INODE=IR*RINGN+JR',
        '*GET,TEND,NODE,INODE,TEMP','TOLD(INODE)=TEND','TBEG=TN(INODE)','*VWRITE,ISTEP,INODE,RLOC,TBEG,TEND',
        '(2(F8.0,1X),3(1X,E20.12))','*ENDDO','*ENDDO','*CFCLOSE','FINISH',
        '*IF,RNEW,GE,REND,THEN','*EXIT','*ENDIF',
        '! Transfer the nonuniform temperature at its actual material radius.',
        '! Piecewise logarithmic interpolation exactly transfers a log steady field.',
        '*DO,IR,0,RN','RLOC=RNEW+(REND-RNEW)*IR/RN','POSIDX=(RLOC-RPOS)*RN/(REND-RPOS)','JLOW=NINT(POSIDX-MOD(POSIDX,1))',
        '*IF,JLOW,GE,RN,THEN','JLOW=RN-1','*ENDIF','RA=RPOS+(REND-RPOS)*JLOW/RN',
        'RB=RPOS+(REND-RPOS)*(JLOW+1)/RN','WT=LOG(RLOC/RA)/LOG(RB/RA)',
        '*DO,JR,1,RINGN','ILOW=JLOW*RINGN+JR',
        'TN(IR*RINGN+JR)=(1-WT)*TOLD(ILOW)+WT*TOLD(ILOW+RINGN)','*ENDDO','*ENDDO','RPOS=RNEW','*ENDDO',
        '*IF,RNEW,GE,REND,THEN',f'/COM,{endflag}','*ENDIF','/EXIT,NOSAVE']
    data=dict(job=job,radial_cells=n,ringsize=ring,nodes=len(nodes),elements=len(elements),
        dt_ceiling_s=dt,exact_event_s=stop,exact_outer_C=exact_temp(RO),
        gas_C_at_initial_and_exhausted_face=[supply(RI),supply(RO)],radial_correction=geom,
        inner_m=RI,outer_m=RO,slope_K=SLOPE,initial_face_C=T0,k_W_m_K=K,rho_kg_m3=RHO,cp_J_kg_K=CP,
        angle_deg=ANGLE,angular_divisions=NT,length_m=LENGTH,terminal_marker=endflag,
        preregistered=dict(max_field_error_K=.5,max_relative_event_time=.01,
                           max_relative_mass_imbalance=2e-6,max_transverse_spread_K=.1),
        limits='Homogeneous pure char, constant properties, manufactured gas law, fixed-temperature outer face. '
               'This verifies a native moving-boundary subproblem and cannot give a motor lifetime.')
    deck=('\n'.join(lines)+'\n').encode('ascii')
    data['deck_sha256']=sha(deck)
    return deck,data


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','verify-input'))
    action=p.parse_args().action
    disks()
    cfg=json.loads(PARENT.read_text())['cases'][0]['configuration']
    files={}
    for n,dt in [(8,.2),(16,.1)]:
        deck,expected=build(cfg,n,dt)
        files[f'mvchar{n}.inp']=deck
        files[f'mvchar{n}.json']=(json.dumps(expected,indent=2)+'\n').encode('ascii')
    if action=='prepare':
        if PACKAGE.exists(): raise FileExistsError('Moving verification packages are sealed')
        with tempfile.TemporaryDirectory(dir=PACKAGE.parent) as tmp:
            stage=Path(tmp)/'new'
            stage.mkdir()
            for name,data in files.items(): (stage/name).write_bytes(data)
            atomic(stage/'manifest.json',dict(parent_sha256=sha(PARENT.read_bytes()),
                files={k:sha(v) for k,v in files.items()},cores=10,prepared_only=True,
                predecessor_manifest_sha256=sha((EARLIER/'manifest.json').read_bytes()),
                changes='Retain the R3 tangent law and mesh rebuild. Reduce the angular and axial spans of the uniform manufactured coupon and share a short final interval to keep the final positive-thickness brick aspect ratios below 20. Recalculate the chord correction and analytic reference. Preserve field and event tolerances.'))
            stage.rename(PACKAGE)
    manifest=json.loads((PACKAGE/'manifest.json').read_text())
    assert manifest['parent_sha256']==sha(PARENT.read_bytes())
    for k,v in files.items(): assert (PACKAGE/k).read_bytes()==v and manifest['files'][k]==sha(v)
    print('Verified sealed nonuniform moving-char decks and analytical references.')


if __name__=='__main__': main()
