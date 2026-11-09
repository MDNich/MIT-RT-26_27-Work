"""Prepare the matched October film interval using verified native modes and independent time integration."""
import argparse

import numpy as np

from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from seeded_motion import FS,FRAMES,integrate,participation


def check_newmark(freq,gamma,acc):
    """Average-acceleration Newmark update with the sealed acceleration samples."""
    dt=1/FS
    w=2*np.pi*freq
    damping=.04*w
    u=np.zeros(len(w))
    v=u.copy()
    a=-gamma*acc[0]
    mass=1+dt*.5*damping+dt**2*.25*w**2
    rows=[]
    for i in range(1,FRAMES[-1]+1):
        prediction=u+dt*v+dt**2*.25*a
        v_half=v+.5*dt*a
        a=(-gamma*acc[i]-damping*v_half-w**2*prediction)/mass
        u=prediction+dt**2*.25*a
        v=v_half+dt*.5*a
        if i>=FRAMES[0] and (i-FRAMES[0])%4==0:
            rows.append(u.copy())
    return np.array(rows)


def prepare(branch,axis,campaign):
    key=branch+'_basis'
    basis=read(ROOT/'validation/global'/(key+'.json'))
    assert basis['campaign']==campaign and basis['case']==key
    folder=ROOT/'.runtime/archive'/campaign/key
    receipt=read(ROOT/'.runtime/receipts'/campaign/key/'archived.json')
    assert receipt['campaign']==campaign and receipt['case']==key
    verified(folder/'file.rst',basis['rst_sha256'])
    log=folder/'solve.out'
    log_sha=verified(log,next(f['sha256'] for f in receipt['files'] if f['name']=='solve.out'))
    f=np.array(basis['frequencies_Hz'])
    g=participation(log.read_text(errors='replace'),axis)
    assert np.all(np.diff(f)>0) and len(f)==len(g)
    t,q,_=integrate(f,g,axis)
    acc_path=ROOT/'.runtime/motion_loads'/(axis+'.txt')
    ref=read(ROOT/'validation/motion_inputs.json')['inputs'][axis]
    verified(acc_path,ref['sha256'])
    input_data=np.loadtxt(acc_path,skiprows=1,max_rows=int(FRAMES[-1])+1)
    assert np.max(abs(input_data[:,0]-np.arange(len(input_data))/FS))<5.1e-13
    direct=check_newmark(f,g,input_data[:,1])
    diff=float(np.linalg.norm(direct-q)/np.linalg.norm(q))
    assert diff<1e-9 and q.shape==(480,len(f)) and np.array_equal(t,FRAMES/FS)
    name=branch+'_motion_'+axis
    out=ROOT/'.runtime/post'/campaign/name/'independent'
    out.mkdir(parents=True,exist_ok=True)
    clip=out/'coordinates.npz'
    if not clip.exists():
        temp=out/'coordinates.tmp.npz'
        np.savez_compressed(temp,time_s=t,coordinates=q,frequencies_Hz=f)
        temp.replace(clip)
    with np.load(clip) as old:
        assert np.array_equal(old['time_s'],t) and np.array_equal(old['coordinates'],q) and np.array_equal(old['frequencies_Hz'],f)
    data=dict(case=name,branch=branch,axis=axis,campaign=campaign,coordinate_method='independent',
              basis_rst_sha256=basis['rst_sha256'],modal_listing_sha256=log_sha,input_sha256=ref['sha256'],
              clip_sha256=digest(clip),frames=len(t),time_s=[float(t[0]),float(t[-1])],
              Newmark_relative_L2=diff,scope='Linear response about the native bolt-locked equilibrium. Independent '
              'modal integration from rest with the original sampled base acceleration. Compared with a direct '
              'average-acceleration update; physical bare reference checks are in seeded_bare_independent_repeat.json.')
    write_json(ROOT/'validation/independent_motion'/(name+'.json'),data)
    print(name,diff,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch');p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args()
    for axis in 'XYZ':prepare(a.branch,axis,a.campaign)
