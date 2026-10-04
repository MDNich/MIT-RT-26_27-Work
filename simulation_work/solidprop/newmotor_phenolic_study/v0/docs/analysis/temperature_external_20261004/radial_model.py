"""Independent 1D cylindrical thermal/pyrolysis/char-recession surrogate.

No MAPDL invocation or runtime write. Linear radial FE, two Gauss points,
consistent heat capacity, backward Euler, original UserMatTh source terms,
and explicit surface-char bookkeeping with whole-row recession.
"""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import numpy as np
from scipy.linalg import solve_banded

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE/'radial_profiles.json').read_text())
CFG = DATA['configuration']
TABLE = np.array([
    [22,.25,.30,900,800], [26.85,.25,.30,900,800],
    [326.85,.32,.35,1100,900], [626.85,.36,.40,1300,1000],
    [776.85,.36,.44,1300,1250], [926.85,.36,.49,1300,1550],
    [1226.85,.36,.68,1300,1950], [1426.85,.36,.81,1300,2060],
    [1926.85,.36,1.24,1300,2085], [2476.85,.36,1.73,1300,2090]])
SIGMA = 5.670374419e-8
R = 8.31446261815324


@dataclass
class State:
    time: float
    T: np.ndarray
    alpha: np.ndarray
    consumed: np.ndarray
    layer: int
    gas_rate: float
    char_rate: float
    qcond: float
    gas_total: float = 0.
    char_total: float = 0.
    eject_total: float = 0.


