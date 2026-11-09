"""Stage exact native inputs for the historical edge-pull and continuous-damage controls."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stage(archive):
    package=archive/'output/battery_side_pull_source'
    inventory=json.loads((package/'SHA256.json').read_text())
    tear=archive/'outputs/battery_tearing_20261005/runtime'
    cases=[('lateral',p) for p in sorted((package/'cases').iterdir()) if p.is_dir()]
    cases.extend(('damage',p) for p in sorted(tear.iterdir()) if p.is_dir() and (p.name in ('continuous_proof','cont_nominal','cont_fine','cont_negative','cont_force5em5') or p.name.startswith(('coupon_','cont_e'))))
    manifest={}
    for group,src in cases:
        key=group+'_'+src.name
        names=['model.inp','config.json','preflight.dat','run.dat']
        post='post_corrected.dat' if group=='lateral' else 'post.dat'
        names.extend(n for n in ['mesh.json',post] if (src/n).is_file())
        dest=ROOT/'.runtime/local_inputs'/key;dest.mkdir(exist_ok=True,parents=True)
        sources=json.loads((src/'input_sha256.json').read_text()) if group=='damage' else {}
        files={}
        for name in names:
            source=src/name;expected=inventory['cases/'+src.name+'/'+name] if group=='lateral' else sources.get(name)
            if not expected or sha(source)!=expected:raise ValueError(f'Archive identity mismatch {key}/{name}')
            target=dest/name
            if not target.exists():shutil.copyfile(source,target)
            assert sha(target)==expected
            files[name]=expected
        manifest[key]=dict(source_path=str(src.relative_to(archive)),files=files)
    (ROOT/'validation/local_inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(len(manifest),'staged local references')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);stage(p.parse_args().archive)
