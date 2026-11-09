"""Reconstruct the historical excitation and independently integrate an arbitrary accepted modal basis."""
from pathlib import Path
import argparse,csv,hashlib,json
import numpy as np
from scipy.signal import lfilter
ROOT=Path(__file__).resolve().parents[1]
FS=65536
FRAMES=np.arange(FS+4,FS+4+4*480,4)
def excitation(axis):
    period=8; n=FS*period
    f=np.fft.rfftfreq(n,1/FS); S=np.zeros_like(f)
    use=(f>=20)&(f<=2000)
    S[use]=np.exp(np.interp(np.log(f[use]),np.log([20,50,800,2000]),np.log([.026,.16,.16,.026])))*9.806**2
    rng=np.random.default_rng(20261005+'XYZ'.index(axis))
    z=n*np.sqrt(S/(2*period))*np.exp(1j*rng.uniform(0,2*np.pi,len(f)))
    z[[0,-1]]=0
    a=np.fft.irfft(z,n=n)
    t=np.arange(9*FS+1)/FS;full=a[np.arange(len(t))%n]
    ramp=t<.1;full[ramp]*=.5-.5*np.cos(np.pi*t[ramp]/.1)
    return t,full,float(np.sqrt(np.mean(a*a))/9.806)
def participation(listing,axis):
    import re
    part=re.search(r'PARTICIPATION FACTOR CALCULATION \*+\s*'+axis+r'\s+DIRECTION(.*?)(?=sum|TOTAL MASS)',listing,re.I|re.S)
    if not part:raise ValueError('Native participation table missing')
    modes=[]
    for l in part[1].splitlines():
        fields=l.split()
        if len(fields)>=8 and fields[0].isdigit():modes.append((int(fields[0]),float(fields[3])))
    assert [i for i,_ in modes]==list(range(1,len(modes)+1))
    return np.array([a for _,a in modes])
def integrate(freq,gamma,axis):
    t,a,rms=excitation(axis)
    coords=np.empty((480,len(freq)))
    for k,(f,g) in enumerate(zip(freq,gamma,strict=True)):
        w=2*np.pi*f
        kappa=2*FS
        damping=2*.02*w
        d=[kappa*kappa+damping*kappa+w*w,2*(w*w-kappa*kappa),kappa*kappa-damping*kappa+w*w]
        b=-g*np.array([1.,2.,1.])
        coords[:,k]=lfilter(b,d,a)[FRAMES]
    assert np.all(np.isfinite(coords))
    return t[FRAMES],coords,rms
def reference():
    previous=ROOT.parent/'1/output/latex/random_vibration/reproduction'
    basis=previous/'native/modal_basis'
    f=np.loadtxt(basis/'frequencies.csv',delimiter=',',skiprows=1)[:,-1]
    proofs=[]
    for ax in 'XYZ':
        with (basis/f'participation_{ax}.csv').open() as h:g=np.array([float(row['participation']) for row in csv.DictReader(h)])
        t,q,rms=integrate(f,g,ax)
        ref=np.loadtxt(previous/f'motion/inputs/modal_coordinates_{ax}_clip.csv',delimiter=',',skiprows=1)
        assert ref.shape==(480,len(f)+1) and np.max(np.abs(t-ref[:,0]))<5.1e-7
        error=float(np.linalg.norm(q-ref[:,1:])/np.linalg.norm(ref[:,1:]))
        proofs.append(dict(axis=ax,modes=len(f),frames=len(t),relative_L2_coordinate_difference=error,excitation_rms_g=rms))
        assert error<.001,(ax,error)
    (ROOT/'validation/seeded_coordinate_reader.json').write_text(json.dumps(dict(scope='Independent integration versus October native MAPDL coordinates on the delivered clip',cases=proofs),indent=2)+'\n')
if __name__=='__main__':reference()
