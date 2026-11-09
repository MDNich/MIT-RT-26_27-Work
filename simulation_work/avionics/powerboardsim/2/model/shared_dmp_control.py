"""Check distributed MAPDL output and a second-session perturbation restart on shared study scratch."""
import sys

import numpy as np

from audit_local import ROOT,read,table
from film_identity import digest,write_json
from native_rst import read_rst
from stage_local_jobs import seal

TRIAL='shared_dmp_io_v1'


def stage():
    d=ROOT/'.runtime'/TRIAL;d.mkdir(exist_ok=True)
    base=['/batch','/prep7','et,1,link180','mp,ex,1,70e9','mp,prxy,1,0','mp,dens,1,2700',
          'sectype,1,link','secdata,1e-4','type,1','mat,1','secnum,1']
    for i in range(121):base.append(f'n,{i+1},{.3*i/120:.12g},0,0')
    for i in range(1,121):base.append(f'e,{i},{i+1}')
    base+=['d,all,uy,0','d,all,uz,0','d,1,ux,0','f,121,fx,1000','finish','/solu','antype,static',
           'rescontrol,linear,all','time,1','nsubst,1,1,1','outres,all,all','solve','finish','/post1','set,last',
           '*get,u,node,121,u,x','*get,rf,node,1,rf,fx','*cfopen,axial,csv','*vwrite', "('tip_m,support_N')",
           '*vwrite,u,rf',"(E18.10,',',E18.10)",'*cfclos','finish','/exit,nosave']
    modal=['/batch','/solu','antype,,restart,1,,perturb','perturb,modal,,current,dzerokeep','solve,elform',
           'modopt,lanb,6','mxpand,6,,,yes','solve','finish','/exit,nosave']
    files={name:seal(d/name,('\n'.join(cards)+'\n').encode()) for name,cards in [('control.inp',base),('modal.inp',modal)]}
    write_json(ROOT/'validation/shared_dmp_control_input.json',dict(trial=TRIAL,files=files,ranks=12))


def audit():
    d=ROOT/'.runtime'/TRIAL
    receipt=read(d/'result.json');assert receipt['trial']==TRIAL and receipt['static_exit']==receipt['modal_exit']==0
    source=read(ROOT/'validation/shared_dmp_control_input.json')
    for name,h in source['files'].items():assert digest(d/name)==h
    paths=[d/'work'/x for x in ('static','modal')]
    import re
    status=[]
    for path,deck in zip(paths,['control.inp','modal.inp'],strict=True):
        assert digest(path/deck)==source['files'][deck]
        log=(path/'solve.out').read_text(errors='replace')
        assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log) and 'RUN COMPLETED' in log
        assert re.search(r'12\s+PARALLEL PROCESSES REQUESTED',log,re.I) or re.search(r'Number of (?:MPI )?processes\s*[:=]\s*12\b',log,re.I)
        status.append(digest(path/'solve.out'))
    a=table(paths[0]/'axial.csv')
    expected_tip=1000*.3/(70e9*1e-4)
    assert np.isclose(a['tip_m'][0],expected_tip,rtol=1e-7) and abs(a['support_N'][0]+1000)<1.e-4
    r=read_rst(paths[1]/'file.rstp',parse_vtk=False)
    exact=(2*np.arange(6)+1)*np.sqrt(70e9/2700)/(4*.3)
    errors=np.abs(r.time_values/exact-1)
    assert r.nsets==6 and np.all(np.diff(r.time_values)>0) and max(errors)<.002
    write_json(ROOT/'validation/shared_dmp_control.json',dict(trial=TRIAL,ranks=12,input_hashes=source['files'],
        listings=status,static_RST_sha256=digest(paths[0]/'file.rst'),modal_RST_sha256=digest(paths[1]/'file.rstp'),
        axial_displacement_m=float(a['tip_m'][0]),support_force_N=float(a['support_N'][0]),
        first_six_native_Hz=r.time_values.tolist(),maximum_relative_frequency_error=float(max(errors)),
        local_free_bytes_before=receipt['initial_free'],local_free_bytes_after=receipt['final_free'],
        scope='Distributed shared-directory file and restart check on a 120-link rod. Larger production cases require their own audits.'))


if __name__=='__main__':{'stage':stage,'audit':audit}[sys.argv[1]]()
