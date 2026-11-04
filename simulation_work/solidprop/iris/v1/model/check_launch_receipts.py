"""Manufactured lost-reply checks; no guest process is launched by this test."""
import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
import launch_case
from ops import ROOT,atomic,disks


def main():
    disks();results=[]
    for mode in ['matching_receipt','stale_receipt','missing_receipt']:
        with tempfile.TemporaryDirectory(prefix='iris_launch_receipt_') as td:
            base=Path(td).resolve();run=base/'ansystmp/runs/fixture';run.mkdir(parents=True)
            (run/'config.json').write_text(json.dumps(dict(windows_root=r'I:\fixture')))
            launch_case.ROOT=base;launch_case.TMP=base/'ansystmp';launch_case.disks=lambda:dict(allowed=True)
            calls=[]
            def lost_reply(script):
                calls.append(script)
                nonce=re.search(r"nonce='([^']+)'",script).group(1)
                if mode!='missing_receipt':
                    atomic(run/'guest_launch_receipt_run.json',dict(ProcessId=123,ReturnValue=0,nonce=nonce if mode=='matching_receipt' else 'old-other-request'))
                raise RuntimeError('Manufactured lost guest reply')
            launch_case.guest=lost_reply
            sys.argv=['launch_case.py','fixture','run'];blocked=False
            try:
                with contextlib.redirect_stdout(io.StringIO()):launch_case.main()
            except RuntimeError:blocked=True
            accepted=(run/'host_launch_run.json').exists()
            assert len(calls)==1
            assert accepted==(mode=='matching_receipt') and blocked==(mode!='matching_receipt')
            results.append(dict(scenario=mode,guest_mutation_requests=len(calls),receipt_accepted=accepted,stopped_for_inspection=blocked))
    atomic(ROOT/'validation/launch_receipt_controls.json',dict(passed=True,qualification='Manufactured communication-fault fixture; zero real guest launches',results=results))
    print('Matching receipt recovered; missing/stale proof stopped; no mutation retried.')


if __name__=='__main__':main()
