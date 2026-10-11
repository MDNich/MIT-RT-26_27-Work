"""Reject resets using both native log and independent result-set metadata."""
import re,json,hashlib
from pathlib import Path
import numpy as np

def audit(d):
    d=Path(d);cfg=json.loads((d/'config.json').read_text())
    assert not (d/'REJECTED_LOAD_HISTORY.json').exists()
    text=(d/'run.out').read_text(errors='replace')
    pairs=[tuple(map(int,x)) for x in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',text)]
    assert pairs and pairs[0][0]==1
    for a,b in zip(pairs,pairs[1:]):
        assert b[0]>=a[0] and (b[0]>a[0] or b[1]>a[1]),f'Load/substep reset: {a} -> {b}'
        assert b[0]<=a[0]+1,f'Skipped load step: {a} -> {b}'
    inv=np.atleast_1d(np.genfromtxt(d/'set_inventory.csv',delimiter=',',names=True))
    for f in inv.dtype.names:assert np.all(np.isfinite(inv[f]))
    assert np.all(np.diff(inv['time'])>0),'Result time reset'
    assert np.all(np.diff(inv['loadstep'])>=0),'Result load step reset'
    assert np.all(inv['substep']!=999999)
    assert set(inv['loadstep'].astype(int))==set(range(1,int(max(inv['loadstep']))+1))
    assert {(int(r['loadstep']),int(r['substep'])) for r in inv}.issubset(set(pairs))
    pre=inv[np.isclose(inv['time'],1,atol=1e-7)]
    lock=inv[np.isclose(inv['time'],2,atol=1e-7)]
    assert len(pre)==len(lock)==1,'Need complete preload and locking states'
    assert pre['loadstep'][0]==1 and lock['loadstep'][0]==2
    # Applied-force DOFs have zero RF in preload; validate force via prescribed750N
    # and the displacement-locked reaction in the immediately following step.
    for f in ['clamp1_N','clamp2_N']:
        assert abs(abs(lock[f][0])-750)<.1,('Locked clamp did not retain750N',f,lock[f][0])
    pulls=inv[inv['loadstep']>=3];assert len(pulls)>0
    assert np.max(abs(pulls['ux_mm']-cfg['sign']*(pulls['time']-2)))<1e-6,'Displacement/time path mismatch'
    assert np.all(np.diff(pulls['damage'])>=-1e-4),'Global damage maximum decreases'
    progress=np.atleast_1d(np.genfromtxt(d/'solve_progress.csv',delimiter=',',names=True))
    assert np.array_equal(progress['stage'],progress['loadstep'])
    assert np.all(np.diff(progress['loadstep'])==1)
    assert np.all(np.diff(progress['iterations'])>0)
    result=dict(native_completed_substeps=len(pairs),retained_converged_sets=len(inv),max_loadstep=int(max(inv['loadstep'])),last_time=float(inv['time'][-1]),locked_clamp_forces_N=[float(lock[f][0]) for f in ['clamp1_N','clamp2_N']],post_history_sha256=hashlib.sha256((d/'set_inventory.csv').read_bytes()).hexdigest(),run_out_sha256=hashlib.sha256((d/'run.out').read_bytes()).hexdigest())
    tmp=d/'LOAD_HISTORY_VERIFIED.json.tmp';tmp.write_text(json.dumps(result,indent=2)+'\n');tmp.replace(d/'LOAD_HISTORY_VERIFIED.json')
    return result
if __name__=='__main__':
    import sys
    print(json.dumps(audit(Path(__file__).resolve().parent.parent/'runtime'/sys.argv[1]),indent=2))
