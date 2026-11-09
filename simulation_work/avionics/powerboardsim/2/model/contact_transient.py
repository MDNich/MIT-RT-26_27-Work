"""Prepare prescribed nodal motion versus time and a native analytical control for the contact replay."""
import sys
import numpy as np
from scipy.signal import lfilter

from audit_local import ROOT,read
from contact_patch import BRANCH,FS,local_fields,mesh_cards,face_cards,prescribed
from film_identity import digest,write_json
from seeded_motion import excitation,integrate
from stage_local_jobs import seal

def data_file(folder,name,values):
    """MAPDL *VREAD consumes column-major values, one fixed-width scalar per line."""
    path=folder/(name+'.dat')
    data=''.join(f'{v:24.16E}\n' for v in np.ravel(values,order='F')).encode()
    return seal(path,data)

def load_array(name,shape,filename):
    dims=','.join(map(str,shape))
    return [f'*dim,{name},array,{dims}',f'*vread,{name}(1),{filename},dat,,IJK,{dims}','(E24.16)']

def tables(folder,nodes,time,modal,shapes,acceleration):
    nt,ndof=modal.shape
    assert shapes.shape==(len(nodes),3,ndof) and np.all(np.diff(nodes)>0) and np.all(np.diff(time)>0)
    files={}
    arrays=[('pbt',time),('pbn',nodes),('pbq',modal),('pba',acceleration)]
    arrays += [('shape'+a,shapes[:,i,:].T) for i,a in enumerate('xyz')]
    lines=[]
    for name,value in arrays:
        files[name+'.dat']=data_file(folder,name,value)
        lines+=load_array(name,value.shape,name)
    lines += [f'*dim,baseacc,table,{nt},1,1,time',f'*vlen,{nt}',
              '*vfun,baseacc(1,0),copy,pbt(1)',f'*vlen,{nt}','*vfun,baseacc(1,1),copy,pba(1)',
              f'*dim,dispbuf,array,{nt},{len(nodes)}']
    for a in 'xyz':
        label='cut'+a
        lines += [f'*moper,dispbuf(1,1),pbq(1,1),mult,shape{a}(1,1)',
                  f'*dim,{label},table,{nt},{len(nodes)},1,time,node',f'*vlen,{nt}',
                  f'*vfun,{label}(1,0),copy,pbt(1)',f'*do,port,1,{len(nodes)}',
                  f'{label}(0,port)=pbn(port)',f'*vlen,{nt}',
                  f'*vfun,{label}(1,port),copy,dispbuf(1,port)','*enddo']
    return lines,files

def control_inputs():
    t=np.arange(257)/25600.
    q=np.column_stack([np.sin(2*np.pi*140*t)**2,np.sin(2*np.pi*88*t)**2])
    maps=np.zeros((2,3,2));maps[:,0,:]=[[.001,-.0003],[-.0002,.0008]]
    accel=9.*np.sin(2*np.pi*80*t)
    return t,q,maps,accel

def stage_control():
    case='patch_table_control_v1'
    trial=ROOT/'.runtime'/case;trial.mkdir(exist_ok=True)
    t,q,shapes,acc=control_inputs()
    commands,files=tables(trial,np.array([1,3]),1+t,q,shapes,acc)
    cards=['/batch','/prep7','et,1,mass21','keyopt,1,3,2','r,1,.2,.2,.2',
           'et,2,combin14','keyopt,2,2,1','r,2,150000','r,3,90000',
           'n,1,-.01','n,2,0','n,3,.01','type,1','real,1','e,2','type,2','real,2','e,1,2',
           'real,3','e,2,3','d,2,uy,0','d,2,uz,0','d,1,ux,0','d,3,ux,0',
           *commands,'finish','/solu','antype,trans','trnopt,full','timint,off','tintp,0',
           'outres,all,all','kbc,0','time,1','nsubst,2','solve','timint,on','autots,off',
           'd,1,ux,%cutx%','d,3,ux,%cutx%','acel,%baseacc%,0,0','time,1.01','nsubst,256','solve',
           'finish','/post1','set,last','*get,ns,active,0,set,nset','*cfopen,control_response,csv',
           '*vwrite',"('time,left_m,mass_m,right_m')",'*do,ii,1,ns','set,,,,,,,ii',
           '*get,t,active,0,set,time','*get,l,node,1,u,x','*get,m,node,2,u,x','*get,rn,node,3,u,x',
           '*vwrite,t,l,m,rn',"(E20.12,3(',',E20.12))",'*enddo','*cfclos','finish','/exit,nosave']
    files['control.inp']=seal(trial/'control.inp',('\n'.join(cards)+'\n').encode())
    write_json(ROOT/'validation/patch_table_control_input.json',dict(case=case,files=files))

