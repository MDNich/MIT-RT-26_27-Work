"""Identify the native UserMatTh temperature convention with uniform ramps."""
import argparse
import hashlib
import json
import math
import re
import shutil
import time
import uuid
from prepare_model import create_mesh, write_model
from ops import ROOT, TMP, atomic, disks, guest


def prepare(run, dll):
    disks();run.mkdir(exist_ok=True)
    if (run/'input_manifest.json').exists():
        return json.loads((run/'expectations.json').read_text())
    shutil.copy2(dll, run/'usermatthLib.dll')
    checks=[];driver=[]
    for start,end in [(300,600),(600,1000),(1000,600),(600,300),(600,600),(1000,1000)]:
        cfg=json.loads((ROOT/'configs/sustainer_al.json').read_text())
        cfg['geometry'].update(phenolic_radial_rows=5,aluminium_radial_rows=5)
        cfg['initial_temperature_C']=start
        mesh,nodes,elements=create_mesh(cfg)
        stem=f't{start}_to_{end}';work=run/stem;work.mkdir(exist_ok=True)
        write_model(cfg,nodes,elements,work)
        body=(work/'model_base.inp').read_text()
        body+='\n/SOLU\nANTYPE,TRANS,NEW\nNROPT,FULL\nTHOPT,FULL\nTRNOPT,FULL\nTINTP,,,,1\nAUTOTS,OFF\nNEQIT,60\nKBC,1\nOUTRES,ALL,LAST\nOUTRES,SVAR,LAST\n'
        phnodes=sorted({n for eid,mat,nn in elements if mat==1 for n in nn})
        phelements=[eid for eid,mat,nn in elements if mat==1]
        for n in phnodes:body+=f'D,{n},TEMP,{end}\n'
        body+='ALLSEL,ALL\nTIME,.01\nDELTIM,.01,.01,.01,OFF\nSOLVE\nFINISH\n/POST1\nSET,LAST\n'
        body+=f'*GET,BS,ACTIVE,0,SET,SBST\n*CFOPEN,{stem}_substep,txt\n*VWRITE,BS\n(F12.0)\n*CFCLOSE\nESEL,S,MAT,,1\nETABLE,ERAS\nETABLE,ALPHA,SVAR,1\n*CFOPEN,{stem}_alpha,txt\n'
        for eid in phelements:body+=f'*GET,BA,ELEM,{eid},ETAB,ALPHA\n*VWRITE,{eid},BA\n(F8.0,1X,E24.16)\n'
        body+='*CFCLOSE\nFINISH\n'
        (run/f'{stem}.inp').write_text(body)
        temperatures={'midpoint':(start+end)/2, 'end_plus_half_increment':end+(end-start)/2}
        predicted={mode:1-math.exp(-333*math.exp(-64081/(8.31446261815324*(T+273.15)))*.01)
                   for mode,T in temperatures.items()}
        checks.append(dict(stem=stem,start_C=start,end_C=end,dt_s=.01,elements=phelements,predicted_alpha=predicted))
        driver+=['/CLEAR,START',f'/FILNAME,{stem}',f'/INPUT,{stem},inp']
    driver+=['/COM,IRIS_RAMP_BENCHMARK_COMPLETE','/EXIT,NOSAVE']
    (run/'ramp.inp').write_text('\n'.join(driver)+'\n')
    atomic(run/'expectations.json', checks)
    files=list(run.glob('*.inp'))+list(run.glob('*.dll'))+[run/'expectations.json']
    atomic(run/'input_manifest.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    return checks


def execute(run):
    disks();windows='I:\\ansystmp\\runs\\'+run.name
    for name,sha in json.loads((run/'input_manifest.json').read_text()).items():
        assert hashlib.sha256((run/name).read_bytes()).hexdigest()==sha
    done=run/'native_exit.json'
    if not done.exists() and not (run/'launch_intent.json').exists():
        # The fixture is short and runs only after the serial queue has ended.
        guard=r"$r=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'});if($r.Count){throw 'Another native solver is active'};"
        guest("$ErrorActionPreference='Stop';"+guard)
        nonce=str(uuid.uuid4());atomic(run/'launch_intent.json',dict(nonce=nonce))
        wrapper="""$ErrorActionPreference='Stop';$root='WINDOWS'
try {
$env:ANSYSLMD_LICENSE_FILE='1055@localhost';$env:ANS_USER_PATH=$root;$env:ANS_USER_PATH_261=$root;$env:ANS_USE_UPF=''
$p=Start-Process -FilePath 'C:\\Program Files\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe' -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j','ramp','-i','ramp.inp','-o','ramp.out') -Wait -PassThru
if($p.ExitCode -ne 0){throw "Native exit $($p.ExitCode)"}
@{ok=$true}|ConvertTo-Json|Set-Content ($root+'\\native_exit.json')
} catch {@{ok=$false;error=$_.ToString()}|ConvertTo-Json|Set-Content ($root+'\\native_exit.json');exit 1}
""".replace('WINDOWS',windows)
        (run/'dispatch.ps1').write_text(wrapper,encoding='utf-8-sig')
        atomic(TMP/'active_runs.json',[dict(relative_runtime=str(run.relative_to(ROOT)),job='ramp',windows_root=windows)])
        command='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+windows+'\\dispatch.ps1'
        script="$ErrorActionPreference='Stop';"+guard
        script+="$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"+command+"';CurrentDirectory='"+windows+"'};if($r.ReturnValue -ne 0){throw 'WMI launch failed'};@{nonce='"+nonce+"';ProcessId=$r.ProcessId;ReturnValue=$r.ReturnValue}|ConvertTo-Json|Set-Content '"+windows+"\\receipt.json'"
        guest(script)
    started=time.monotonic()
    while not done.exists():
        disks()
        if time.monotonic()-started>120:raise RuntimeError('Existing native fixture still pending; do not duplicate')
        time.sleep(5)
    assert json.loads(done.read_text(encoding='utf-8-sig'))['ok']


def validate(run,checks,expected):
    log=(run/'ramp.out').read_text(errors='replace')
    assert 'IRIS_RAMP_BENCHMARK_COMPLETE' in log
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    rows=[]
    for c in checks:
        assert int(float((run/(c['stem']+'_substep.txt')).read_text()))==1
        values={int(float(i)):float(a) for i,a in (line.split() for line in (run/(c['stem']+'_alpha.txt')).read_text().splitlines())}
        assert set(values)==set(c['elements'])
        errors={mode:max(abs(a-predicted) for a in values.values()) for mode,predicted in c['predicted_alpha'].items()}
        assert errors[expected]<2e-7,(c,errors)
        rows.append(dict(start_C=c['start_C'],end_C=c['end_C'],dt_s=c['dt_s'],native_alpha=min(values.values()),predictions=c['predicted_alpha'],max_errors=errors))
    result=dict(passed=True,verified_convention=expected,qualification='Prescribed-temperature software diagnostic; not a motor exposure or material calibration.',
                results=rows,input_hashes=json.loads((run/'input_manifest.json').read_text()),
                log_sha256=hashlib.sha256((run/'ramp.out').read_bytes()).hexdigest())
    warnings=[part.split('\n\n')[0][:700] for part in log.split('*** WARNING ***')[1:]]
    assert all('USERCK' in w or 'reference heat flow' in w for w in warnings)
    result.update(warning_count=len(warnings),warning_explanation='Standard USERCK notices and near-zero reference heat flow in the two constant-temperature controls.',warning_blocks=warnings)
    atomic(ROOT/'validation'/f'{run.name}.json', result)
    atomic(TMP/'active_runs.json',[])
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime');p.add_argument('--dll',default=str(ROOT/'model/usermatthLib.dll'))
    p.add_argument('--expected',choices=['midpoint','end_plus_half_increment'],default='end_plus_half_increment');p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args();assert '/' not in a.runtime and '\\' not in a.runtime
    run=TMP/'runs'/a.runtime;checks=prepare(run,a.dll)
    if not a.prepare_only:execute(run);validate(run,checks,a.expected)
    else:print('Prepared; no native solve launched')
