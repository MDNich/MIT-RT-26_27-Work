"""Verify native substep metadata on the preserved, withdrawn cooling chain."""
import hashlib,json,subprocess
from ops import ROOT,TMP,atomic,disks,guest
from coupler import validate_native_step_identity

def main():
    disks();source=TMP/'runs/sustainer_al_pulse7_n80_dt0125_restartfix';run=TMP/'runs/substep_metadata_probe'
    run.mkdir(exist_ok=True)
    if not (run/'probe.out').exists():
        inp=['FINISH','/POST1',r'FILE,C:\IrisStudy\runs\sustainer_al_pulse7_n80_dt0125_restartfix\file,rth']
        for index in [560,561]:
            inp += [f'SET,{index},LAST','*GET,LS,ACTIVE,0,SET,LSTP','*GET,SS,ACTIVE,0,SET,SBST','*GET,TT,ACTIVE,0,SET,TIME',f'*CFOPEN,step{index},txt','*VWRITE,LS,SS,TT','(2(F12.0,1X),E24.16)','*CFCLOSE']
        inp+=['FINISH','/COM,IRIS_SUBSTEP_PROBE_COMPLETE','/EXIT,NOSAVE']
        (run/'probe.inp').write_text('\n'.join(inp)+'\n')
        script=r"$ErrorActionPreference='Stop';$p=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'});if($p.Count){throw 'Another native solver is active'};$env:ANSYSLMD_LICENSE_FILE='1055@localhost';$r='I:\ansystmp\runs\substep_metadata_probe';$p=Start-Process -FilePath 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -WorkingDirectory $r -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j','probe','-i','probe.inp','-o','probe.out') -Wait -PassThru;if($p.ExitCode -ne 0){throw 'Native probe failed'}"
        atomic(TMP/'active_runs.json',[dict(relative_runtime=str(run.relative_to(ROOT)),job='probe',windows_root=r'I:\ansystmp\runs\substep_metadata_probe')])
        guest(script)
    log=(run/'probe.out').read_text(errors='replace');assert 'IRIS_SUBSTEP_PROBE_COMPLETE' in log
    records=[]
    for index,target in [(560,7.),(561,7.25)]:
        values=list(map(float,(run/f'step{index}.txt').read_text().split()));pending=dict(index=index,target=target)
        try:validate_native_step_identity(values,pending);accepted=True
        except ValueError:accepted=False
        assert accepted==(index==560)
        records.append(dict(index=index,time_s=values[2],native_substep=values[1],gate_accepts=accepted))
    # Audit the full native logs for every already reported macro-step chain.
    import re
    older=[]
    for r in sorted((TMP/'runs').iterdir()):
        if not (ROOT/'validation'/f'accepted_{r.name}.json').exists():continue
        entries=[]
        for p in r.glob('solve_*.out'):
            entries += [(int(a),int(b)) for a,b in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',p.read_text(errors='replace'))]
        assert entries and all(ss==1 for ls,ss in entries),(r.name,entries)
        older.append(dict(runtime=r.name,completed_native_substeps=len(entries),max_substep=max(ss for ls,ss in entries)))
    result=dict(passed=True,records=records,previously_published_native_chains=older,qualification='Native postprocessing probe and retrospective log audit. Withdrawn multi-substep cooling is rejected; no rejected thermal state is accepted.',input_sha256=hashlib.sha256((run/'probe.inp').read_bytes()).hexdigest(),log_sha256=hashlib.sha256((run/'probe.out').read_bytes()).hexdigest())
    atomic(ROOT/'validation/substep_metadata_gate.json',result);atomic(TMP/'active_runs.json',[]);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
