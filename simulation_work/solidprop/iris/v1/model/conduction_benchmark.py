"""Native steady cylindrical conduction check; no pyrolysis or ablation.

Uses the same structured mesh, surface face numbers and CF material frames as
production. Compares all radial temperatures against the analytical two-layer
cylinder with convection, deliberately excluding radiation and reactions.
"""
import hashlib
import json
import math
import re
from pathlib import Path
from prepare_model import create_mesh, write_model
from ops import ROOT, TMP, atomic, disks, guest


def main():
    disks()
    runtime=TMP/'runs/conduction_benchmark'
    runtime.mkdir(exist_ok=True)
    if (runtime/'benchmark.out').exists():
        raise RuntimeError('Preserve existing benchmark; inspect rather than overwrite')
    expectations=[]
    driver=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        cfg=json.loads((ROOT/'configs'/f'{case}.json').read_text())
        mesh,nodes,elements=create_mesh(cfg)
        work=runtime/case;work.mkdir(exist_ok=True)
        write_model(cfg,nodes,elements,work)
        body=(work/'model_base.inp').read_text()
        start=body.index('! Phenolic UserMatTh:')
        stop=body.index('MP,KXX,2,',start)
        body=body[:start]+'MP,KXX,1,.25\nMP,C,1,900\nMP,DENS,1,1250\n'+body[stop:]
        body+='\n/SOLU\nANTYPE,STATIC\n'
        for face in mesh['rows'][0]:
            body+=f'SFE,{face["element"]},5,CONV,0,1000\nSFE,{face["element"]},5,CONV,2,2230.85\n'
        for face in mesh['outer']:
            body+=f'SFE,{face["element"]},3,CONV,0,8\nSFE,{face["element"]},3,CONV,2,22\n'
        body+='ALLSEL,ALL\nSOLVE\nFINISH\n/POST1\nSET,LAST\n'
        body+=f'*CFOPEN,{case}_temperatures,txt\n'
        for nid,x,y,z in nodes:
            body+=f'*GET,BT,NODE,{nid},TEMP\n*VWRITE,{nid},BT\n(F8.0,1X,E24.16)\n'
        body+='*CFCLOSE\nFINISH\n'
        (runtime/f'{case}.inp').write_text(body)
        driver+=['/CLEAR,START',f'/INPUT,{case},inp']
        g=cfg['geometry'];ri=g['inner_radius_m'];rp=g['phenolic_outer_radius_m'];ro=g['outer_radius_m']
        kc=cfg['cf_radial_k'] if cfg['case_material']=='cf' else 167.
        resistance=1/(1000*ri)+math.log(rp/ri)/.25+math.log(ro/rp)/kc+1/(8*ro)
        q=(2230.85-22)/resistance
        def exact(r):
            R=math.log(min(r,rp)/ri)/.25
            if r>rp:R+=math.log(r/rp)/kc
            return 2230.85-q*(1/(1000*ri)+R)
        expectations.append(dict(case=case,radial_conductivity_W_m_K=kc,heat_W_per_radian_m=q,
                                 nodes={str(n):exact(math.hypot(x,z)) for n,x,y,z in nodes}))
    driver+=['/COM,IRIS_CONDUCTION_BENCHMARK_COMPLETE','/EXIT,NOSAVE']
    (runtime/'benchmark.inp').write_text('\n'.join(driver)+'\n')
    atomic(TMP/'active_runs.json',[dict(relative_runtime=str(runtime.relative_to(ROOT)),job='benchmark')])
    script=r"""$ErrorActionPreference='Stop';$r=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'});if($r.Count){throw 'Another solver is running'}
$root='I:\ansystmp\runs\conduction_benchmark'
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
$p=Start-Process -FilePath 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j','benchmark','-i','benchmark.inp','-o','benchmark.out') -Wait -PassThru
if($p.ExitCode -ne 0){throw "Benchmark exit $($p.ExitCode)"};$p.ExitCode
"""
    print(guest(script,timeout=45))
    log=(runtime/'benchmark.out').read_text(errors='replace')
    assert 'IRIS_CONDUCTION_BENCHMARK_COMPLETE' in log
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    results=[]
    for expected in expectations:
        actual={str(int(float(a))):float(b) for a,b in (line.split() for line in (runtime/(expected['case']+'_temperatures.txt')).read_text().splitlines())}
        assert actual.keys()==expected['nodes'].keys()
        error=max(abs(actual[n]-T) for n,T in expected['nodes'].items())
        assert error<.1,(expected['case'],error)
        results.append(dict(case=expected['case'],max_temperature_error_K=error,
                            radial_conductivity_W_m_K=expected['radial_conductivity_W_m_K'],
                            analytical_heat_W_per_radian_m=expected['heat_W_per_radian_m'],
                            max_temperature_C=max(actual.values()),min_temperature_C=min(actual.values())))
    output=dict(method='Native steady SOLID278 versus analytical two-layer cylindrical conduction',
                acceptance_K=.1,passed=True,results=results,
                log_sha256=hashlib.sha256((runtime/'benchmark.out').read_bytes()).hexdigest())
    atomic(ROOT/'validation/conduction_benchmark.json',output)
    atomic(TMP/'active_runs.json',[])
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
