"""Seal isolated side-pull runs and native readbacks for eligible bare and cased fixtures."""
import hashlib
import json
from pathlib import Path

from local_equilibrium import movement_deck

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def seal(path, data):
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f'Staged input changed: {path}')
    if not path.exists():
        path.write_bytes(data)
    return digest(data)


def stage():
    sources = json.loads((ROOT/'validation/local_inputs.json').read_text())
    cased = json.loads((ROOT/'validation/local_cased_candidates.json').read_text())
    cases = {f'bare_{key}': key for key in sources}
    cases.update({key: row['source'] for key,row in cased.items()})
    manifest = {}
    for name, source in cases.items():
        folder = ROOT/'.runtime/local_inputs'/source
        config = json.loads((folder/'config.json').read_text())
        is_bare = name.startswith('bare_')
        coupon = source.startswith('damage_coupon_')
        is_damage = source.startswith('damage_')
        job = 'tear' if is_damage else 'pull'
        run_path = (folder if is_bare else ROOT/'.runtime/local_cased'/name)/'run.dat'
        deck = run_path.read_bytes()
        expected = sources[source]['files']['run.dat'] if is_bare else cased[name]['run_sha256']
        if digest(deck) != expected:
            raise ValueError(f'Source input hash failed: {name}')
        dest = ROOT/'.runtime/inputs'/name
        dest.mkdir(exist_ok=True)
        files = {'model.inp':seal(dest/'model.inp',deck)}
        if not coupon:
            post_name = 'post.dat' if is_damage else 'post_corrected.dat'
            post = (folder/post_name).read_bytes()
            if digest(post) != sources[source]['files'][post_name]:
                raise ValueError(f'Postprocessing input hash failed: {name}')
            files['local_post.inp'] = seal(dest/'local_post.inp',post)
            files['moving.inp'] = seal(dest/'moving.inp',movement_deck(folder,job).encode())
        spec = dict(case=name,source=source,cased=not is_bare,coupon=coupon,job=job,
                    cores=config.get('solver_ranks',4),files=files)
        spec_bytes = (json.dumps(spec,indent=2)+'\n').encode()
        manifest[name] = dict(source=source,spec_sha256=seal(dest/'local_job.json',spec_bytes),
                              input_sha256=files['model.inp'])
    (ROOT/'validation/local_jobs.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__ == '__main__':
    stage()