class RadialModel:
    def __init__(self, k_scale=1., cp_scale=1., refine=1, removal=True, char_scale=1., qcond_scale=1.):
        self.k_scale, self.cp_scale = k_scale, cp_scale
        self.removal, self.char_scale = removal, char_scale
        self.qcond_scale = qcond_scale
        self.refine = refine
        self.np = 240 * refine
        self.r = np.r_[np.linspace(.066675,.0714375,self.np+1),
                       np.linspace(.0714375,.0762,64*refine+1)[1:]]
        self.dr = np.diff(self.r)
        self.N = np.array([[(1+1/math.sqrt(3))/2,(1-1/math.sqrt(3))/2],
                           [(1-1/math.sqrt(3))/2,(1+1/math.sqrt(3))/2]])
        self.rg = self.r[:-1,None]*self.N[None,:,0] + self.r[1:,None]*self.N[None,:,1]
        self.w = self.dr[:,None]/2*self.rg
        self.vol = (self.r[1:]**2-self.r[:-1]**2)/2
        self.max_balance_error=0.
        self.max_alpha_increment=0.
        self.max_mass_balance_error=0.
        self.steps=0

    def initial(self, profile):
        T=np.interp(self.r,DATA['radii_m'],profile['temperature_C'])
        a=np.repeat(np.asarray(profile['alpha']),self.refine)
        # Split consumed mass conservatively by cylindrical child-cell volume.
        cc=np.repeat(np.asarray(profile['char_consumed_kg_per_rad_m']),self.refine)
        if self.refine>1:
            parentvol=self.vol[:self.np].reshape(240,self.refine).sum(axis=1)
            cc*=self.vol[:self.np]/np.repeat(parentvol,self.refine)
        return State(profile['time_s'],T,np.repeat(a[:,None],2,axis=1),cc,
                     profile['layer']*self.refine,profile['gas_rate_kg_per_rad_m_s'],
                     profile['char_rate_kg_per_rad_m_s'],profile['qcond_surface_W_m2'])

    def front(self, s):
        a=s.alpha.mean(axis=1)
        j=next((i for i,v in enumerate(a) if v<.98),self.np)
        if j==0:return 0.
        if j==self.np:return 4.7625
        return (j-.5+(a[j-1]-.98)/(a[j-1]-a[j]))*4.7625/self.np

    def summary(self,s):
        return {'time_s':s.time,'outer_C':float(s.T[-1]),'interface_C':float(s.T[self.np]),
                'hot_C':float(s.T[s.layer]),'front98_mm':self.front(s),
                'removed_mm':1000*(self.r[s.layer]-.066675),
                'remaining_mm':1000*(.0714375-self.r[s.layer]),'layer':s.layer}

    def char_flux(self,T):
        law=CFG['char_law']; ratio=law['pressure_Pa']/law['pressure_reference_Pa']
        exponent=-law['activation_energy_J_mol']/R*(1/(T+273.15)-1/law['reference_temperature_K'])
        kin=law['reference_rate_kg_m2_s']*math.exp(max(-700,min(100,exponent)))*ratio**law['pressure_exponent']
        trans=law['mass_transfer_cap_kg_m2_s']*ratio
        return self.char_scale/(1/kin+1/trans) if kin>0 else 0.

    def boundary(self,s,dt):
        j=s.layer; hot_r=self.r[j]
        b=max(s.gas_rate+s.char_rate,0.)/hot_r*1600/1000
        h=1000*(b/math.expm1(b) if b>1e-7 else 1-b/2+b*b/12)
        available=max(600*self.vol[j]*s.alpha[j].mean()-s.consumed[j],0.)
        flux=min(s.alpha[j].mean()*self.char_flux(s.T[j]),
                 max(h*(2230.85-s.T[j])-self.qcond_scale*s.qcond,0.)/35e6,
                 available/(dt*hot_r),.2*600*self.vol[j]/(dt*hot_r))
        qrad=.25*SIGMA*((22+273.15)**4-(s.T[-1]+273.15)**4)*self.r[-1]
        return h,flux,qrad

    def step(self,s,dt,boundary=None,allow_removal=True):
        j=s.layer; nph=self.np-j
        if nph<=0:raise RuntimeError('Phenolic entirely removed')
        old=s.T[j:]; aa=s.alpha[j:]; NN=self.N
        Toldg=old[:-1,None]*NN[None,:,0]+old[1:,None]*NN[None,:,1]
        w=self.w[j:]; dr=self.dr[j:]; vol=self.vol[j:]
        hot_r=self.r[j]; outer_r=self.r[-1]
        h,flux,qrad=self.boundary(s,dt) if boundary is None else boundary
        ablation=flux*35e6*hot_r
        guess=old.copy()
        for iteration in range(60):
            Tg=guess[:-1,None]*NN[None,:,0]+guess[1:,None]*NN[None,:,1]
            mid=(Tg[:nph]+Toldg[:nph])/2
            rate=333*np.exp(-64081/(R*np.maximum(mid+273.15,1.)))
            anew=1-(1-aa)*np.exp(-rate*dt)
            da=anew-aa
            rho=1250-650*anew
            kv=np.interp(Tg[:nph],TABLE[:,0],TABLE[:,1])
            kc=np.interp(Tg[:nph],TABLE[:,0],TABLE[:,2])
            cv=np.interp(Tg[:nph],TABLE[:,0],TABLE[:,3])
            cc=np.interp(Tg[:nph],TABLE[:,0],TABLE[:,4])
            k=np.full(Tg.shape,167.); cap=np.full(Tg.shape,2700*896.)
            k[:nph]=self.k_scale*((1-anew)*kv+anew*kc)
            cap[:nph]=self.cp_scale*rho*((1-anew)*cv+anew*cc)
            sink=np.zeros(Tg.shape)
            sink[:nph]=(rho*418000+650*1600*np.maximum(mid+273.15-300,0.))*da/dt
            m00=np.sum(cap*w*NN[:,0]**2,axis=1)
            m11=np.sum(cap*w*NN[:,1]**2,axis=1)
            m01=np.sum(cap*w*NN[:,0]*NN[:,1],axis=1)
            stiff=np.sum(k*w,axis=1)/dr**2
            md=np.r_[m00,0.]+np.r_[0.,m11]
            kd=np.r_[stiff,0.]+np.r_[0.,stiff]
            diag=md/dt+kd
            off=m01/dt-stiff
            rhs=md/dt*old
            rhs[:-1]+=m01/dt*old[1:]
            rhs[1:]+=m01/dt*old[:-1]
            src0=np.sum(sink*w*NN[:,0],axis=1)
            src1=np.sum(sink*w*NN[:,1],axis=1)
            rhs-=np.r_[src0,0.]+np.r_[0.,src1]
            diag[0]+=h*hot_r;rhs[0]+=h*hot_r*2230.85-ablation
            diag[-1]+=8*outer_r;rhs[-1]+=8*outer_r*22+qrad
            band=np.zeros((3,len(old)));band[1]=diag;band[0,1:]=off;band[2,:-1]=off
            solved=solve_banded((1,1),band,rhs,check_finite=False)
            err=np.max(np.abs(solved-guess))
            if err<1e-7:
                guess=solved
                break
            guess=.7*solved+.3*guess
        else:
            return None
        if np.max(da)>.05+1e-9 or not np.all(np.isfinite(guess)):
            return None
        if np.min(guess)<21.999 or np.max(guess)>2230.851:
            raise RuntimeError(('Unphysical temperature',s.time,np.min(guess),np.max(guess)))
        delta=guess-old
        storage=np.sum((m00+m01)*delta[:-1]+(m11+m01)*delta[1:])/dt
        qnet=h*hot_r*(2230.85-guess[0])-ablation+8*outer_r*(22-guess[-1])+qrad-np.sum(sink*w)
        balance=abs(storage-qnet)/max(abs(storage),abs(qnet),1.)
        self.max_balance_error=max(self.max_balance_error,float(balance))
        self.max_alpha_increment=max(self.max_alpha_increment,float(np.max(da)))
        self.steps+=1
        T=s.T.copy();T[j:]=guess
        alpha=s.alpha.copy();alpha[j:]=anew
        consumed=s.consumed.copy();consumed[j]+=flux*hot_r*dt
        gas=float(np.sum(650*da*w[:nph]))
        layer=j
        remainder=float(np.sum(rho[0]*w[0])-consumed[j])
        eject=0.
        if self.removal and allow_removal and remainder<=.001*1250*vol[0]:
            layer+=1;eject=max(remainder,0.)
        front=layer-j
        qcond=float(np.mean(-k[front]*(guess[front+1]-guess[front])/dr[front]))
        mass_old=np.sum((1250-650*aa)*w[:nph])-np.sum(s.consumed[j:])
        mass_new=np.sum(rho[front:]*w[front:nph])-np.sum(consumed[layer:])
        mass_error=abs(mass_old-mass_new-gas-flux*hot_r*dt-eject)/max(abs(mass_old),1e-12)
        self.max_mass_balance_error=max(self.max_mass_balance_error,float(mass_error))
        if mass_error>1e-8:
            raise RuntimeError(('Mass balance failure',s.time,mass_error))
        return State(s.time+dt,T,alpha,consumed,layer,gas/dt,flux*hot_r,qcond,
                     s.gas_total+gas,s.char_total+flux*hot_r*dt,s.eject_total+eject)

    def advance(self,s,dt,substeps):
        if substeps==1:return self.step(s,dt)
        boundary=self.boundary(s,dt);new=s
        for i in range(substeps):
            new=self.step(new,dt/substeps,boundary=boundary,allow_removal=i==substeps-1)
            if new is None:return None
        new.gas_rate=(new.gas_total-s.gas_total)/dt
        return new

    def run(self,initial,end,dt=.0125,targets=None,stop_front=None,record_dt=.1,substeps=1):
        s=initial
        history=[self.summary(s)]; snapshots={}
        targets=sorted(targets or [])
        targets=[t for t in targets if t>s.time+1e-8]
        next_record=s.time+record_dt
        while s.time<end-1e-10:
            step=min(dt,end-s.time)
            if targets:step=min(step,targets[0]-s.time)
            while True:
                new=self.advance(s,step,substeps)
                if new is not None:break
                step/=2
                if step<1e-5:raise RuntimeError(('Reduced model did not converge',s.time))
            s=new
            if targets and abs(s.time-targets[0])<1e-8:
                snapshots[targets.pop(0)]=s
            if s.time>=next_record-1e-9 or s.time>=end-1e-9:
                history.append(self.summary(s));next_record=s.time+record_dt
            if stop_front is not None and self.front(s)>=stop_front:
                if abs(history[-1]['time_s']-s.time)>1e-10:
                    history.append(self.summary(s))
                break
        return s,history,snapshots


if __name__=='__main__':
    profiles=DATA['profiles']; model=RadialModel()
    start=model.initial(profiles[0])
    final,history,snaps=model.run(start,profiles[-1]['time_s'],targets=[p['time_s'] for p in profiles[1:]])
    comparisons=[]
    for p in profiles[1:]:
        pred=model.summary(snaps[p['time_s']]);truth=np.array(p['temperature_C'])
        comparisons.append({'time_s':p['time_s'],'outer_error_K':pred['outer_C']-truth[-1],
                            'interface_error_K':pred['interface_C']-truth[240],
                            'hot_error_K':pred['hot_C']-p['audit_hot_C'],
                            'profile_rmse_K':float(np.sqrt(np.mean((snaps[p['time_s']].T[max(p['layer'],snaps[p['time_s']].layer):]-truth[max(p['layer'],snaps[p['time_s']].layer):])**2)))})
    out={'history':history,'comparisons':comparisons,'max_energy_balance_relative':model.max_balance_error,
         'max_alpha_increment':model.max_alpha_increment,'steps':model.steps}
    (HERE/'baseline_model.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'last':history[-1],'comparisons':comparisons[-3:],'balance':model.max_balance_error,'steps':model.steps},indent=2))
