"""Isolate the installed case contact search before a structural solve. Never alter sealed decks."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'.runtime'


def prepare(name):
    assert name in ('stand3_nylon_static','flush_nylon_static','stand3_nylon_lateral_friction_locked','flush_nylon_lateral_friction_locked')
    folder = RUNTIME/'contact_checks'/name
    folder.mkdir(exist_ok=True,parents=True)
    source = (RUNTIME/'inputs'/name/'model.inp').read_bytes()
    local = '_lateral_' in name
    cut = source.lower().index(b'save,model,db' if local else b'/gst,on,on')
    pairs = (861,862) if local else (853,)
    scale = 1 if local else .001
    commands = ['FINISH','/PREP7','ALLSEL,ALL','/GOPR']
    for window in (0,0.6,1.,2.):
        if window:
            commands += [f'RMODIF,{real},6,{-window*scale:.6g}' for real in pairs]
        commands += ['FINISH','/SOLU','ANTYPE,STATIC','NLGEOM,ON',f'/COM,BEGIN_WINDOW_MM_{window:g}',
                     f'CNCHECK,DETAIL,{pairs[0]},{pairs[-1]}',f'/COM,END_WINDOW_MM_{window:g}','FINISH','/PREP7']
    commands += ['FINISH','/EXIT,NOSAVE','']
    inp = source[:cut]+('\n'+'\n'.join(commands)).encode()
    sink = folder/'pre.inp'
    if sink.exists() and sink.read_bytes()!=inp:
        raise ValueError('Preflight input changed')
    sink.write_bytes(inp)
    print(name, hashlib.sha256(inp).hexdigest())


def parse(name):
    folder = RUNTIME/'contact_checks'/name
    listing = (folder/'pre.out').read_bytes()
    s = listing.decode(errors='replace')
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',s)
    scale = 1 if '_lateral_' in name else 1000
    rows = []
    for match in re.finditer(r'^\s*BEGIN_WINDOW_MM_([.0-9]+)\s*$(.*?)^\s*END_WINDOW_MM_\1\s*$',s,re.S|re.M):
        bodies = re.split(r'(?=Contact pair identified by real constant set)',match[2],flags=re.I)
        for block in bodies[1:]:
            rid = int(re.search(r'constant set\s*(\d+)',block,re.I)[1])
            def number(pattern):
                m = re.search(pattern+r'\s+([+\d.E-]+)',block,re.I)
                return None if not m else float(m[1])*scale
            rows.append(dict(request_mm=float(match[1]) or None,real=rid,actual_pinball_mm=number(r'(?:resulting pinball region|User defined pinball region PINB)'),
                             min_gap_mm=number(r'Min\.\s+Initial gap'),max_penetration_mm=number(r'Max\.\s+Initial penetration')))
    assert len(rows)==(8 if '_lateral_' in name else 4),rows
    return dict(case=name,input_sha256=hashlib.sha256((folder/'pre.inp').read_bytes()).hexdigest(),
                listing_sha256=hashlib.sha256(listing).hexdigest(),checks=rows)

if __name__=='__main__':
    for name in sys.argv[2:]:
        if sys.argv[1]=='prepare':prepare(name)
        elif sys.argv[1]=='parse':print(json.dumps(parse(name),indent=2))
        else:raise ValueError(sys.argv[1])
