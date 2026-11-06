"""Moving, mass-lumped sector FE controller. Extensive quantities per radian per axial metre.

A linear thermal backend solves a new field from initial temperatures, nodal
capacities, element conductivities and applied heat. Chemistry, backing fusion
or decomposition, ambient exchange and recession are live states of this run.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import solve_banded
from scipy.optimize import brentq

from aluminium_phase_enthalpy import caloric, MELT_K, SOLID_K, LIQUID_K
from cf_backing_response import (CHI,DENSITY_LOSS,VIRGIN_DENSITY,conductivity,mixture,react)
from coupler import blowing,char_rate
from moving_surface_remap import remap
from moving_surface_thermochemistry import Chemistry,REFERENCE_C,recover_temperature,sensible
from radial_model import R,SIGMA,TABLE


def dual(nodes):
    """Bound each nodal storage volume with the exact row-summed brick shape weights."""
    a,b=nodes[:-1],nodes[1:]
    return np.r_[nodes[0],np.sqrt(a*a+(b-a)*(2*a+b)/3.),nodes[-1]]


def volume(edges):
    return np.diff(edges)*(edges[1:]+edges[:-1])*.5


def join(liner,back):
    """Assemble contributions at the shared liner/casing interface node."""
    return np.r_[liner[:-1],liner[-1]+back[0],back[1:]]


@dataclass
class FEState:
    time: float
    nodes: np.ndarray
    virgin: np.ndarray
    char: np.ndarray
    temperature: np.ndarray
    paths: np.ndarray
    bulk_gas_rate: float


@dataclass
class Block:
    radii: np.ndarray
    k: np.ndarray
    capacity: np.ndarray
    initial: np.ndarray
    load: np.ndarray
    hot_h: float
    outer_h: float
    dt: float
    facet: float


def banded(block):
    """Independently assemble the radial reduction of a straight-sided sector."""
    r=block.radii
    g=block.k*(r[:-1]+r[1:])/(2*np.diff(r)*block.facet**2)
    a=np.zeros((3,len(r)))
    a[1]=block.capacity/block.dt
    a[1,:-1]+=g
    a[1,1:]+=g
    a[0,1:]=a[2,:-1]=-g
    a[1,0]+=block.hot_h
    a[1,-1]+=block.outer_h
    # Solve increments to avoid subtracting large conductive matrix entries.
    q=g*(block.initial[:-1]-block.initial[1:])
    rhs=block.load.copy()
    rhs[:-1]-=q
    rhs[1:]+=q
    rhs[0]-=block.hot_h*block.initial[0]
    rhs[-1]-=block.outer_h*block.initial[-1]
    return block.initial+solve_banded((1,1),a,rhs)


class Retry(Exception):
    """Roll back the full macro-step and reduce its duration."""


class Sector:
    def __init__(self,cfg,n,nc):
        self.cfg=cfg
        self.mat=Chemistry.from_config(cfg)
        self.heat=cfg['heating']
        self.cf=cfg['case_material']=='cf'
        geom=cfg['geometry']
        self.inner=geom['inner_radius_m'];self.interface=geom['phenolic_outer_radius_m']
        self.case=np.linspace(self.interface,geom['outer_radius_m'],nc+1)
        self.facet=math.cos(math.radians(geom['angle_deg'])/(2*geom['angular_divisions']))
        self.case_initial_mass=volume(dual(self.case))*(VIRGIN_DENSITY if self.cf else cfg['material']['aluminium_density_kg_m3'])
        self.n=n;self.pitch=(self.interface-self.inner)/n
        melt=MELT_K-273.15
        self.al_t=np.r_[SOLID_K[:-1]-273.15,melt-.25,melt+.25,LIQUID_K[1:]-273.15]
        self.al_h=caloric(self.al_t,.5)[0]

    def initial(self):
        r=np.linspace(self.inner,self.interface,self.n+1)
        v=self.cfg['material']['virgin_reference_density_kg_m3']*volume(dual(r))
        t=np.full(len(r)+len(self.case)-1,self.cfg['initial_temperature_C'],dtype=float)
        return FEState(0.,r,v,0.*v,t,np.zeros((2,len(self.case))),0.)

    def back(self,temp,paths):
        if self.cf:
            extent=CHI@paths
            h,cp=mixture(temp,extent)
            return self.case_initial_mass*(1.-DENSITY_LOSS*extent),h,cp,conductivity(temp,extent)
        h,cp=caloric(temp,.5)
        return self.case_initial_mass,h,cp,np.full_like(temp,self.cfg['material']['aluminium_conductivity_W_m_K'])

    def inventory(self,s):
        n=len(s.virgin)
        if n:
            h=sensible(s.temperature[:n])
            liner_h=s.virgin@h[:,0]+s.char@h[:,1]
        else: liner_h=0.
        bm,bh,_,_=self.back(s.temperature[max(0,n-1):],s.paths)
        return float(sum(s.virgin+s.char)),float(sum(bm)),float(liner_h+bm@bh)

    def motion(self,s,dt):
        r=s.nodes[0];faces=dual(s.nodes)
        vol=volume(faces)
        v,c=s.virgin,s.char
        effective=c+self.mat.char_yield*v
        j=c[0]/effective[0]*char_rate(s.temperature[0],self.cfg['char_law'])
        def flux(radius): return j*(radius+r)/(2*self.facet)
        if j==0.: return r,dt,np.zeros_like(v),j
        end_dt=effective.sum()/flux(self.interface)
        if end_dt<=dt:
            return self.interface,end_dt,np.ones_like(v),j
        inventory=np.r_[0.,np.cumsum(effective)]
        positions=(faces-r)*(faces+r)/2.
        def balance(radius):
            x=(radius-r)*(radius+r)/2.
            return np.interp(x,positions,inventory)-dt*flux(radius)
        new=brentq(balance,r,self.interface,xtol=1e-15,rtol=9e-16)
        swept=np.clip((new-faces[:-1])*(new+faces[:-1])/(2.*vol),0.,1.)
        return new,dt,swept,j

    def _thermal(self,s,dt,rnew,swept,j,backend):
        n=len(s.virgin); y=self.mat.char_yield
        r=s.nodes[0]; area=.5*(r+rnew)/self.facet
        v,c=s.virgin,s.char
        swept_v,swept_c=v@swept,c@swept
        front_gas=(1.-y)*swept_v
        char_product=swept_c+y*swept_v
        film=blowing(self.heat['h0_W_m2_K'],(s.bulk_gas_rate+(front_gas+char_product)/dt)/area,self.mat.gas_cp_J_kg_K)
        char_cost=char_product*self.cfg['char_law']['effective_endothermic_cost_J_kg']
        front_cost=swept_v*self.mat.pyrolysis_J_per_kg_virgin+char_cost
        t0=s.temperature;tl0=t0[:n];tb0=t0[n-1:]
        l0=sensible(tl0);bm,bh0,_,_=self.back(tb0,s.paths)
        alpha=c/(c+y*v)
        radii=np.r_[s.nodes[:-1],self.case]
        surface=self.case[-1]/self.facet
        tg=self.heat['gas_temperature_C'];ta=self.heat['ambient_temperature_C']
        guess=t0.copy()
        def block(t):
            tl,tb=t[:n],t[n-1:]
            hs=sensible(tl)
            bm,bh,bc,bk=self.back(tb,s.paths)
            cpv=np.interp(tl,TABLE[:,0],TABLE[:,3]);cpc=np.interp(tl,TABLE[:,0],TABLE[:,4])
            ls=v*cpv+c*cpc
            delt=tl-tl0
            np.divide(v*(hs[:,0]-l0[:,0])+c*(hs[:,1]-l0[:,1]),delt,out=ls,where=abs(delt)>1e-6)
            delt=tb-tb0
            bs=bm*bc
            np.divide(bm*(bh-bh0),delt,out=bs,where=abs(delt)>1e-6)
            lk=(1.-alpha)*np.interp(tl,TABLE[:,0],TABLE[:,1])+alpha*np.interp(tl,TABLE[:,0],TABLE[:,2])
            k=np.r_[.5*(lk[:-1]+lk[1:]),.5*(bk[:-1]+bk[1:])]
            h_outer=self.heat['outer_h_W_m2_K']+self.heat['outer_emissivity']*SIGMA*(tb[-1]+ta+546.30)*((tb[-1]+273.15)**2+(ta+273.15)**2)
            rad=self.heat['hot_effective_emissivity']*SIGMA*((self.heat['radiative_temperature_C']+273.15)**4-(tl[0]+273.15)**4)
            swept_h=swept@(v*hs[:,0]+c*hs[:,1])
            products=front_gas*self.mat.gas_cp_J_kg_K*(tl[0]-REFERENCE_C)+char_product*hs[0,1]
            load=np.zeros_like(t)
            load[0]=area*(film*tg+rad)+(swept_h-products-front_cost)/dt
            load[-1]=surface*h_outer*ta
            b=Block(radii,k,join(ls,bs),t0,load,area*film,surface*h_outer,dt,self.facet)
            return b,dict(film=dt*area*film*(tg-tl[0]),radiation=dt*area*rad,
                          outer=dt*surface*h_outer*(tb[-1]-ta),face_cost=front_cost,face_products_h=products,
                          swept_h=swept_h,front_gas=front_gas,char_products=char_product)
        # Use a radial predictor, then solve the same unconstrained transient
        # with the selected backend. The returned backend field must satisfy
        # the original nodal energy equations before it can update any state.
        for _ in range(50):
            b,_=block(guess)
            trial=banded(b)
            delta=trial-guess
            if max(abs(delta))<2e-7: break
            guess+=min(1.,60./max(1.,max(abs(delta))))*delta
        else: raise Retry('Thermal predictor failed')
        for _ in range(6):
            b,_=block(trial)
            field=backend(b)
            if np.shape(field)!=np.shape(t0) or not np.all(np.isfinite(field)): raise RuntimeError('Invalid backend field')
            check,ledger=block(field)
            projected=banded(check)
            if max(abs(projected-field))<2e-6: return field,ledger
            trial=projected
        raise Retry('Backend and coupled heat equation differ')

    def equilibrate(self,v,c,lin_h,bt,paths):
        """Resolve the shared interface temperature without adding stored heat."""
        if not len(v): return bt
        lt=recover_temperature(v,c,lin_h)
        if abs(lt[-1]-bt[0])<1e-10: return np.r_[lt[:-1],bt]
        bm,bh,_,_=self.back(bt,paths)
        wanted=lin_h[-1]+bm[0]*bh[0]
        def residual(t):
            if self.cf: h=mixture(t,(CHI@paths)[0])[0]
            else: h=np.interp(t,self.al_t,self.al_h)
            return np.dot([v[-1],c[-1]],sensible(t))+bm[0]*h-wanted
        lo,hi=sorted((lt[-1],bt[0]))
        joint=brentq(residual,lo-1e-8,hi+1e-8,xtol=1e-11)
        return np.r_[lt[:-1],joint,bt[1:]]

    def _react_liner(self,v,c,old,dt):
        hp=sensible(old)
        old_h=v*hp[:,0]+c*hp[:,1]
        mid=old.copy()
        for _ in range(24):
            rate=333.*np.exp(-64081./(R*(mid+273.15)))
            lost=v*(-np.expm1(-rate*dt))
            nv=v-lost;nc=c+self.mat.char_yield*lost
            gas=(1.-self.mat.char_yield)*lost
            cost=lost*self.mat.pyrolysis_J_per_kg_virgin
            gh=gas*self.mat.gas_cp_J_kg_K*(mid-REFERENCE_C)
            h=old_h-cost-gh
            if np.any(lost/(v+c/self.mat.char_yield)>.05): raise Retry('Liner conversion increment')
            try: temperature=recover_temperature(nv,nc,h)
            except ValueError as exc: raise Retry('Liner caloric bracket') from exc
            next_mid=.5*(old+temperature)
            if max(abs(next_mid-mid))<1e-8:
                return nv,nc,h,float(sum(gas)),float(sum(cost)),float(sum(gh))
            mid=next_mid
        raise Retry('Liner reaction iteration')

    def advance(self,s,requested,backend=banded):
        if requested<=0 or not len(s.virgin): raise ValueError('Expected a live liner and positive time')
        dt=requested
        init_inventory=self.inventory(s)
        for cuts in range(25):
            try:
                new,dt,swept,rate=self.motion(s,dt)
                n=len(s.nodes)
                if n>2 and new-s.nodes[0]>.40*(s.nodes[1]-s.nodes[0]): raise Retry('Front crossed step limit')
                t,led=self._thermal(s,dt,new,swept,rate,backend)
                bt=t[n-1:].copy(); paths=s.paths
                if self.cf:
                    try: rx=react(bt,paths,dt,self.cfg.get('cf_catalyst',7.4886))
                    except ArithmeticError as exc: raise Retry('Backing reaction') from exc
                    if max((rx.paths-paths).sum(axis=0))>.04: raise Retry('Backing conversion increment')
                    bt,paths=rx.temperature,rx.paths
                    led.update(back_gas=self.case_initial_mass@rx.gas,back_gas_h=self.case_initial_mass@rx.gas_heat,
                               back_release=self.case_initial_mass@rx.reaction_heat)
                else: led.update(back_gas=0.,back_gas_h=0.,back_release=0.)
                if new==self.interface:
                    nodes=np.array([new]);v=c=lh=np.array([]);gas=cost=gas_h=0.;temp=bt
                else:
                    first=2 if n>2 and s.nodes[1]-new<.5*self.pitch else 1
                    nodes=np.r_[new,s.nodes[first:]]
                    old_edges=dual(s.nodes)
                    h=sensible(t[:n])
                    data=np.array([s.virgin,s.char,s.virgin*h[:,0]+s.char*h[:,1]])
                    if np.array_equal(nodes,s.nodes): v,c,lh=data
                    else:
                        transfer=remap(old_edges,data/volume(old_edges),dual(nodes))
                        v,c,lh=transfer.cell_integrals
                        if abs(transfer.removed_integrals[2]-led['swept_h'])>2e-7*max(1.,abs(led['swept_h'])):
                            raise RuntimeError('Geometric and surface enthalpy differ')
                    local=recover_temperature(v,c,lh)
                    v,c,lh,gas,cost,gas_h=self._react_liner(v,c,local,dt)
                    temp=self.equilibrate(v,c,lh,bt,paths)
                break
            except Retry:
                dt*=.5
        else: raise RuntimeError('Sector step exhausted cutbacks')
        result=FEState(s.time+dt,nodes,v,c,temp,paths,gas/dt)
        led.update(bulk_gas=gas,bulk_cost=cost,bulk_gas_h=gas_h)
        m0,b0,h0=init_inventory; m1,b1,h1=self.inventory(result)
        dm=m1-m0+gas+led['char_products']+led['front_gas']
        db=b1-b0+led['back_gas']
        energy=h1-h0-led['film']-led['radiation']+led['outer']+led['face_cost']+led['face_products_h']+cost+gas_h+led['back_gas_h']-led['back_release']
        scale=max(1.,abs(led['film'])+abs(led['radiation'])+abs(led['outer']))
        if abs(dm)>5e-11*max(m0,1e-3) or abs(db)>5e-11*b0 or abs(energy)>2e-5*scale:
            raise RuntimeError(f'Sector balance failed: liner {dm:g}, backing {db:g}, heat {energy:g}, scale {scale:g}')
        return result,led,dict(cutbacks=cuts,mass_error=dm,back_mass_error=db,energy_error=energy,
                              transport_hot_C=float(t[0]),transport_interface_C=float(t[n-1]),rate=rate)
