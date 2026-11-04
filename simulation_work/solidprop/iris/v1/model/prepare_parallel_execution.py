"""Create fresh SMP successor packages and explicitly inherit an accepted pause.

Never edit sealed parents or start a solver. The copied prefix remains byte-for-
byte original; only the live controller state's configuration identity changes.
"""
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from coupler import fingerprint
from ops import ROOT, TMP, atomic, disks, utc
from validate_run import validate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(parent_name, name, cores=10, horizon=None):
    disks()
    parent=TMP/'runs'/parent_name
    target=TMP/'runs'/name
    assert parent.parent==target.parent==TMP/'runs'
    assert not target.exists(), 'Preserve every existing package'
    cfg=json.loads((parent/'config.json').read_text())
    changed=copy.deepcopy(cfg)
    changed.update(ranks=cores,parallel_mode='smp',windows_root='C:\\IrisStudy\\runs\\'+name,
                   host_runtime='I:\\ansystmp\\runs\\'+name)
    changed['provenance']['parallel_execution_parent']=dict(runtime=parent_name,
        config_sha256=sha(parent/'config.json'),requested_cores=cores,
        authorization='User requested ten ANSYS cores on November 4, 2026.')
    if horizon is not None:
        changed.update(end_time_s=horizon,campaign_role='parallel_restart_verification')
    path=ROOT/'configs'/f'{name}.json'
    assert not path.exists()
    atomic(path,changed)
    subprocess.run([sys.executable,str(ROOT/'model/prepare_model.py'),'--config',str(path),'--output',str(target)],
                   check=True,stdout=subprocess.DEVNULL)
    # Physics, geometry, material and controller bytes are unchanged.
    for filename in ['model_base.inp','mesh_map.json','material_v0.apdl','export_fields.mac','coupler.py','usermatth.F','usermatthLib.dll']:
        assert sha(parent/filename)==sha(target/filename),filename
    print('Prepared',name,cores,'SMP cores',flush=True)


def seed(parent_name, name):
    disks()
    parent=TMP/'runs'/parent_name;target=TMP/'runs'/name
    assert parent.parent==target.parent==TMP/'runs'
    assert not (target/'state.json').exists()
    checked=validate(parent,allow_paused=True)
    state=json.loads((parent/'state.json').read_text())
    assert state['status']=='PAUSED_AT_CHECKPOINT'
    cfg=json.loads((target/'config.json').read_text())
    assert cfg['provenance']['parallel_execution_parent']['runtime']==parent_name
    slot=parent/f'accepted_restart_{state["index"]%2}'
    manifest=json.loads((slot/'manifest.json').read_text())
    assert manifest['accepted_index']==state['index']
    for filename,want in manifest['files'].items():
        assert sha(slot/filename)==want
        if filename!='state.json':shutil.copy2(slot/filename,target/filename)
    # Keep completed prefix fields and audits immutable, and retain its native log.
    prefix={}
    (target/'checkpoints').mkdir()
    for source in sorted((parent/'checkpoints').iterdir()):
        if int(source.name.split('_')[1].split('.')[0])>state['index']:continue
        destination=target/'checkpoints'/source.name
        shutil.copy2(source,destination)
        assert sha(source)==sha(destination)
        prefix[str(destination.relative_to(target))]=sha(source)
    for source in parent.glob('solve_*.out'):
        prefix[source.name]=sha(source)
        shutil.copy2(source,target/source.name)
    for filename in ['file.rth','file.db','file.esav','file.full']:
        source=parent/filename
        if source.exists():shutil.copy2(source,target/filename)
    state['config_sha256']=fingerprint(cfg)
    state['status']='PAUSED_AT_CHECKPOINT'
    atomic(target/'state.json',state)
    atomic(target/'restart_lineage.json',dict(created_utc=utc(),parent_runtime=parent_name,
        parent_config_sha256=sha(parent/'config.json'),accepted_index=state['index'],accepted_time_s=state['time_s'],
        accepted_parent_validation=checked,copied_prefix_sha256=prefix,
        restart_manifest_sha256=sha(slot/'manifest.json'),native_restart_sha256=manifest['files'],
        successor_config_sha256=sha(target/'config.json'),
        note='Original accepted prefix and parent remain unchanged. The live state fingerprint is migrated to the physically identical successor configuration.'))
    print('Seeded accepted checkpoint',name,state['index'],state['time_s'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','seed']);p.add_argument('parent');p.add_argument('name')
    p.add_argument('--cores',type=int,default=10);p.add_argument('--horizon',type=float);a=p.parse_args()
    if a.action=='prepare':prepare(a.parent,a.name,a.cores,a.horizon)
    else:seed(a.parent,a.name)
