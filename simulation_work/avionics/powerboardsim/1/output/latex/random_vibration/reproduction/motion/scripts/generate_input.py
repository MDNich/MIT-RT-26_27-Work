from pathlib import Path
import numpy as np,json,hashlib
T=Path(__file__).resolve().parents[1];O=T/'inputs';O.mkdir(exist_ok=True)
fs=65536;duration=8.;N=int(fs*duration);g=9.806
f=np.fft.rfftfreq(N,1/fs);keep=(f>=20)&(f<=2000)
S=np.zeros_like(f);S[keep]=np.exp(np.interp(np.log(f[keep]),np.log([20,50,800,2000]),np.log([.026,.16,.16,.026])))*g*g
for ia,axis in enumerate('XYZ'):
 rng=np.random.default_rng(20261005+ia);ph=rng.uniform(0,2*np.pi,len(f));z=N*np.sqrt(S/(2*duration))*np.exp(1j*ph)
 z[0]=0;z[-1]=0;a=np.fft.irfft(z,n=N);t=np.arange(9*fs+1)/fs;full=a[np.arange(len(t))%N];ramp=t<.1;full[ramp]*=.5-.5*np.cos(np.pi*t[ramp]/.1)
 np.savez(O/(axis+'.npz'),t=t,acceleration=full,frequency=f,psd=S,periodic_acceleration=a)
 # TREAD accepts first row of table column indexes, followed by TIME,value.
 np.savetxt(O/(axis+'_acc.txt'),np.column_stack([t,full]),fmt=['%.12f','%.12e'],header='0 1',comments='')
 report={'seed':20261005+ia,'fs_Hz':fs,'period_s':duration,'run_duration_s':9,'stationary_interval_s':[1,9],'initial_ramp_s':.1,'g_m_per_s2':g,'units':'m/s^2','input_rms_m_per_s2':float(np.sqrt(np.mean(a*a))),'input_rms_g':float(np.sqrt(np.mean(a*a))/g),'mean':float(a.mean()),'crest_factor':float(abs(a).max()/np.sqrt(np.mean(a*a))),'synthesis':'fixed Fourier amplitudes matched to one-sided log-log PSD, independent seeded uniform phases; zero outside 20..2000 Hz','samples':len(t),'file_sha256':hashlib.sha256((O/(axis+'_acc.txt')).read_bytes()).hexdigest()}
 (O/(axis+'_audit.json')).write_text(json.dumps(report,indent=2));print(axis,report['input_rms_g'])
