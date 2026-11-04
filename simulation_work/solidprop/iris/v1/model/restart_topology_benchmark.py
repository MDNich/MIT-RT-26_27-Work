"""Transient removal/restart regression, including the old resurrection defect.

Compare continuous solves, restarts with full EKILL replay, and a deliberately
broken pending-only replay. Constant properties isolate topology from chemistry.
"""
import hashlib,json,re,time,uuid
from pathlib import Path
from prepare_model import create_mesh,write_model
from coupler import prepare_step,initial_state
from ops import ROOT,TMP,atomic,disks,guest
RUNTIME=TMP/'runs/restart_topology_benchmark_v3'
WINDOWS=r'I:\ansystmp\runs\restart_topology_benchmark_v3'
CASES=['sustainer_al','sustainer_cf','booster_al','booster_cf']

def prepare():
    disks();RUNTIME.mkdir(exist_ok=True)
    if (RUNTIME/'benchmark.inp').exists():return
    driver=[]
    for case in CASES:
        cfg=json.loads((ROOT/'configs'/f'{case}.json').read_text())
        cfg['geometry'].update(phenolic_radial_rows=5,aluminium_radial_rows=5)
        cfg['end_time_s']=1.
        cfg['heating'].update(gas_temperature_C=100.,hot_effective_emissivity=0.,outer_emissivity=0.)
        cfg['char_law']['reactive_activity']=0.
        mesh,nodes,elements=create_mesh(cfg)
        for mode in ['continuous','replay','pending_only']:
            stem=case+'_'+mode;work=RUNTIME/stem;work.mkdir(exist_ok=True)
            write_model(cfg,nodes,elements,work)
            b=(work/'model_base.inp').read_text();start=b.index('! Phenolic UserMatTh:');stop=b.index('MP,KXX,2,',start)
            b=b[:start]+'MP,KXX,1,.25\nMP,C,1,900\nMP,DENS,1,1250\n'+b[stop:]
            # Direct continuation needs an updated in-memory solution DB.
            # Production deliberately uses NOELDB=1 and restores by restart.
            if mode=='continuous':b=b.replace('/CONFIG,NOELDB,1','/CONFIG,NOELDB,0')
            b+='\n/SOLU\nANTYPE,TRANS,NEW\nNROPT,FULL\nTHOPT,FULL\nTRNOPT,FULL\nTINTP,,,,1\nAUTOTS,OFF\nKBC,1\nESTIF,1E-6\nRESCONTROL,DEFINE,ALL,LAST\nOUTRES,ALL,LAST\nFINISH\n'
            exports=[]
            for step in range(1,5):
                removed=0 if step==1 else 1
                b+='/SOLU\n'
                if mode!='continuous' and step>1:b+='ANTYPE,,REST,,,CONTINUE\n'
                state=initial_state(mesh,cfg);state.update(layer=removed,time_s=(step-1)*.1)
                _,commands=prepare_step(mesh,cfg,state)
                if mode=='pending_only' and step>2:
                    commands='\n'.join(line for line in commands.splitlines() if not line.startswith('EKILL,'))+'\n'
                    # The intentionally defective branch must reach SOLVE;
                    # retain measured count but omit the new fail-fast guard.
                    a=commands.index('*IF,V0_LIVE');z=commands.index('*ENDIF',a)+len('*ENDIF')
                    commands=commands[:a]+commands[z:]
                b+=commands
                prefix=f'{stem}_{step}'
                b+=f'ALLSEL,ALL\nESEL,R,LIVE\n*GET,BNLIVE,ELEM,0,COUNT\n*CFOPEN,{prefix}_count,txt\n*VWRITE,BNLIVE\n(F12.0)\n*CFCLOSE\nALLSEL,ALL\nTIME,{step*.1:.16e}\nDELTIM,.1,.1,.1,OFF\nSOLVE\n'
                result_set=f'{step},1' if mode=='continuous' else 'LAST'
                post=f'FINISH\n/POST1\nSET,{result_set}\nALLSEL,ALL\n*CFOPEN,{prefix}_temp,txt\n'
                live_nodes=sorted({n for eid,mat,nn in elements[removed*4:] for n in nn})
                for n in live_nodes:post+=f'*GET,BT,NODE,{n},TEMP\n*VWRITE,{n},BT\n(F8.0,1X,E24.16)\n'
                post+='*CFCLOSE\nFINISH\n'
                if mode=='continuous':exports.append(post)
                else:b+=post
            b+=''.join(exports)
            (RUNTIME/f'{stem}.inp').write_text(b)
            driver+=['/CLEAR,START',f'/FILNAME,{stem}',f'/INPUT,{stem},inp']
    driver+=['/COM,IRIS_RESTART_TOPOLOGY_COMPLETE','/EXIT,NOSAVE']
    (RUNTIME/'benchmark.inp').write_text('\n'.join(driver)+'\n')
    atomic(RUNTIME/'input_manifest.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RUNTIME.glob('*.inp')})

def execute():
    disks()
    for name,sha in json.loads((RUNTIME/'input_manifest.json').read_text()).items():assert hashlib.sha256((RUNTIME/name).read_bytes()).hexdigest()==sha
    exitfile=RUNTIME/'native_exit.json'
    if not exitfile.exists() and not (RUNTIME/'launch_intent.json').exists():
        nonce=str(uuid.uuid4());atomic(RUNTIME/'launch_intent.json',dict(nonce=nonce))
        wrapper=r"""$ErrorActionPreference='Stop';$root='I:\ansystmp\runs\restart_topology_benchmark_v3'
try {
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
$p=Start-Process -FilePath 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j','benchmark','-i','benchmark.inp','-o','benchmark.out') -Wait -PassThru
if($p.ExitCode -ne 0){throw "Native exit $($p.ExitCode)"}
@{ok=$true}|ConvertTo-Json|Set-Content ($root+'\native_exit.json')
} catch {@{ok=$false;error=$_.ToString()}|ConvertTo-Json|Set-Content ($root+'\native_exit.json');exit 1}
"""
        (RUNTIME/'dispatch.ps1').write_text(wrapper,encoding='utf-8-sig')
        atomic(TMP/'active_runs.json',[dict(relative_runtime=str(RUNTIME.relative_to(ROOT)),job='benchmark',windows_root=WINDOWS)])
        command='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+WINDOWS+'\\dispatch.ps1'
        script=r"$ErrorActionPreference='Stop';$r=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'});if($r.Count){throw 'Another solver is running'};"
        script+="$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"+command+"';CurrentDirectory='"+WINDOWS+"'};if($r.ReturnValue -ne 0){throw 'WMI launch failed'};@{nonce='"+nonce+"';ProcessId=$r.ProcessId;ReturnValue=$r.ReturnValue}|ConvertTo-Json|Set-Content '"+WINDOWS+"\\receipt.json'"
        guest(script)
    started=time.monotonic()
    while not exitfile.exists():
        disks()
        if time.monotonic()-started>180:raise RuntimeError('Still pending; inspect the existing native fixture')
        time.sleep(5)
    assert json.loads(exitfile.read_text(encoding='utf-8-sig'))['ok']

def validate():
    log=(RUNTIME/'benchmark.out').read_text(errors='replace')
    assert 'IRIS_RESTART_TOPOLOGY_COMPLETE' in log
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    results=[]
    for case in CASES:
        for step in range(1,5):
            expected=40-(4 if step>1 else 0);values={};counts={}
            for mode in ['continuous','replay','pending_only']:
                stem=f'{case}_{mode}_{step}'
                counts[mode]=int(float((RUNTIME/(stem+'_count.txt')).read_text()))
                values[mode]={int(float(n)):float(t) for n,t in (l.split() for l in (RUNTIME/(stem+'_temp.txt')).read_text().splitlines())}
            assert counts['continuous']==counts['replay']==expected
            assert counts['pending_only']==(40 if step>2 else expected)
            error=max(abs(t-values['continuous'][n]) for n,t in values['replay'].items())
            broken=max(abs(t-values['continuous'][n]) for n,t in values['pending_only'].items())
            assert error<1e-7,(case,step,error)
            if step>2:assert broken>1e-4,(case,step,broken)
            results.append(dict(case=case,step=step,live_elements=counts,max_replay_vs_continuous_K=error,max_broken_vs_continuous_K=broken))
    out=dict(passed=True,qualification='Manufactured transient software regression; not a motor result',results=results,source='https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_bas/Hlp_G_BAS3_12.html',input_hashes=json.loads((RUNTIME/'input_manifest.json').read_text()),log_sha256=hashlib.sha256((RUNTIME/'benchmark.out').read_bytes()).hexdigest())
    atomic(ROOT/'validation/restart_topology_benchmark.json',out);atomic(TMP/'active_runs.json',[])
    print(json.dumps(dict(passed=True,max_replay_vs_continuous_K=max(x['max_replay_vs_continuous_K'] for x in results))))

if __name__=='__main__':prepare();execute();validate()
