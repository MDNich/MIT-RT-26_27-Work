"""Reconcile whole-board candidate geometry with the raised native baseline before any flush installation."""
import json
import re
import sys
from audit_local import ROOT,read,table
from stage_local_jobs import digest,seal


def stage():
    src=ROOT/'.runtime/board_install_v1/nylon/pre.inp'
    dest=ROOT/'.runtime/board_initial_v1';dest.mkdir(exist_ok=True)
    data=src.read_bytes()
    assert digest(data)==read(ROOT/'validation/board_install_candidates.json')['nylon']['preflight_sha256']
    seal(dest/'pre.inp',data)


def audit():
    d=ROOT/'.runtime/board_initial_v1'
    assert int((d/'exit.txt').read_text(encoding='utf-16').strip())==0
    log=(d/'pre.out').read_text(errors='replace')
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log) and 'BOARD_APPROACH_INITIAL_CHECK_DONE' in log
    assert not re.search(r'(?:CERIG or CE|CE or CERIG|constraint equation|rigid region|dependent node).{0,150}(?:skipped|ignored|does not exist)',log,re.I)
    inv=table(d/'board_inventory.csv')
    counts={int(r['type']):int(r['elements']) for r in inv}
    assert counts=={850:16108,851:4,852:9466,853:8038,854:4,855:0,856:8},counts
    block=re.split(r'contact pair identified by real constant set\s+853\b',log,flags=re.I)[-1]
    g=float(re.search(r'Min\.\s+Initial gap\s+([\d.E+-]+)',block,re.I)[1])*1e3
    search=float(re.search(r'User defined pinball region PINB\s+([\d.E+-]+)',block,re.I)[1])*1e3
    assert abs(search-.6)<1e-6 and not re.search(r'Max\.\s+Initial penetration',block,re.I)
    # Millimetres; initial case outer geometry is identical to raised. Only shank grip and seat actuator differ.
    from contact_search_check import parse
    ref=next(r for r in parse('stand3_nylon_static')['checks'] if r['request_mm']==.6)
    assert abs(g-ref['min_gap_mm'])<1e-4
    data=dict(scope='Native initial geometry only. Flexible-board actuator control and nonlinear seating must be accepted separately.',
              inventory=counts,initial_gap_mm=g,search_mm=search,raised_control_gap_mm=ref['min_gap_mm'],
              input_sha256=digest((d/'pre.inp').read_bytes()),listing_sha256=digest((d/'pre.out').read_bytes()))
    (ROOT/'validation/board_initial_approach.json').write_text(json.dumps(data,indent=2)+'\n')

if __name__=='__main__':{'stage':stage,'audit':audit}[sys.argv[1]]()
