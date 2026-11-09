"""Seal four-stage flush fixtures from the native open-contact preflight, without changing the original decks."""
import json
import re

from extend_board import SCREWS
from local_equilibrium import movement_deck
from stage_local_jobs import ROOT, digest, seal


def contact_deck():
    data=(ROOT/'model/local_pair_readback.inp').read_text()
    assert data.count('*DO,IP,861,862')==data.count('    ESEL,S,TYPE,,862')==1
    return data.replace('*DO,IP,861,862','*DO,IP,861,864').replace('    ESEL,S,TYPE,,862',
      '    *IF,IP,LE,862,THEN\n      ESEL,S,TYPE,,862\n    *ELSE\n      ESEL,S,TYPE,,864\n    *ENDIF')


def solid_deck():
    # Solid centroids: reversible elastic surrogate; these are not print failure allowables.
    lines=['ALLSEL,ALL','SET,LAST','*GET,NSAV,ACTIVE,0,SET,NSET','*CFOPEN,case_solid,csv',
           '*VWRITE',"('set,solids,seqv_MPa,e1_max,e3_min')",'*DO,IK,1,NSAV','  ALLSEL,ALL','  SET,,,,,,,IK',
           '  *GET,ISB,ACTIVE,0,SET,SBST','  *IF,ISB,EQ,999999,THEN','    *CYCLE','  *ENDIF',
           '  ESEL,S,TYPE,,850','  *GET,NSLD,ELEM,0,COUNT','  ETABLE,ERAS',
           '  ETABLE,VMS,S,EQV','  ETABLE,EP1,EPEL,1','  ETABLE,EP3,EPEL,3']
    for et,param,op in [('VMS','VM','MAX'),('EP1','EONE','MAX'),('EP3','ETHREE','MIN')]:
        lines+=['  ESORT,ETAB,'+et+',0,0',f'  *GET,{param},SORT,0,{op}']
    return '\n'.join(lines+['  *VWRITE,IK,NSLD,VM,EONE,ETHREE',"(F9.0,',',F9.0,3(',',E19.11))",
                            '*ENDDO','*CFCLOS','ALLSEL,ALL',''])


def stage():
    trial=ROOT/'.runtime/flush_approach_v1'
    proof=json.loads((ROOT/'validation/flush_approach_preflight.json').read_text())
    for file,key in [('pre.inp','preflight_sha256'),('pre.out','listing_sha256'),('trial.inp','trial_sha256')]:
        assert digest((trial/file).read_bytes())==proof[key]
    text=(trial/'pre.out').read_text(errors='replace')
    blocks=re.split(r'contact pair identified by real constant set\s+(\d+)',text,flags=re.I)
    pairs={int(i):s for i,s in zip(blocks[1::2],blocks[2::2])}
    for rid in range(861,865):
        b=pairs[rid]
        assert 'Max.  Initial penetration' not in b and re.search(r'User defined pinball region PINB\s+0\.60000',b)
        assert ('No contact was detected' in b) if rid==863 else ('Min.  Initial gap' in b)
    source='lateral_friction_locked'
    d=ROOT/'.runtime/local_inputs'/source
    ids=json.loads((ROOT/'validation/local_inputs.json').read_text())[source]['files']
    for name in ('model.inp','config.json','mesh.json','post_corrected.dat','run.dat'):
        assert digest((d/name).read_bytes())==ids[name]
    ref=(trial/'trial.inp').read_text()
    post=(d/'post_corrected.dat').read_text()
    assert post.startswith('RESUME,solved,db\n')
    post=post.replace('RESUME,solved,db','RESUME,model,db',1)
    # Do not allow a diagnostic nonconverged result to enter a history. Single endpoint
    # nodal/shell exports in legacy POST1 are unused; all decisions use indexed equilibria.
    post=post.replace('SET,,,,,,,II\n','SET,,,,,,,II\n*GET,ESUB,ACTIVE,0,SET,SBST\n*IF,ESUB,EQ,999999,THEN\n*CYCLE\n*ENDIF\n')
    moving=movement_deck(d,'pull',moving_screw_tops=True)
    marker='finish\n/exit,nosave'
    assert moving.count(marker)==1
    moving=moving.replace(marker,contact_deck()+solid_deck()+marker)
    manifest={}
    for mat,(e,nu,rho) in SCREWS.items():
        key=f'flush_{mat}_{source}_approach1'
        dest=ROOT/'.runtime/inputs'/key;dest.mkdir(exist_ok=True)
        deck=ref
        for prop,value in [('EX',e/1e6),('PRXY',nu),('DENS',rho*1e-12)]:
            pat=rf'(?m)^MP,{prop},851,[^\n]+$'
            deck,n=re.subn(pat,f'MP,{prop},851,{value}',deck)
            assert n==1
        if mat=='nylon':assert digest(deck.encode())==proof['trial_sha256']
        else:assert sum(a!=b for a,b in zip(deck.splitlines(),ref.splitlines(),strict=True))==3
        files={n:seal(dest/n,s.encode()) for n,s in [('model.inp',deck),('local_post.inp',post),('moving.inp',moving)]}
        spec=dict(case=key,source=source,cased=True,coupon=False,job='pull',cores=4,files=files,
                  load_protocol='four_stage_install',washer_lock_time=2.,installed_time=3.,end_time=4.,
                  top_travel_mm=3.,cell_pull_mm=.5,absolute_search_mm=.6,geometry_preflight_sha256=proof['listing_sha256'],
                  reference_trial_sha256=proof['trial_sha256'],screw_material=mat)
        manifest[key]=dict(source=source,spec_sha256=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode()),
                           input_sha256=files['model.inp'],preflight_sha256=proof['listing_sha256'])
    (ROOT/'validation/local_install_jobs.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':stage()