def verify_control():
    from audit_local import table
    spec=read(ROOT/'validation/patch_table_control_input.json')
    folder=ROOT/'.runtime'/spec['case']
    assert int((folder/'exit.txt').read_text(encoding='utf-8-sig'))==0
    for name,sha in spec['files'].items(): assert digest(folder/name)==sha
    a=table(folder/'control_response.csv');a=a[a['time']>=1]
    t,q,shapes,acc=control_inputs()
    assert len(a)==len(t) and np.allclose(a['time']-1,t,atol=1e-10,rtol=0)
    ports=q@shapes[:,0,:].T
    error=np.max(abs(ports-np.column_stack([a['left_m'],a['right_m']])))
    assert error<1e-10,error
    # Average-acceleration Newmark is the trapezoidal rule for this undamped linear oscillator.
    h=t[1]-t[0];m=.2;k1=150000.;k2=90000.;k=k1+k2
    forcing=k1*ports[:,0]+k2*ports[:,1]-m*acc
    exact=lfilter([1,2,1],[4*m/h**2+k,2*k-8*m/h**2,4*m/h**2+k],forcing)
    mass_error=max(abs(a['mass_m']-exact))
    assert mass_error<1e-7, mass_error
    write_json(ROOT/'validation/patch_table_control.json',dict(steps=len(t)-1,input_sha256=spec['files']['control.inp'],
        native_data_sha256=digest(folder/'control_response.csv'),peak_prescribed_error_m=float(error),
        peak_free_oscillator_error_m=float(mass_error),peak_free_response_m=float(max(abs(exact))),
        method='Native TIME,NODE tables on two different supports, modal matrix product and base acceleration. The independent calculation uses the same linear interpolation and average-acceleration time integration.'))

def stage_replay(campaign):
    from extend_board import component
    sample=read(ROOT/'validation/patch_waveform.json')
    assert sample['campaign']==campaign
    catalog={}
    for radius,stride,kind in ((9,4,'free'),(9,4,'contact'),(9,2,'contact'),(15,4,'contact')):
        case=f'replay_{BRANCH}_span{radius}_{kind}_s{stride}_v1'
        folder=ROOT/'.runtime/inputs'/case;folder.mkdir(exist_ok=True)
        state=local_fields(campaign,radius)
        assert state['native_basis']==sample['global_basis_sha256']
        steps=np.arange(0,sample['replay_last_index']+1,stride)
        t,q,_=integrate(state['freq'],state['gamma'],'X',steps)
        at,acc,_=excitation('X');assert np.array_equal(at[steps],t)
        nodes=state['driven'];ix=np.searchsorted(state['nodes'],nodes)
        shapes=np.concatenate([state['locked'][ix,:,None],state['phi'][ix]],axis=2)
        coords=np.column_stack([np.ones(len(q)),q])
        commands,files=tables(folder,nodes,1+t,coords,shapes,acc[steps])
        cards=mesh_cards(state)
        if kind=='contact':cards.extend(face_cards(state))
        component(cards,'PBPORTS',nodes)
        cards += ['allsel,all',*commands,'finish','/solu','antype,trans','trnopt,full','timint,off','tintp,0',
                  'nlgeom,on','nropt,full','neqit,50','kbc,0','outres,all,none','outres,nsol,all','outres,rsol,all']
        if kind=='contact':cards+=['outres,cont,all,PBTOUCH','outres,misc,all,PBTOUCH','cncheck,detail,31,31']
        cards+=prescribed(state,state['locked'])
        # A constant support state before the transient gives zero initial velocity.
        cards+=['time,.5','nsubst,4,100,2','autots,on','solve','time,1','nsubst,2,2,2','solve',
                'timint,on','d,PBPORTS,ux,%cutx%','d,PBPORTS,uy,%cuty%','d,PBPORTS,uz,%cutz%',
                'acel,%baseacc%,0,0']
        # Fit 2% Rayleigh damping to the low case mode and the matched cell mode of the full assembly.
        w1,w2=2*np.pi*np.array([state['freq'][0],state['freq'][8]])
        beta=.04/(w1+w2);alpha=beta*w1*w2
        cards += [f'alphad,{alpha:.15g}',f'betad,{beta:.15g}',f'time,{1+t[-1]:.15g}',
                  f'deltim,{stride/FS:.15g},{stride/FS/8:.15g},{stride/FS:.15g},off','autots,on','solve',
                  'finish','/post1','set,last','/com,PB_TRANSIENT_COMPLETE','finish','/exit,nosave']
        files['model.inp']=seal(folder/'model.inp',('\n'.join(cards)+'\n').encode())
        catalog[case]=dict(case=case,branch=BRANCH,campaign=campaign,files=files,radius_mm=radius,kind=kind,
            stride=stride,global_basis_sha256=state['native_basis'],global_static_sha256=state['native_static'],
            last_physical_time_s=float(t[-1]),samples=len(t),drive_nodes=len(nodes),damping_alpha_per_s=alpha,
            damping_beta_s=beta,damping_reference_Hz=[float(w1/(2*np.pi)),float(w2/(2*np.pi))],
            scope='Transient with relative native modal translations prescribed on local PLA cut faces and cell nodes, plus the same X base acceleration. Reactions can affect the free PLA within the submodel.')
    write_json(ROOT/'validation/contact_replay_inputs.json',catalog)
if __name__=='__main__':
    if sys.argv[1]=='control':stage_control()
    elif sys.argv[1]=='audit':verify_control()
    else:stage_replay(sys.argv[1])
