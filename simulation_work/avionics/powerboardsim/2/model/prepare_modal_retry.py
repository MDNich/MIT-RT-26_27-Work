"""Prepare an independently sealed retry when the original Lanczos solve returns too few modes."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def prepare(source, campaign):
    run = ROOT/'.runtime/receipts'/campaign/source
    if not (run/'audit_failed.txt').is_file():
        raise ValueError('The original completed but unaudited result is required')
    listing = (run/'solve.out').read_text(errors='replace')
    counts = re.search(r'Fewer modes than the requested number of modes \(\s*(\d+)\s*\).*?contains only\s+(\d+) modes',listing,re.S)
    if not counts:
        raise ValueError('The original solve has a different failure')
    name = source+'_sturm'
    path = ROOT/'.runtime/inputs'/source/'model.inp'
    deck = path.read_bytes()
    retry, number = re.subn(rb'(?im)^(modopt,lanb,20,1\.,10000\.)(\r?\n)',rb'\1\2lanboption,on,,alt1\2',deck)
    if number != 1:
        raise ValueError('Unexpected original eigenanalysis settings')
    target = ROOT/'.runtime/inputs'/name/'model.inp'
    target.parent.mkdir(exist_ok=True)
    if target.exists() and target.read_bytes()!=retry:
        raise ValueError('Existing sealed retry has a different input')
    target.write_bytes(retry)
    audit = dict(source=source, campaign=campaign, retry=name, requested_modes=int(counts[1]),
                 produced_modes=int(counts[2]), first_listing_sha256=hashlib.sha256((run/'solve.out').read_bytes()).hexdigest(),
                 original_input_sha256=hashlib.sha256(deck).hexdigest(), retry_input_sha256=hashlib.sha256(retry).hexdigest(),
                 modification='LANBOPTION,ON,,ALT1 after the original MODOPT. Same geometry, constraints and 1 to 10000 Hz search.',
                 solver_reference='https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_cmd/Hlp_C_LANBOPTION.html')
    (ROOT/'validation'/f'{name}_input.json').write_text(json.dumps(audit,indent=2)+'\n')

if __name__ == '__main__':
    import sys
    prepare(*sys.argv[1:])
