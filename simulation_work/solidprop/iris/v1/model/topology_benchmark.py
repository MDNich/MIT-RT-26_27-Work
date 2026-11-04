"""Manufactured native verification of moving loads and last-row topology.

Constant properties, 100 C gas, no reactions: all temperatures have an exact
steady-cylinder reference. Four stages per case: no removal, first row gone,
only the final phenolic row remaining, and no phenolic remaining. These are
software verification states, not an inferred physical recession history.
"""
import argparse
import hashlib
import json
import math
import re
import time
from pathlib import Path
from prepare_model import create_mesh,write_model
from ops import ROOT,TMP,atomic,disks,guest

RUNTIME=TMP/'runs/topology_benchmark'
WINDOWS=r'I:\ansystmp\runs\topology_benchmark'


def prepare():
    disks();RUNTIME.mkdir(exist_ok=True)
    if (RUNTIME/'topology.inp').exists():
        return json.loads((RUNTIME/'expectations.json').read_text())
    driver=[];checks=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        cfg=json.loads((ROOT/'configs'/f'{case}.json').read_text())
        mesh,nodes,elements=create_mesh(cfg);g=cfg['geometry'];nph=g['phenolic_radial_rows'];nface=g['faces_per_row']
        work=RUNTIME/case;work.mkdir(exist_ok=True);write_model(cfg,nodes,elements,work)
        body=(work/'model_base.inp').read_text();start=body.index('! Phenolic UserMatTh:');stop=body.index('MP,KXX,2,',start)
        body=body[:start]+'MP,KXX,1,.25\nMP,C,1,900\nMP,DENS,1,1250\n'+body[stop:]
        body+='\n/SOLU\nANTYPE,STATIC\nNROPT,FULL\nESTIF,1E-6\n'
        last_removed=0
        for stage,removed in enumerate([0,1,nph-1,nph]):
            # These are the same delete-old-load/reapply-new-face operations
            # used by the production controller. No temperature-based kill law.
            body+='ALLSEL,ALL\nFDELE,ALL,HEAT\nSFEDELE,ALL,ALL,CONV\n'
            for row in mesh['rows'][last_removed:removed]:
                for f in row:body+=f'EKILL,{f["element"]}\n'
            last_removed=removed
            if removed<nph:hot=mesh['rows'][removed]
            else:
                hot=[]
                for eid,mat,nn in elements[nph*nface:nph*nface+nface]:
                    hot.append(dict(element=eid,face=5,nodes=[nn[i] for i in [3,0,4,7]]))
            for f in hot:body+=f'SFE,{f["element"]},5,CONV,0,1000\nSFE,{f["element"]},5,CONV,2,100\n'
            for f in mesh['outer']:body+=f'SFE,{f["element"]},3,CONV,0,8\nSFE,{f["element"]},3,CONV,2,22\n'
            prefix=f'{case}_removed{removed}'
            body+=f'ALLSEL,ALL\nESEL,R,LIVE\n*GET,BNLIVE,ELEM,0,COUNT\n*CFOPEN,{prefix}_counts,txt\n*VWRITE,BNLIVE\n(F12.0)\n*CFCLOSE\n'
            body+=f'ALLSEL,ALL\nTIME,{stage+1}\nSOLVE\nFINISH\n/POST1\nSET,LAST\nALLSEL,ALL\n*CFOPEN,{prefix}_temperatures,txt\n'
            ri=g['inner_radius_m']+removed*g['phenolic_thickness_m']/nph;rp=g['phenolic_outer_radius_m'];ro=g['outer_radius_m']
            live_nodes=[n for n in nodes if math.hypot(n[1],n[3])>=ri-1e-10]
            for nid,x,y,z in live_nodes:body+=f'*GET,BT,NODE,{nid},TEMP\n*VWRITE,{nid},BT\n(F8.0,1X,E24.16)\n'
            body+='*CFCLOSE\nETABLE,ERAS\nETABLE,HOT,NMISC,29\nETABLE,OUTER,NMISC,17\n'
            body+=f'*CFOPEN,{prefix}_heat,txt\n'
            for f in hot:
                body+=f'*GET,BQ,ELEM,{f["element"]},ETAB,HOT\n*VWRITE,1,BQ\n(F8.0,1X,E24.16)\n'
            for f in mesh['outer']:
                body+=f'*GET,BQ,ELEM,{f["element"]},ETAB,OUTER\n*VWRITE,2,BQ\n(F8.0,1X,E24.16)\n'
            body+='*CFCLOSE\nFINISH\n/SOLU\n'
            kc=cfg['cf_radial_k'] if cfg['case_material']=='cf' else 167.
            resist=1/(1000*ri)+math.log(rp/ri)/.25+math.log(ro/rp)/kc+1/(8*ro)
            q=78/resist
            def exact(radius):
                R=math.log(min(radius,rp)/ri)/.25
                if radius>rp:R+=math.log(radius/rp)/kc
                return 100-q*(1/(1000*ri)+R)
            checks.append(dict(case=case,removed_rows=removed,prefix=prefix,
                               expected_live_elements=len(elements)-removed*nface,
                               expected_power_W=q*math.radians(g['angle_deg'])*g['length_m'],
                               expected_temperatures={str(n):exact(math.hypot(x,z)) for n,x,y,z in live_nodes}))
        (RUNTIME/f'{case}.inp').write_text(body+'FINISH\n')
        driver+=['/CLEAR,START',f'/INPUT,{case},inp']
    driver+=['/COM,IRIS_TOPOLOGY_BENCHMARK_COMPLETE','/EXIT,NOSAVE']
    (RUNTIME/'topology.inp').write_text('\n'.join(driver)+'\n');atomic(RUNTIME/'expectations.json',checks)
    atomic(RUNTIME/'input_manifest.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RUNTIME.glob('*.inp')})
    return checks


def execute():
    disks()
    for name,sha in json.loads((RUNTIME/'input_manifest.json').read_text()).items():
        assert hashlib.sha256((RUNTIME/name).read_bytes()).hexdigest()==sha
    exitfile=RUNTIME/'native_exit.json'
    if not exitfile.exists() and not (RUNTIME/'launch.json').exists():
        if (RUNTIME/'topology.out').exists():raise RuntimeError('Unexplained prior native output; preserve and inspect')
        wrapper=r"""$ErrorActionPreference='Stop';$root='I:\ansystmp\runs\topology_benchmark'
try {
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
$p=Start-Process -FilePath 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j','topology','-i','topology.inp','-o','topology.out') -Wait -PassThru
if($p.ExitCode -ne 0){throw "Native exit $($p.ExitCode)"}
@{ok=$true}|ConvertTo-Json|Set-Content ($root+'\native_exit.json')
} catch {@{ok=$false;error=$_.ToString()}|ConvertTo-Json|Set-Content ($root+'\native_exit.json');exit 1}
"""
        (RUNTIME/'dispatch.ps1').write_text(wrapper,encoding='utf-8-sig')
        atomic(TMP/'active_runs.json',[dict(relative_runtime=str(RUNTIME.relative_to(ROOT)),job='topology',windows_root=WINDOWS)])
        script=r"$ErrorActionPreference='Stop';$r=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'});if($r.Count){throw 'Another solver is running'};"
        command='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+WINDOWS+'\\dispatch.ps1'
        script+="$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"+command+"';CurrentDirectory='"+WINDOWS+"'};if($r.ReturnValue -ne 0){throw 'WMI launch failed'};$r|Select-Object ProcessId,ReturnValue|ConvertTo-Json"
        atomic(RUNTIME/'launch.json',dict(result=guest(script)))
    started=time.monotonic()
    while not exitfile.exists():
        disks()
        if time.monotonic()-started>300:raise RuntimeError('Benchmark has not exited; inspect existing process, do not duplicate')
        time.sleep(5)
    status=json.loads(exitfile.read_text(encoding='utf-8-sig'));assert status['ok'],status


def validate(checks):
    log=(RUNTIME/'topology.out').read_text(errors='replace')
    assert 'IRIS_TOPOLOGY_BENCHMARK_COMPLETE' in log
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    results=[]
    for c in checks:
        alive=int(float((RUNTIME/(c['prefix']+'_counts.txt')).read_text().strip()))
        assert alive==c['expected_live_elements'],(c['prefix'],alive,c['expected_live_elements'])
        rows=[line.split() for line in (RUNTIME/(c['prefix']+'_temperatures.txt')).read_text().splitlines()]
        values={str(int(float(n))):float(t) for n,t in rows}
        assert values.keys()==c['expected_temperatures'].keys()
        error=max(abs(values[n]-t) for n,t in c['expected_temperatures'].items())
        heat=[(int(float(a)),float(b)) for a,b in (line.split() for line in (RUNTIME/(c['prefix']+'_heat.txt')).read_text().splitlines())]
        hot=-sum(q for side,q in heat if side==1);outer=sum(q for side,q in heat if side==2)
        power_error=abs(hot-c['expected_power_W'])/c['expected_power_W'];balance=abs(hot-outer)/max(abs(hot),1e-9)
        assert error<.02 and power_error<.001 and balance<1e-6,(c['prefix'],error,power_error,balance)
        results.append(dict(case=c['case'],removed_rows=c['removed_rows'],max_temperature_error_K=error,
                            live_elements=alive,
                            hot_power_W=hot,outer_power_W=outer,power_relative_error=power_error,relative_energy_balance=balance))
    out=dict(passed=True,qualification='Manufactured constant-property native verification; not a physical recession result',
             temperature_tolerance_K=.02,power_relative_tolerance=.001,results=results,
             warning_count=int(re.findall(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',log)[-1]),
             warning_explanation='Static nonlinear fixture chooses its initial load factor; dead-element ETABLE entries are zero and unused. Live face values, counts and analytical balance are checked separately.',
             native_input_hashes=json.loads((RUNTIME/'input_manifest.json').read_text()),
             log_sha256=hashlib.sha256((RUNTIME/'topology.out').read_bytes()).hexdigest())
    atomic(ROOT/'validation/topology_benchmark.json',out)
    active=json.loads((TMP/'active_runs.json').read_text())
    if active and all(a.get('job')=='topology' for a in active):
        atomic(TMP/'active_runs.json',[])
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    checks=prepare()
    if not a.prepare_only:execute();validate(checks)
    else:print('Prepared sixteen native topology-verification states; no solver launched')
