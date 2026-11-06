"""Assemble the *generated* brick input independently with eight Gauss points.

This is ordinary Python, without ANSYS. Run it with the guest interpreter to
verify portability, geometry, thermal masses, convection and the free fields.
"""
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import scipy
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import spsolve

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'configs/native_verification/whole_sector_r1'
ARCHIVE=PACKAGE/'controller.zip'
sys.path.insert(0,str(ARCHIVE))
from sector_exposure import integrate,balances,unpack
from sector_wall import Sector,banded
from sector_mapdl import commands,topology


def check_storage():
    guard=ROOT/'ansystmp'
    state=json.loads((guard/'host_storage_status.json').read_text())
    if ((guard/'STOP_WORK.json').exists() or not state['allowed'] or time.time()-state['checked_epoch']>45 or
        state['mac_free_bytes']<400_000_000_000 or shutil.disk_usage('C:/').free<10_000_000_000):
        raise RuntimeError('Storage guard')


def brick_geometry(coords):
    signs=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])
    store=np.zeros(coords.shape[:2])
    matrix=np.zeros((len(coords),8,8))
    for sample in itertools.product([-.5773502691896258,.5773502691896258],repeat=3):
        factors=1.+signs*np.array(sample)
        shape=factors.prod(axis=1)/8.
        deriv=shape[:,None]*signs/factors
        jac=coords.transpose(0,2,1)@deriv
        determinant=np.linalg.det(jac)
        if np.min(determinant)<=0: raise ValueError('Inverted brick')
        gradients=deriv@np.linalg.inv(jac)
        matrix+=(gradients@gradients.transpose(0,2,1))*determinant[:,None,None]
        store+=shape*determinant[:,None]
    return store,matrix


def assemble(block,geom,i):
    # Parse numeric input records independently of the radial assembly.
    nodes=[];solids={};ks={};klist=[];rs={};mass=[];loads={};films={};temps={}
    for line in commands(block,geom,i).splitlines():
        x=line.split(',')
        if x[0]=='N':
            assert int(x[1])==len(nodes)+1
            nodes.append(list(map(float,x[2:])))
        elif x[0]=='TYPE': typ=int(x[1])
        elif x[0]=='MAT': mat=int(x[1])
        elif x[:2]==['MP','KXX']: ks[int(x[2])]=float(x[3])
        elif x[0]=='R': rs[int(x[1])]=float(x[2])
        elif x[0]=='REAL': real=int(x[1])
        elif x[0]=='EN':
            if typ==1:
                solids[int(x[1])]=np.array(list(map(int,x[2:])))-1
                klist.append(ks[mat])
            else: mass.append((int(x[2])-1,rs[real]))
        elif x[0]=='SFE' and x[3:5]==['CONV','0']:
            films[int(x[1]),int(x[2])]=float(x[5])
        elif x[0]=='IC': temps[int(x[1])-1]=float(x[3])
        elif x[0]=='F': loads[int(x[1])-1]=float(x[3])
        elif x[0]=='D': raise ValueError('A temperature was prescribed')
    ids=np.array(list(solids.values()))
    xyz=np.array(nodes)
    parts,ke=brick_geometry(xyz[ids])
    nn=len(xyz)
    heat=np.zeros(nn);c=np.zeros(nn);h=np.zeros(nn)
    np.add.at(c,ids.ravel(),parts.ravel())
    for node,cap in mass: c[node]+=cap
    for node,load in loads.items(): heat[node]=load
    t0=np.array([temps[n] for n in range(nn)])
    for (elem,side),coeff in films.items():
        face=solids[elem][[3,0,4,7] if side==5 else [1,2,6,5]]
        p=xyz[face]
        area=np.linalg.norm(np.cross(p[1]-p[0],p[3]-p[0]))
        h[face]+=coeff*area/4.
    rows=np.broadcast_to(ids[:,:,None],ke.shape).ravel()
    columns=np.broadcast_to(ids[:,None,:],ke.shape).ravel()
    k=coo_matrix(((ke*np.array(klist)[:,None,None]).ravel(),(rows,columns)),shape=(nn,nn)).tocsr()
    field=spsolve(k+diags(c/block.dt+h),heat+c/block.dt*t0)
    weights=topology(block,geom)[4]
    ref=np.repeat(banded(block),len(weights))
    error=float(np.max(abs(ref-field)))
    if error>2e-6: raise ValueError(f'Full brick assembly differs by {error:g} K')
    return field.reshape(-1,len(weights))@weights,error


def main():
    check_storage()
    manifest=json.loads((PACKAGE/'manifest.json').read_text())
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==manifest['controller.zip']
    summary={}
    for job in ['pilotwal','pilotwcf']:
        config=PACKAGE/(job+'_settings.json')
        assert hashlib.sha256(config.read_bytes()).hexdigest()==manifest[config.name]
        settings=json.loads(config.read_text())
        errors=[]
        def backend(block):
            field,error=assemble(block,settings['configuration']['geometry'],1+len(errors))
            errors.append(error)
            return field
        rec=integrate(settings,backend,check_storage)
        summary[job]=dict(blocks=len(errors),max_3d_field_error_K=max(errors),terminal_s=rec['state']['time'],
                          balances=balances(settings,rec))
    warm_path=ROOT/'ansystmp/sector_reduction/guest_warm_states.json'
    raw=warm_path.read_bytes()
    warm=json.loads(raw)
    assert warm['archive_sha256']==manifest['controller.zip']
    stations={}
    for job,item in warm['cases'].items():
        source=PACKAGE/(job+'_settings.json')
        assert hashlib.sha256(source.read_bytes()).hexdigest()==item['settings_sha256']==manifest[source.name]
        setup=json.loads(source.read_text())
        wall=Sector(setup['configuration'],setup['n'],setup['nc'])
        values={}
        for name,frame in item['frames'].items():
            check_storage()
            errors=[]
            def late(block):
                field,error=assemble(block,wall.cfg['geometry'],1+len(errors))
                errors.append(error)
                return field
            state=unpack(frame['state'])
            new,_,_=wall.advance(state,frame['dt'],late)
            assert len(new.nodes)==frame['expected_nodes'] and abs(new.time-frame['expected_time_s'])<1e-8
            assert abs(new.temperature[0]-frame['expected_hot_C'])<2e-6
            values[name]=dict(start_s=state.time,end_s=new.time,start_radial_rows=len(state.nodes)-1,
                              end_radial_rows=len(new.nodes)-1,blocks=len(errors),max_3d_field_error_K=max(errors))
        stations[job]=values
    assert len(stations)==4 and all(len(item)==3 for item in stations.values())
    print(json.dumps(dict(passed=True,scope='Independent 3-D Gauss assembly in Windows CPython; no MAPDL call.',
               stations=stations,warm_source_sha256=hashlib.sha256(raw).hexdigest(),python=sys.version,numpy=np.__version__,scipy=scipy.__version__,jobs=summary,
               package_sha256=manifest['controller.zip'],audit_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())))


if __name__=='__main__': main()
