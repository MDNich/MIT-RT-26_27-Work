"""Native controls for the two time tables and the substep contact-force tracker used in startup replay."""
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

from audit_local import ROOT, read, table
from audit_snug_transient_pilot import pair_tracker
from contact_transient import control_inputs, tables
from film_identity import digest, verified, write_json
from stage_local_jobs import seal
from stage_snug_fit import AUDIT

TRIAL='snug_transient_control_v1'


def signals():
    t,q,shapes,_=control_inputs()
    at=np.arange(513)/51200.
    acc=9*np.sin(2*np.pi*80*at)
    # The extra forcing vanishes at the coarse displacement knots.
    acc[1::2]+=15*np.sin(2*np.pi*60*at[1::2])
    return t,q,shapes,at,acc


def stage():
    rt=ROOT/'.runtime'
    old=rt/'patch_table_control_v1'/'control.inp'
    verified(old,read(ROOT/'validation/patch_table_control.json')['input_sha256'])
    touch=rt/'seat_surface_control_v1'/'control.inp'
    verified(touch,read(ROOT/'validation/seat_surface_control.json')['input_sha256'])
    dest=rt/TRIAL;dest.mkdir(exist_ok=True)
    t,q,shapes,at,acc=signals()
    legacy_deck=old.read_text()
    # Reproduce the old command block and all input arrays before substituting the independent acceleration table.
    with tempfile.TemporaryDirectory(dir=dest) as temp:
        _,_,_,legacy_acc=control_inputs()
        original,files=tables(Path(temp),np.array([1,3]),1+t,q,shapes,legacy_acc)
        hashes=read(ROOT/'validation/patch_table_control_input.json')['files']
        assert all(hashes[n]==v for n,v in files.items())
    dual,files=tables(dest,np.array([1,3]),1+t,q,shapes,acc,acceleration_time=1+at)
    source='\n'.join(original)
    assert legacy_deck.count(source)==1 and legacy_deck.count('nsubst,256')==1
    block=legacy_deck.replace(source,'\n'.join(dual)).replace('nsubst,256','nsubst,512')
    marker='/exit,nosave'
    assert block.count(marker)==1
    second=touch.read_text()
    assert second.startswith('/batch\n') and second.count('cncheck,detail,880,880')==1
    tracker='\n'.join(f'nlhist,pair,{name},cont,{component},880' for name,component in
                      [('pbfx','CFNX'),('pbfy','CFNY'),('pbfz','CFNZ'),('pbclosed','ELCN'),('pbpress','PRES'),('pbpen','PENE')])
    second=second.removeprefix('/batch\n').replace('cncheck,detail,880,880',tracker+'\ncncheck,detail,880,880')
    # A fresh database keeps the analytic oscillator and the two deformable contact bodies independent.
    deck=block.replace(marker,'/clear,nostart\n/filname,twoblock,1\n'+second)
    files['control.inp']=seal(dest/'control.inp',deck.encode())
    write_json(AUDIT/'transient_control_input.json',dict(case=TRIAL,files=files,
               original_spring_input_sha256=digest(old),original_contact_input_sha256=digest(touch)))


def audit():
    folder=ROOT/'.runtime'/TRIAL
    assert int((folder/'exit.txt').read_text(encoding='utf-8-sig'))==0
    src=read(AUDIT/'transient_control_input.json')
    for name,sha in src['files'].items():verified(folder/name,sha)
    listing=(folder/'control.out').read_text(errors='replace')
    errors=re.findall(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)',listing)
    assert errors and all(int(n)==0 for n in errors)
    t,q,shapes,at,acc=signals()
    ports=q@shapes[:,0,:].T
    drive=np.stack([np.interp(at,t,column) for column in ports.T],axis=1)
    a=table(folder/'control_response.csv');a=a[a['time']>=1]
    np.testing.assert_allclose(a['time']-1,at,rtol=0,atol=1e-10)
    drive_error=float(abs(np.c_[a['left_m'],a['right_m']]-drive).max())
    h=at[1];m=.2;k1,k2=150000.,90000.;k=k1+k2
    def response(base):
        f=k1*drive[:,0]+k2*drive[:,1]-m*base
        return lfilter([1,2,1],[4*m/h**2+k,2*k-8*m/h**2,4*m/h**2+k],f)
    error=float(abs(response(acc)-a['mass_m']).max())
    single_clock=float(abs(response(np.interp(at,t,acc[::2]))-a['mass_m']).max())
    assert drive_error<1e-10 and error<1e-7 and single_clock>1e-6 and single_clock>100*error
    seat=table(folder/'seat_control.csv')
    reference=table(ROOT/'.runtime/seat_surface_control_v1/seat_control.csv')
    assert len(seat)==len(reference)
    for key in reference.dtype.names:np.testing.assert_allclose(seat[key],reference[key],rtol=1e-5,atol=1e-7)
    x=pair_tracker(folder/'twoblock.nlh')
    np.testing.assert_allclose(x[:,0],seat['time'],rtol=1e-5,atol=1e-7)
    assert abs(x[:,1:3]).max()<1e-4 and np.max(abs(x[:,3]))>100
    sign=1 if (x[:,3]@seat['bot_F'])>0 else -1
    gap=float(abs(sign*x[:,3]-seat['bot_F']).max())
    assert gap<.3 and np.all((x[:,4]>0)==(seat['state']>=2))
    write_json(AUDIT/'transient_control.json',dict(input_sha256=src['files']['control.inp'],
               oscillator_csv_sha256=digest(folder/'control_response.csv'),contact_csv_sha256=digest(folder/'seat_control.csv'),
               tracker_sha256=digest(folder/'twoblock.nlh'),listing_sha256=digest(folder/'control.out'),
               oscillator_steps=len(at)-1,prescribed_error_m=drive_error,free_mass_error_m=error,
               single_clock_error_m=single_clock,contact_sets=len(seat),max_tracker_reaction_difference_N=gap,
               tracker_sign_relative_to_lower_block=sign,scope='Analytical time-table and two-block fixture verification.'))


if __name__=='__main__':
    {'stage':stage,'audit':audit}[sys.argv[1]]()
