"""Stage history-matched native MSUP cases for an accepted prestressed basis."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from seeded_motion import excitation, FS

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT.parent/'1/output/latex/random_vibration/reproduction/motion'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def seal(path, content):
    if path.exists() and path.read_bytes()!=content:
        raise ValueError(f'Existing motion input differs: {path}')
    if not path.is_file():
        path.parent.mkdir(exist_ok=True,parents=True)
        path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def enforced_deck(n):
    reference=(ROOT/'.runtime/inputs/bare_psd_X/model.inp').read_text()
    support=reference[reference.index('CMBLOCK,USERSELFSU'):reference.index('cmsel,s,USERSELFSU')]
    deck='/batch\nresume,file,db\nallsel,all\n'+support+'/solu\nantype,modal,restart\nfdele,all,all\nacel,0,0,0\nmodcont,,on\n'+f'mxpand,{n},,,yes,,yes\ncmsel,s,USERSELFSU\n'
    deck+='*get,PBNC,node,0,count\n*if,PBNC,ne,781,then\n*msg,fatal\nSupport node count mismatch.\n*endif\n'
    for dof in ('UX','UY','UZ'):
        deck+=f'cmsel,s,USERSELFSU\nnsel,r,d,{dof},0\n*get,PBNF,node,0,count\n*if,PBNF,ne,781,then\n*msg,fatal\nSupport DOFs were not all blocked in source modal model.\n*endif\n'
    return deck+'cmsel,s,USERSELFSU\nd,all,ux,1\nd,all,uy,2\nd,all,uz,3\nallsel,all\noutpr,all,none\nsolve\nsave,file,db\nfinish\n/exit,nosave\n'


def combine_deck(n):
    return f'/batch\n/aux2\ncombine,full\nfinish\nresume,file,db\n*get,F1,mode,1,freq\n*get,F{n},mode,{n},freq\n/com,MODE_RANGE=%F1% TO %F{n}%\n/exit,nosave\n'


def transient_deck(axis,n):
    return f""" /batch
resume,file,db
allsel,all
finish
/solu
antype,trans
trnopt,msup,{n},,1,yes,nmk,yes
mcfopt,1,0,0
dmprat,0.02
tintp,0,,,,,,,,1
kbc,1
outpr,all,none
outres,all,all
rescontrol,define,last,last
deltim,{1/FS:.16g}
dval,1,acc,0,,off
dval,2,acc,0,,off
dval,3,acc,0,,off
solve
*dim,PBACC,table,589825,1,,time
*tread,PBACC,acc,txt
dval,{'XYZ'.index(axis)+1},acc,%PBACC%,,off
time,9.0
solve
save,file,db
finish
/exit,nosave
""".lstrip()


def verify_sources(archive):
    source=archive/'outputs/random_motion_20261005_2143'
    decks={'basis/run.dat':enforced_deck(38),'basis_smp/combine.dat':combine_deck(38)}
    decks.update({f'transient_{axis}/run.dat':transient_deck(axis,38) for axis in 'XYZ'})
    digest={}
    for name,deck in decks.items():
        if deck!=(source/name).read_text():
            raise ValueError(f'October deck differs: {name}')
        digest[name]=hashlib.sha256(deck.encode()).hexdigest()
    inputs={}
    for axis in 'XYZ':
        path=source/f'inputs/{axis}_acc.txt'
        expected=json.loads((REFERENCE/f'inputs/{axis}_audit.json').read_text())
        if sha(path)!=expected['file_sha256']:
            raise ValueError('Historical acceleration table hash failed')
        samples=np.loadtxt(path,skiprows=1)
        t,acc,rms=excitation(axis)
        if not np.allclose(samples[:,0],t,rtol=0,atol=5.1e-13) or not np.allclose(samples[:,1],acc,rtol=1e-9,atol=1e-8):
            raise ValueError('Independent excitation differs from the sealed acceleration')
        target=ROOT/f'.runtime/motion_loads/{axis}.txt'
        inputs[axis]=dict(samples=len(t),rms_g=rms,sha256=seal(target,path.read_bytes()))
    out=dict(scope='Checked input decks for the October 38-mode case, and native forcing tables for the separate X, Y and Z repeats',decks=digest,inputs=inputs)
    (ROOT/'validation/motion_inputs.json').write_text(json.dumps(out,indent=2)+'\n')


def stage(branch,campaign):
    controls=json.loads((ROOT/'validation/motion_inputs.json').read_text())
    basis=json.loads((ROOT/f'validation/global/{branch}_basis.json').read_text())
    if basis['campaign']!=campaign or basis['case']!=branch+'_basis':
        raise ValueError('Basis identity mismatch')
    n=len(basis['frequencies_Hz'])
    if n<1 or n>60:
        raise ValueError('Unexpected number of retained modes')
    for suffix in ['enforced','motion_X','motion_Y','motion_Z']:
        name=f'{branch}_{suffix}'
        kind='enforced' if suffix=='enforced' else 'transient'
        dest=ROOT/'.runtime/inputs'/name
        spec=dict(case=name,branch=branch,campaign=campaign,kind=kind,modes=n,basis_rst_sha256=basis['rst_sha256'])
        if kind=='enforced':
            files={'model.inp':enforced_deck(n),'combine.inp':combine_deck(n)}
        else:
            axis=suffix[-1]
            files={'model.inp':transient_deck(axis,n)}
            load=ROOT/f'.runtime/motion_loads/{axis}.txt'
            if sha(load)!=controls['inputs'][axis]['sha256']:
                raise ValueError('Acceleration history changed')
            dest.mkdir(exist_ok=True,parents=True)
            local=dest/'acc.txt'
            if not local.exists():
                os.link(load,local)
            if sha(local)!=controls['inputs'][axis]['sha256']:
                raise ValueError('Staged acceleration history differs')
            spec.update(axis=axis,acc_sha256=controls['inputs'][axis]['sha256'])
        spec['files']={key:seal(dest/key,deck.encode()) for key,deck in files.items()}
        seal(dest/'motion_job.json',(json.dumps(spec,indent=2)+'\n').encode())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='action',required=True)
    v=commands.add_parser('verify-inputs');v.add_argument('archive',type=Path)
    s=commands.add_parser('stage');s.add_argument('branch');s.add_argument('campaign')
    a=p.parse_args()
    if a.action=='verify-inputs':verify_sources(a.archive)
    else:stage(a.branch,a.campaign)
