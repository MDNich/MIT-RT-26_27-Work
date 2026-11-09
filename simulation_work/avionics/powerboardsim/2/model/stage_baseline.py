"""Stage the immutable October bare-board MAPDL inputs in the revision-2 runtime."""
from pathlib import Path
import argparse,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
MATRIX={'bare_static':('random_vibration/reproduction','static750','ds.dat'),
        'bare_original':('modal_reproduction','default_original','ds.dat'),
        'bare_refined':('modal_reproduction','default_refined','ds.dat'),
        'bare_modal20':('modal_reproduction','modal20','ds.dat'),
        'bare_basis':('random_vibration/reproduction','modal_basis','ds.dat')}
for axis in 'XYZ':
    MATRIX['bare_psd_'+axis]=('random_vibration/reproduction','random_'+axis,'run.dat')
def prepare(archive):
    evidence={}
    for key,(package,sub,filename) in MATRIX.items():
        base=archive/'output/latex'/package
        rel='native/'+sub+'/'+filename
        src=(base/rel).read_bytes()
        expected=json.loads((base/'MANIFEST.json').read_text())['files'][rel]['sha256']
        assert hashlib.sha256(src).hexdigest()==expected
        raw=re.sub(rb"(?im)^(_wb_(?:ProjectScratch|SolverFiles|userfiles)_dir\(1\)\s*=\s*)'[^'\r\n]*'",lambda m:m[1]+b"'.\\'",src)
        raw=re.sub(rb'(?im)^! File used for geometry attach:[^\r\n]+',b'! Geometry embedded in this Workbench input.',raw)
        folder=ROOT/'.runtime/inputs'/key
        folder.mkdir(exist_ok=True,parents=True)
        target=folder/'model.inp'
        if target.exists() and target.read_bytes()!=raw:raise RuntimeError(f'Changed sealed input {key}')
        target.write_bytes(raw)
        evidence[key]={'source_package':package,'source_path':rel,'source_sha256':expected,'staged_sha256':hashlib.sha256(raw).hexdigest()}
    (ROOT/'validation/bare_inputs.json').write_text(json.dumps(evidence,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);prepare(p.parse_args().archive)
