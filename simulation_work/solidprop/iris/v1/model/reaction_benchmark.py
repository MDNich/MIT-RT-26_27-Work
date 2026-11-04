"""Native isothermal UserMatTh conversion check against the analytic ODE."""
import argparse
import hashlib
import json
import math
import re
import shutil
import time
from prepare_model import create_mesh,write_model
from ops import ROOT,TMP,atomic,disks,guest

RUNTIME=TMP/'runs/reaction_benchmark'
WINDOWS=r'I:\ansystmp\runs\reaction_benchmark'


def prepare():
    disks();RUNTIME.mkdir(exist_ok=True)
    if (RUNTIME/'reaction.inp').exists():
        return json.loads((RUNTIME/'expectations.json').read_text())
    shutil.copy2(ROOT/'model/usermatthLib.dll',RUNTIME/'usermatthLib.dll')
    checks=[];driver=[]
    for temp in [300,600,1000]:
        cfg=json.loads((ROOT/'configs/sustainer_al.json').read_text())
        cfg['geometry'].update(phenolic_radial_rows=5,aluminium_radial_rows=5)
        cfg['initial_temperature_C']=temp
        mesh,nodes,elements=create_mesh(cfg)
        work=RUNTIME/f't{temp}';work.mkdir(exist_ok=True);write_model(cfg,nodes,elements,work)
        body=(work/'model_base.inp').read_text()
        body+='\n/SOLU\nANTYPE,TRANS,NEW\nNROPT,FULL\nTHOPT,FULL\nTRNOPT,FULL\nTINTP,,,,1\nAUTOTS,ON\nNEQIT,60\nKBC,1\nOUTRES,ALL,LAST\nOUTRES,SVAR,LAST\n'
        # Prescribed uniform phenolic temperature eliminates thermal-history
        # uncertainty; unconstrained isothermal casing nodes retain active DOFs.
        phnodes=sorted({n for eid,mat,nn in elements if mat==1 for n in nn})
        phelements=[eid for eid,mat,nn in elements if mat==1]
        for n in phnodes:body+=f'D,{n},TEMP,{temp}\n'
        for target in [.1,1,5]:
            prefix=f't{temp}_time{str(target).replace(".","p")}'
            body+=f'ALLSEL,ALL\nTIME,{target}\nDELTIM,.05,.0001,.05,OFF\nSOLVE\nFINISH\n/POST1\nSET,LAST\nESEL,S,MAT,,1\nETABLE,ERAS\nETABLE,ALPHA,SVAR,1\n*CFOPEN,{prefix},txt\n'
            for eid in phelements:
                body+=f'*GET,BA,ELEM,{eid},ETAB,ALPHA\n*VWRITE,{eid},BA\n(F8.0,1X,E24.16)\n'
            body+='*CFCLOSE\nFINISH\n/SOLU\n'
            alpha=1-math.exp(-333*math.exp(-64081/(8.31446261815324*(temp+273.15)))*target)
            checks.append(dict(temperature_C=temp,time_s=target,prefix=prefix,elements=phelements,expected_alpha=alpha))
        (RUNTIME/f't{temp}.inp').write_text(body+'FINISH\n')
        driver+=['/CLEAR,START',f'/INPUT,t{temp},inp']
    driver+=['/COM,IRIS_REACTION_BENCHMARK_COMPLETE','/EXIT,NOSAVE']
    (RUNTIME/'reaction.inp').write_text('\n'.join(driver)+'\n')
    atomic(RUNTIME/'expectations.json',checks)
    atomic(RUNTIME/'input_manifest.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(RUNTIME.glob('*.inp'))+list(RUNTIME.glob('*.dll'))})
    return checks


def execute():
    disks()
    for name,sha in json.loads((RUNTIME/'input_manifest.json').read_text()).items():
        assert hashlib.sha256((RUNTIME/name).read_bytes()).hexdigest()==sha
    exitfile=RUNTIME/'native_exit.json'
    if not exitfile.exists() and not (RUNTIME/'launch.json').exists():
        if (RUNTIME/'reaction.out').exists():raise RuntimeError('Prior output preserved; inspect before any launch')
        wrapper=r"""$ErrorActionPreference='Stop';$root='I:\ansystmp\runs\reaction_benchmark'
try {
$env:ANSYSLMD_LICENSE_FILE='1055@localhost';$env:ANS_USER_PATH=$root;$env:ANS_USER_PATH_261=$root;$env:ANS_USE_UPF=''
$p=Start-Process -FilePath 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j','reaction','-i','reaction.inp','-o','reaction.out') -Wait -PassThru
if($p.ExitCode -ne 0){throw "Native exit $($p.ExitCode)"}
@{ok=$true}|ConvertTo-Json|Set-Content ($root+'\native_exit.json')
} catch {@{ok=$false;error=$_.ToString()}|ConvertTo-Json|Set-Content ($root+'\native_exit.json');exit 1}
"""
        (RUNTIME/'dispatch.ps1').write_text(wrapper,encoding='utf-8-sig')
        atomic(TMP/'active_runs.json',[dict(relative_runtime=str(RUNTIME.relative_to(ROOT)),job='reaction',windows_root=WINDOWS)])
        script=r"$ErrorActionPreference='Stop';$r=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'});if($r.Count){throw 'Another solver is running'};"
        command='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+WINDOWS+'\\dispatch.ps1'
        script+="$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"+command+"';CurrentDirectory='"+WINDOWS+"'};if($r.ReturnValue -ne 0){throw 'WMI launch failed'};$r|Select-Object ProcessId,ReturnValue|ConvertTo-Json"
        atomic(RUNTIME/'launch.json',dict(result=guest(script)))
    started=time.monotonic()
    while not exitfile.exists():
        disks()
        if time.monotonic()-started>300:raise RuntimeError('Native fixture still pending; inspect instead of duplicating')
        time.sleep(5)
    result=json.loads(exitfile.read_text(encoding='utf-8-sig'));assert result['ok'],result


def validate(checks):
    log=(RUNTIME/'reaction.out').read_text(errors='replace')
    assert 'IRIS_REACTION_BENCHMARK_COMPLETE' in log
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    results=[]
    for c in checks:
        values={int(float(i)):float(a) for i,a in (line.split() for line in (RUNTIME/(c['prefix']+'.txt')).read_text().splitlines())}
        assert set(values)==set(c['elements'])
        error=max(abs(a-c['expected_alpha']) for a in values.values())
        assert error<2e-5,(c,error)
        results.append(dict(temperature_C=c['temperature_C'],time_s=c['time_s'],expected_alpha=c['expected_alpha'],native_min_alpha=min(values.values()),native_max_alpha=max(values.values()),max_absolute_error=error))
    out=dict(passed=True,qualification='Native prescribed-temperature software verification, not material calibration or a motor exposure',
        alpha_absolute_tolerance=2e-5,results=results,
        warning_count=int(re.findall(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',log)[-1]),
        warning_explanation='Nine standard USERCK warnings and nine near-zero heat-flow reference warnings in the deliberately isothermal prescribed-temperature fixture. Conversion is checked against the exact ODE at every sampled time.',
        log_sha256=hashlib.sha256((RUNTIME/'reaction.out').read_bytes()).hexdigest(),
        native_input_hashes=json.loads((RUNTIME/'input_manifest.json').read_text()))
    atomic(ROOT/'validation/reaction_benchmark.json',out)
    active=json.loads((TMP/'active_runs.json').read_text())
    if active and all(a.get('job')=='reaction' for a in active):atomic(TMP/'active_runs.json',[])
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    checks=prepare()
    if not a.prepare_only:execute();validate(checks)
    else:print('Prepared native isothermal conversion fixture; no solver launched')
