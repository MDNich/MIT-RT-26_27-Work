"""Seal whole-wall MAPDL inputs with a portable thermochemistry snapshot.

Builds the embedded Python modules deterministically. The portable CF constants
are the literal assignments of the archived study source; its workstation-only
diagnostic runner is excluded from the embedded interpreter.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED,ZipFile,ZipInfo

from check_sector_exposure import FILES,OUT,PLAN
from ops import ROOT,UNC,disks

PACKAGE=ROOT/'configs/native_verification/whole_sector_r1'
NAMES=['sustainer_al','sustainer_cf','booster_al','booster_cf']
JOBS=('pilotwal','pilotwcf','wallsa','wallsc','wallba','wallbc')


def sha(data): return hashlib.sha256(data).hexdigest()


def portable():
    buf=io.BytesIO()
    with ZipFile(buf,'w') as z:
        for name in sorted([*FILES,'sector_mapdl']):
            path=ROOT/f'model/{name}.py'
            data=path.read_bytes()
            if name=='diagnose_cf_backing':
                text=data.decode()
                wanted={'A','CHI','DENSITY_LOSS','E','N','RGAS'}
                keep=[n for n in ast.parse(text).body if isinstance(n,ast.Assign)
                      and any(isinstance(t,ast.Name) and t.id in wanted for t in n.targets)]
                assert len(keep)==len(wanted)
                data=('import numpy as np\n'+'\n'.join(ast.get_source_segment(text,n) for n in keep)+'\n').encode()
            z.writestr(ZipInfo(name+'.py',(2026,1,1,0,0,0)),data,compress_type=ZIP_DEFLATED)
    return buf.getvalue()


def materials():
    rows=json.loads(PLAN.read_text())['cases']
    cases={}
    for row in rows[:4]:
        cfg=row['configuration']
        # Whitelist only inputs actually consumed. Pulse cutoff and earlier
        # material libraries must never be inherited as a hidden firing history.
        out={k:cfg[k] for k in ('case_id','geometry','case_material','case_property_limit_C','heating',
                                'char_law','material','initial_temperature_C')}
        out['geometry']={k:cfg['geometry'][k] for k in ('angle_deg','angular_divisions','axial_divisions',
                       'inner_radius_m','phenolic_outer_radius_m','outer_radius_m','length_m')}
        out['heating']={k:v for k,v in cfg['heating'].items() if not k.startswith('post_pulse')}
        cases[row['case']]=out
    assert list(cases)==NAMES
    return cases


def build():
    audit=json.loads(OUT.read_text())
    assert audit['passed'] and sha(PLAN.read_bytes())==audit['config_sha256']
    for name,digest in audit['sources'].items():
        assert sha((ROOT/f'model/{name}.py').read_bytes())==digest
    files={'controller.zip':portable()}
    archive_sha=sha(files['controller.zip'])
    reference=materials()
    for job,case in zip(JOBS,[*NAMES[:2],*NAMES]):
        pilot=job.startswith('pilot')
        settings=dict(job=job,case=case,n=80,nc=20,dt_s=.04,horizon_s=.1 if pilot else 220.,
                      configuration=reference[case],role='pilot' if pilot else 'exhaustion')
        config=(json.dumps(settings,indent=2)+'\n').encode()
        files[job+'_settings.json']=config
        archive=UNC+r'\configs\native_verification\whole_sector_r1'
        lines=['/CLEAR,NOSTART','! In-process controller. Native execution and acceptance are separate.',
               '*PYTHON','import hashlib, json, sys','from pathlib import Path',f'pkg = Path({archive!r})',
               "archive = pkg / 'controller.zip'",f'signature = {archive_sha!r}',
               "if hashlib.sha256(archive.read_bytes()).hexdigest() != signature:",
               "    raise RuntimeError('Controller package hash mismatch')",
               f"raw = (pkg / '{job}_settings.json').read_bytes()",f"if hashlib.sha256(raw).hexdigest() != '{sha(config)}':",
               "    raise RuntimeError('Configuration hash mismatch')","sys.path.insert(0,str(archive))",
               'from sector_mapdl import execute',f'execute(mapdl,json.loads(raw),signature,{UNC!r})',
               '*ENDPY','/COM,IRIS_WHOLE_SECTOR_RETURNED','/EXIT,NOSAVE']
        assert max(map(len,lines))<250
        deck=('\n'.join(lines)+'\n').encode('ascii')
        files[job+'.inp']=deck
        data=dict(job=job,case=case,deck_sha256=sha(deck),settings_sha256=sha(config),controller_sha256=archive_sha,
                  independent_reference_sha256=sha(OUT.read_bytes()),thermal_field_tolerance_K=2e-6,
                  max_transverse_range_K=.001,mass_and_energy_relative=1e-7,max_event_difference_fraction=.01)
        files[job+'.json']=(json.dumps(data,indent=2)+'\n').encode()
    files['manifest.json']=(json.dumps({k:sha(v) for k,v in files.items()},indent=2)+'\n').encode()
    return files


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','verify-input'])
    args=parser.parse_args()
    disks()
    files=build()
    if args.action=='prepare':
        PACKAGE.mkdir(exist_ok=False)
        for name,data in files.items(): (PACKAGE/name).write_bytes(data)
    for name,data in files.items():
        if (PACKAGE/name).read_bytes()!=data: raise RuntimeError('Sealed package differs: '+name)
    print('Verified four complete exposure inputs and two pilot inputs.')


if __name__=='__main__': main()
