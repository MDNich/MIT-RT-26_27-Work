"""Prepare fresh physical-sector inputs for startup, terminal, and whole-exposure verification."""
import argparse
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from ops import ROOT, disks
from prepare_sector_exposures import PACKAGE as PREVIOUS, sha

PACKAGE = PREVIOUS.parent/'whole_sector_r2'
PROOF = ROOT/'validation/terminal_brick_geometry.json'
JOBS = ('start2al','start2cf','end2sa','end2sc','end2ba','end2bc','wall2sa','wall2sc','wall2ba','wall2bc')
PARENTS = ('wallsa','wallsc','wallsa','wallsc','wallba','wallbc','wallsa','wallsc','wallba','wallbc')


def replace_once(source, before, after):
    if source.count(before)!=1:
        raise ValueError('Predecessor expression changed: '+before)
    return source.replace(before,after)


def archive():
    manifest = json.loads((PREVIOUS/'manifest.json').read_text())
    original = (PREVIOUS/'controller.zip').read_bytes()
    if sha(original)!=manifest['controller.zip']:
        raise ValueError('Sealed predecessor changed')
    with ZipFile(BytesIO(original)) as source:
        modules = {p:source.read(p) for p in source.namelist()}
    controller = modules['sector_exposure.py'].decode()
    controller = replace_once(controller,'from sector_wall import FEState, Sector',
                              'from sector_wall import FEState, Sector\nfrom copy import deepcopy\nfrom sector_terminal_step import end_step')
    controller = replace_once(controller,'    if initial_record is None:',
                              "    if initial_record is None:\n        initial_record = deepcopy(settings.get('donor_record'))\n    if initial_record is None:")
    controller = replace_once(controller,'wall.advance(state, min(dt, end-before, next_output-before), backend)',
                              'wall.advance(state, end_step(wall, state, min(dt, end-before, next_output-before), dt), backend)')
    modules['sector_exposure.py'] = controller.encode()
    modules['sector_terminal_step.py'] = (ROOT/'model/sector_terminal_step.py').read_bytes()
    result = BytesIO()
    with ZipFile(result,'w') as out:
        for name,data in sorted(modules.items()):
            out.writestr(ZipInfo(name,(2026,1,1,0,0,0)),data,compress_type=ZIP_DEFLATED)
    return result.getvalue()


def encode(data):
    return (json.dumps(data,indent=2,allow_nan=False)+'\n').encode('ascii')


def build():
    proof = json.loads(PROOF.read_text())
    assert proof['source_sha256']==sha((ROOT/'model/check_terminal_brick_geometry.py').read_bytes())
    assert proof['step_sha256']==sha((ROOT/'model/sector_terminal_step.py').read_bytes())
    files = {'controller.zip':archive()}
    signature = sha(files['controller.zip'])
    for job,parent in zip(JOBS,PARENTS):
        row = proof['cases'][parent]
        assert row['candidate_peak_edge_ratio']<20 and max(map(abs,row['balance_errors'].values()))<1e-7
        settings = json.loads((PREVIOUS/(parent+'_settings.json')).read_text())
        settings.update(job=job,role='startup' if job.startswith('start') else 'terminal' if job.startswith('end') else 'whole')
        settings['configuration']['geometry'] = row['geometry']
        if settings['role']=='startup':
            settings['horizon_s'] = .1
        if settings['role']=='terminal':
            warm = row['warm_station']
            settings['donor_record'] = dict(state=warm['state'],stats=dict(steps=warm['steps'],cutbacks=0,
                sums=warm['sums'],events={},samples=[],max_step_energy_error=0.))
        config = encode(settings)
        files[job+'_settings.json'] = config
        deck = (PREVIOUS/(parent+'.inp')).read_text(encoding='ascii')
        deck = replace_once(deck,PREVIOUS.name,PACKAGE.name)
        deck = replace_once(deck,parent+'_settings.json',job+'_settings.json')
        old = json.loads((PREVIOUS/(parent+'.json')).read_text())
        deck = replace_once(deck,old['controller_sha256'],signature)
        deck = replace_once(deck,old['settings_sha256'],sha(config))
        files[job+'.inp'] = deck.encode('ascii')
        files[job+'.json'] = encode(dict(job=job,case=settings['case'],role=settings['role'],
            deck_sha256=sha(files[job+'.inp']),controller_sha256=signature,settings_sha256=sha(config),
            geometry_audit_sha256=sha(PROOF.read_bytes()),reference_end_s=row['candidate_end_s'],
            max_field_error_K=2e-6,max_transverse_error_K=.001,max_balance_relative=1e-7,
            max_event_relative=.01,donor_start_s=settings.get('donor_record',{}).get('state',{}).get('time',0.)))
    files['manifest.json'] = encode({k:sha(v) for k,v in files.items()})
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('preview','prepare','verify'))
    action=parser.parse_args().action
    disks()
    files=build()
    if action=='prepare':
        if PACKAGE.exists(): raise FileExistsError('Sealed endpoint package exists')
        with TemporaryDirectory(dir=PACKAGE.parent) as tmp:
            stage=Path(tmp)/'stage'
            stage.mkdir()
            for name,data in files.items():
                (stage/name).write_bytes(data)
            stage.rename(PACKAGE)
    if action=='verify':
        assert set(files)=={p.name for p in PACKAGE.iterdir()}
        for name,data in files.items(): assert (PACKAGE/name).read_bytes()==data
    print(action,len(JOBS),'cases',sha(files['controller.zip']))


if __name__=='__main__':
    main()
