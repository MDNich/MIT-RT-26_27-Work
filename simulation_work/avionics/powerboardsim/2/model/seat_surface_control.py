"""Flat compression control for the four initially open tab/PCB interfaces (metres, N, Pa)."""
import json, re, sys
import numpy as np
from audit_local import ROOT, table
from film_identity import digest,write_json
from stage_local_jobs import seal
TRIAL='seat_surface_control_v1'

def pair_cards(target,contact):
    return [f'ET,{target},TARGE170',f'ET,{contact},CONTA174',f'KEYOPT,{contact},2,0',f'KEYOPT,{contact},9,0',
            f'KEYOPT,{contact},12,0',f'MP,MU,{contact},0']

def constants(real):
    # Negative absolute pinball in m; a positive 3 mm geometric clearance is retained.
    return [f'R,{real}',f'RMODIF,{real},6,-.0036',f'RMODIF,{real},4,-1e-7']

def stage():
    d=ROOT/'.runtime'/TRIAL;d.mkdir(exist_ok=True)
    l=['/batch','/prep7','et,1,solid185','mp,ex,1,3e9','mp,prxy,1,0','type,1','mat,1']
    for i,z in enumerate([-.005,-.003,0.,.002]):
        for j,(x,y) in enumerate([(0,0),(.01,0),(.01,.01),(0,.01)]):
            l.append(f'n,{4*i+j+1},{x},{y},{z}')
    l+=['en,1,1,2,3,4,5,6,7,8','en,2,9,10,11,12,13,14,15,16',*pair_cards(857,858),*constants(880),
        'real,880','esel,s,elem,,2','nsel,s,node,,9,12','type,857','esurf',
        'allsel,all','esel,s,elem,,1','nsel,s,node,,5,8','type,858','mat,858','esurf','allsel,all',
        'd,all,ux,0','d,all,uy,0','d,1,uz,0,,4','d,13,uz,0,,16','finish','/solu','antype,static','nlgeom,on',
        'cncheck,detail,880,880','outres,all,all','autots,on','kbc,0','neqit,60']
    for stage,travel,n in [(1,0,2),(2,.0029,12),(3,.00302,12),(4,.0027,16)]:
        drift=.0004
        l += [f'd,1,uz,{drift+travel:.8f},,4',f'd,13,uz,{drift:.8f},,16',f'time,{stage}',f'nsubst,{n},1000,{n}','solve']
    l+=['finish','/post1','allsel,all','set,last','*get,ns,active,0,set,nset','*cfopen,seat_control,csv','*vwrite',
        "('set,time,bot_u,top_u,bot_F,top_F,state,pressure,penetration')",
        '*do,i,1,ns','set,,,,,,,i','allsel,all','*get,t,active,0,set,time','*get,bu,node,1,u,z','*get,tu,node,13,u,z',
        'bf=0','tf=0','*do,j,1,4','*get,v,node,j,rf,fz','bf=bf+v','jtop=j+12','*get,v,node,jtop,rf,fz','tf=tf+v','*enddo',
        'esel,s,type,,858','etable,eras','etable,sta,cont,stat,max','etable,pr,cont,pres,max','etable,pe,cont,pene,max',
        '*get,ie,elem,0,num,min','*get,st,elem,ie,etab,sta','*get,pp,elem,ie,etab,pr','*get,pen,elem,ie,etab,pe',
        '*vwrite,i,t,bu,tu,bf,tf,st,pp,pen',"(F6.0,8(',',E17.9))",'*enddo','*cfclos','allsel,all','finish','/exit,nosave']
    return seal(d/'control.inp',('\n'.join(l)+'\n').encode())

def audit():
    d=ROOT/'.runtime'/TRIAL
    assert int((d/'exit.txt').read_text(encoding='utf-8-sig'))==0
    log=(d/'control.out').read_text(errors='replace')
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    gap=float(re.search(r'Min\.\s+Initial gap\s+([\d.+E-]+)',log,re.I)[1])
    assert abs(gap-.003)<1e-7
    a=table(d/'seat_control.csv');t=a['time'];q=a['bot_u']-a['top_u']
    assert np.all(np.diff(t)>0) and np.isclose(t[-1],4)
    assert np.allclose(q,np.interp(t,[0,1,2,3,4],[0,0,.0029,.00302,.0027]),rtol=0,atol=1e-9)
    assert np.allclose(a['top_u'],.0004*np.minimum(t,1.),rtol=0,atol=1e-9)
    f=np.maximum(q-.003,0)*1.e-4*3.e9/.004
    active=f>5;opened=q<.003-1e-6
    assert active.any() and opened[t<=2].all() and opened[-1]
    assert np.max(abs(a['bot_F']+a['top_F']))<.2 and np.max(abs(a['bot_F'][opened]))<.1
    assert np.all(a['state'][active]>=2) and np.all(a['state'][opened]<2)
    assert np.allclose(a['bot_F'][active],f[active],rtol=.04,atol=1)
    assert np.allclose(a['pressure'][active]*1e-4,a['bot_F'][active],rtol=.03,atol=.5)
    assert np.max(a['penetration'][active])<2e-7
    k=int(np.argmax(q));rec=dict(states=len(t),initial_native_gap_mm=gap*1000,
        max_relative_travel_mm=q[k]*1e3,peak_force_N=a['bot_F'][k],analytic_peak_force_N=f[k],
        peak_pressure_MPa=a['pressure'][k]/1e6,free_end_force_N=a['bot_F'][-1],force_balance_max_N=float(np.max(abs(a['bot_F']+a['top_F']))),
        input_sha256=digest(d/'control.inp'),listing_sha256=digest(d/'control.out'),
        scope='Two opposed solid faces, prescribed approach and reopening. Checks contact sign, force, pressure and common translation, not a battery assembly result.')
    write_json(ROOT/'validation/seat_surface_control.json',rec)
    print(rec)

if __name__=='__main__':{'stage':stage,'audit':audit}[sys.argv[1]]()
