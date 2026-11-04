"""Independent cylindrical FE check of the documented thermal assumptions.

Two Gauss points per linear radial cell; row-summed heat capacity by default,
as used by SOLID278 without advection. No ANSYS result is manufactured here.
All results from this program must be labelled independent reduced-model data.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.linalg import solve_banded
from coupler import char_rate, blowing

TABLE=np.array([(22,.25,.30,900,800),(26.85,.25,.30,900,800),
 (326.85,.32,.35,1100,900),(626.85,.36,.40,1300,1000),
 (776.85,.36,.44,1300,1250),(926.85,.36,.49,1300,1550),
 (1226.85,.36,.68,1300,1950),(1426.85,.36,.81,1300,2060),
 (1926.85,.36,1.24,1300,2085),(2476.85,.36,1.73,1300,2090)])
SIGMA=5.670374419e-8
R=8.314462618

@dataclass
class State:
    time:float
    T:np.ndarray
    alpha:np.ndarray
    consumed:np.ndarray
    layer:int=0
    gas_rate:float=0.
    char_rate:float=0.
    qcond:float=0.
    gas_total:float=0.
    char_total:float=0.
    eject_total:float=0.

class RadialModel:
    def __init__(self,cfg,rows=None,case_rows=None,capacity='lumped',partial_capacity=False):
        self.c=cfg;g=cfg['geometry'];self.np=rows or g['phenolic_radial_rows']
        self.nc=case_rows or g['aluminium_radial_rows']
        self.r=np.r_[np.linspace(g['inner_radius_m'],g['phenolic_outer_radius_m'],self.np+1),
                     np.linspace(g['phenolic_outer_radius_m'],g['outer_radius_m'],self.nc+1)[1:]]
        self.dr=np.diff(self.r);self.vol=(self.r[1:]**2-self.r[:-1]**2)/2
        self.N=np.array([[(1+1/math.sqrt(3))/2,(1-1/math.sqrt(3))/2],
                         [(1-1/math.sqrt(3))/2,(1+1/math.sqrt(3))/2]])
        self.rg=self.r[:-1,None]*self.N[None,:,0]+self.r[1:,None]*self.N[None,:,1]
        self.w=self.dr[:,None]/2*self.rg
        self.capacity=capacity;self.partial_capacity=partial_capacity
        self.max_energy_error=0.;self.max_mass_error=0.;self.max_alpha_increment=0.
        self.steps=0;self.max_retained_fraction=0.;self.event_bracket=None;self.property_bracket=None

    def initial(self):
        return State(0.,np.full(len(self.r),self.c['initial_temperature_C'],dtype=float),
                     np.zeros((self.np,2)),np.zeros(self.np))

    def boundary(self,s,dt):
        hcfg=self.c['heating'];law=self.c['char_law'];m=self.c['material']
        j=s.layer;r=self.r[j]
        pulse=hcfg.get('pulse_duration_s',math.inf)
        on=s.time<pulse-1e-10
        h0=hcfg['h0_W_m2_K'] if on else hcfg.get('post_pulse_h_W_m2_K',8.)
        Tg=hcfg['gas_temperature_C'] if on else hcfg['ambient_temperature_C']
        h=blowing(h0,(s.gas_rate+s.char_rate)/r,hcfg['gas_cp_J_kg_K']) if on else h0
        qhot=hcfg['hot_effective_emissivity']*SIGMA*((hcfg['radiative_temperature_C']+273.15)**4-(s.T[j]+273.15)**4) if on else 0.
        a=float(np.sum(s.alpha[j]*self.w[j])/self.vol[j]);rc=m['char_reference_density_kg_m3']
        available=max(rc*self.vol[j]*a-s.consumed[j],0.)
        flux=min(a*char_rate(s.T[j],law),max(h*(Tg-s.T[j])+qhot-s.qcond,0.)/law['effective_endothermic_cost_J_kg'],
                 available/(dt*r),self.c['numerics']['max_char_fraction_per_step']*rc*self.vol[j]/(dt*r)) if on else 0.
        qouter=hcfg['outer_emissivity']*SIGMA*((hcfg['ambient_temperature_C']+273.15)**4-(s.T[-1]+273.15)**4)*self.r[-1]
        return h,Tg,flux,qhot,qouter

    def step(self,s,dt):
        j=s.layer;nph=self.np-j
        if nph<=0:raise RuntimeError('Phenolic already consumed')
        c=self.c;m=c['material'];hcfg=c['heating'];rv=m['virgin_reference_density_kg_m3'];rc=m['char_reference_density_kg_m3']
        old=s.T[j:];aa=s.alpha[j:];NN=self.N;w=self.w[j:];dr=self.dr[j:];vol=self.vol[j:]
        Toldg=old[:-1,None]*NN[None,:,0]+old[1:,None]*NN[None,:,1]
        h,Tgas,flux,qhot,qouter=self.boundary(s,dt)
        ablation=flux*c['char_law']['effective_endothermic_cost_J_kg']*self.r[j]
        guess=old.copy()
        for iteration in range(90):
            Tg=guess[:-1,None]*NN[None,:,0]+guess[1:,None]*NN[None,:,1]
            mid=(Tg[:nph]+Toldg[:nph])/2
            rate=333*np.exp(-64081/(R*np.maximum(mid+273.15,1.)))
            anew=1-(1-aa)*np.exp(-rate*dt);da=anew-aa;rho=rv-(rv-rc)*anew
            kv,kc,cv,cc=[np.interp(Tg[:nph],TABLE[:,0],TABLE[:,i]) for i in range(1,5)]
            if c['case_material']=='cf':
                k=np.full(Tg.shape,c['cf_radial_k'])
                cp=np.full(Tg.shape,c['cf_cp_constant_J_kg_K']) if 'cf_cp_constant_J_kg_K' in c else 2.8773*np.clip(Tg,20,200)+687.31
                cap=m['aluminium_density_kg_m3']*cp*c.get('cf_cp_scale',1.)
            else:
                k=np.full(Tg.shape,m['aluminium_conductivity_W_m_K'])
                cap=np.full(Tg.shape,m['aluminium_density_kg_m3']*m['aluminium_heat_capacity_J_kg_K'])
            k[:nph]=((1-anew)*kv+anew*kc)*m.get('phenolic_k_scale',1.)
            cap[:nph]=rho*((1-anew)*cv+anew*cc)*m.get('phenolic_cp_scale',1.)
            if self.partial_capacity:
                cap[0]*=np.maximum(rho[0]-s.consumed[j]/vol[0],1e-6)/rho[0]
            sink=np.zeros(Tg.shape)
            sink[:nph]=(rho*m['pyrolysis_enthalpy_J_kg']+(rv-rc)*hcfg['gas_cp_J_kg_K']*np.maximum(mid+273.15-300,0.))*da/dt
            m00=np.sum(cap*w*NN[:,0]**2,axis=1);m11=np.sum(cap*w*NN[:,1]**2,axis=1);m01=np.sum(cap*w*NN[:,0]*NN[:,1],axis=1)
            if self.capacity=='lumped':
                m00+=m01;m11+=m01;m01=np.zeros_like(m01)
            stiff=np.sum(k*w,axis=1)/dr**2
            md=np.r_[m00,0.]+np.r_[0.,m11];kd=np.r_[stiff,0.]+np.r_[0.,stiff]
            diag=md/dt+kd;off=m01/dt-stiff
            rhs=md/dt*old;rhs[:-1]+=m01/dt*old[1:];rhs[1:]+=m01/dt*old[:-1]
            src0=np.sum(sink*w*NN[:,0],axis=1);src1=np.sum(sink*w*NN[:,1],axis=1)
            rhs-=np.r_[src0,0.]+np.r_[0.,src1]
            diag[0]+=h*self.r[j];rhs[0]+=h*self.r[j]*Tgas-ablation+qhot*self.r[j]
            diag[-1]+=hcfg['outer_h_W_m2_K']*self.r[-1]
            rhs[-1]+=hcfg['outer_h_W_m2_K']*self.r[-1]*hcfg['ambient_temperature_C']+qouter
            band=np.zeros((3,len(old)));band[1]=diag;band[0,1:]=off;band[2,:-1]=off
            solved=solve_banded((1,1),band,rhs,check_finite=False)
            err=np.max(np.abs(solved-guess))
            if err<1e-7:guess=solved;break
            guess=.7*solved+.3*guess
        else:return None
        if np.max(da)>.05+1e-9 or not np.all(np.isfinite(guess)):return None
        delta=guess-old
        storage=np.sum((m00+m01)*delta[:-1]+(m11+m01)*delta[1:])/dt
        qnet=h*self.r[j]*(Tgas-guess[0])-ablation+qhot*self.r[j]+hcfg['outer_h_W_m2_K']*self.r[-1]*(hcfg['ambient_temperature_C']-guess[-1])+qouter-np.sum(sink*w)
        balance=abs(storage-qnet)/max(abs(storage),abs(qnet),1.)
        self.max_energy_error=max(self.max_energy_error,float(balance));self.max_alpha_increment=max(self.max_alpha_increment,float(np.max(da)));self.steps+=1
        if balance>1e-6:raise RuntimeError(('Radial energy balance',s.time,balance))
        T=s.T.copy();T[j:]=guess;alpha=s.alpha.copy();alpha[j:]=anew
        consumed=s.consumed.copy();consumed[j]+=flux*self.r[j]*dt
        gas=float(np.sum((rv-rc)*da*w[:nph]));remainder=float(np.sum(rho[0]*w[0])-consumed[j]);layer=j;eject=0.
        if remainder<=c['numerics']['row_residual_mass_fraction']*rv*vol[0]:layer+=1;eject=max(remainder,0.)
        front=layer-j
        qcond=float(np.mean(-k[front]*(guess[front+1]-guess[front])/dr[front])) if layer<self.np else 0.
        mass_old=np.sum((rv-(rv-rc)*aa)*w[:nph])-np.sum(s.consumed[j:])
        mass_new=np.sum(rho[front:]*w[front:nph])-np.sum(consumed[layer:])
        mass_error=abs(mass_old-mass_new-gas-flux*self.r[j]*dt-eject)/max(abs(mass_old),1e-12)
        self.max_mass_error=max(self.max_mass_error,float(mass_error))
        if mass_error>1e-8:raise RuntimeError(('Radial mass balance',s.time,mass_error))
        self.max_retained_fraction=max(self.max_retained_fraction,float(consumed[j]/(rv*np.sum(self.vol[:self.np]))))
        if layer==self.np:self.event_bracket=[s.time,s.time+dt]
        return State(s.time+dt,T,alpha,consumed,layer,gas/dt,flux*self.r[j],qcond,s.gas_total+gas,s.char_total+flux*self.r[j]*dt,s.eject_total+eject)

    def summary(self,s):
        a=np.sum(s.alpha*self.w[:self.np],axis=1)/self.vol[:self.np]
        front=s.layer
        while front<self.np and a[front]>=.98:front+=1
        initial=self.c['geometry']['phenolic_thickness_m']
        return dict(time_s=s.time,hot_C=float(s.T[s.layer]),interface_C=float(s.T[self.np]),outer_C=float(s.T[-1]),
                    remaining_mm=1000*(self.r[self.np]-self.r[s.layer]),removed_mm=1000*(self.r[s.layer]-self.r[0]),
                    front98_upper_cell_mm=front*initial*1000/self.np,layer=s.layer,
                    case_property_range_exceeded=bool(s.T[self.np]>self.c['case_property_limit_C']),
                    solid_remaining_kg_per_rad_m=float(np.sum((self.c['material']['virgin_reference_density_kg_m3']-(self.c['material']['virgin_reference_density_kg_m3']-self.c['material']['char_reference_density_kg_m3'])*s.alpha[s.layer:])*self.w[s.layer:self.np])-np.sum(s.consumed[s.layer:])))

    def run(self,end,dt=.0125,record_dt=.1,targets=(),check=None,stop_at_property_limit=False,post_dt=None):
        s=self.initial();history=[self.summary(s)];snapshots={};targets=sorted(t for t in targets if t>0);next_record=record_dt
        while s.time<end-1e-10 and s.layer<self.np:
            if check and self.steps%200==0:check()
            pulse=self.c['heating'].get('pulse_duration_s',math.inf)
            step=min(post_dt if post_dt is not None and s.time>=pulse-1e-10 else dt,end-s.time)
            if s.time<pulse-1e-10:step=min(step,pulse-s.time)
            elif self.c.get('post_pulse_initial_duration_s',0)>0:
                initial_end=pulse+self.c['post_pulse_initial_duration_s']
                if s.time<initial_end-1e-10:
                    step=min(step,self.c['post_pulse_initial_dt_s'],initial_end-s.time)
            if targets:step=min(step,targets[0]-s.time)
            while True:
                new=self.step(s,step)
                if new is not None:break
                step/=2
                if step<1e-6:raise RuntimeError(('Radial convergence failure',s.time))
            oldlayer=s.layer;oldtime=s.time;s=new
            crossed=s.T[self.np]>self.c['case_property_limit_C']
            if crossed and self.property_bracket is None:self.property_bracket=[oldtime,s.time]
            if targets and abs(s.time-targets[0])<1e-8:snapshots[targets.pop(0)]=s
            if s.time>=next_record-1e-9 or s.time>=end-1e-9 or s.layer!=oldlayer or (crossed and stop_at_property_limit):
                history.append(self.summary(s));next_record=s.time+record_dt
            if crossed and stop_at_property_limit:break
        return s,history,snapshots
