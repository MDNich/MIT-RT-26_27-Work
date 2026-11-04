"""Exercise storage faults without touching live solver state or actual disks."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ops


def main():
    ops.disks()
    checks=[]
    with tempfile.TemporaryDirectory(dir=ops.TMP) as temp:
        fake=Path(temp)
        with patch.object(ops,'TMP',fake):
            with patch.object(ops.shutil,'disk_usage',return_value=SimpleNamespace(free=ops.MAC_FLOOR-1)):
                try:ops.host_check()
                except ops.StorageLimitError:checks.append('Mac below 400 GB stops')
                else:raise AssertionError('Mac floor not enforced')
            with patch.object(ops.shutil,'disk_usage',return_value=SimpleNamespace(free=ops.MAC_FLOOR)):
                assert ops.host_check()==ops.MAC_FLOOR
                checks.append('Exact Mac threshold allowed')
            (fake/'STOP_WORK.json').write_text('{}')
            try:ops.host_check()
            except RuntimeError:checks.append('Latched stop blocks work')
            else:raise AssertionError('Latched stop ignored')
            (fake/'STOP_WORK.json').unlink()
            with patch.object(ops,'guest',return_value=str(ops.WINDOWS_FLOOR-1)):
                try:ops.disks()
                except ops.StorageLimitError:checks.append('Windows below 10 GB stops')
                else:raise AssertionError('Windows floor not enforced')
            with patch.object(ops,'guest',side_effect=[RuntimeError('communication fault'),str(20_000_000_000)]) as get:
                with patch.object(ops.time,'sleep'):
                    assert ops.disks()['windows_free_bytes']==20_000_000_000
                assert get.call_count==2
                assert not (fake/'STOP_WORK.json').exists()
                checks.append('Read-only communication retry does not invent a storage crossing')
            run=fake/'runs/test';run.mkdir(parents=True)
            (run/'preflight_123.out').write_text('test')
            ops.atomic(fake/'active_runs.json',[dict(relative_runtime=str(run.relative_to(ops.ROOT)),job='preflight')])
            ops.stop_runs('manufactured test only')
            assert (run/'preflight_123.abt').read_text()=='nonlinear\n'
            assert (run/'PAUSE_REQUESTED').exists() and (fake/'STOP_WORK.json').exists()
            checks.append('Threshold crossing latches and requests correct native job stop')
    result=dict(passed=True,checks=checks,scope='Manufactured faults in temporary fixtures; actual disks unchanged')
    ops.atomic(ops.ROOT/'validation/storage_controls.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
