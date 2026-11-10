"""Repeat the modal displacement extraction on the installed 3 mm nylon case for the outer-pocket mesh check."""
import numpy as np

from audit_local import ROOT,read
from case_stress import source
from film_identity import digest,verified,write_json
from independent_motion_clip import prepare
from modal_correspondence import compare
from seeded_motion import participation
from snug_modal_mesh import run as jacobians
from stage_local_jobs import seal
from stage_snug_fit import AUDIT,INPUTS,STEP_HASH

BRANCH='snug125_nylon_mesh3'
CASE=BRANCH+'_basis'
PARENT=BRANCH+'_static'
REFERENCE='snug125_nylon_basis'
RECORD=AUDIT/'coarse_geometry_modes.json'


def stage(campaign='nov08_01'):
    catalog=read(AUDIT/'global_inputs.json')
    parent,nominal=catalog[PARENT],catalog[REFERENCE]
    assert parent['step_sha256']==nominal['step_sha256']==STEP_HASH
    assert parent['tab_spacing_mm']==nominal['tab_spacing_mm']==1.25 and parent['size_mm']==3
    installed_path=AUDIT/(PARENT+'_installed.json')
    installed=read(installed_path);assert installed['linearization_review_passed']
    proof=read(ROOT/'validation/global'/(PARENT+'.json'))
    assert installed['case']==proof['case']==PARENT and installed['rst_sha256']==proof['rst_sha256']
    receipt=ROOT/'.runtime/receipts'/campaign/PARENT
    assert (receipt/'released.txt').is_file()
    ledger=read(receipt/'archived.json')
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    assert len([k for k in hashes if k.endswith('.r001')])>=12
    assert hashes['file.rst']==proof['rst_sha256'] and hashes['model.inp']==parent['input_sha256']
    path=INPUTS/REFERENCE/'model.inp';verified(path,nominal['input_sha256'])
    original=path.read_bytes()
    nl=b'\r\n' if b'\r\n' in original else b'\n'
    start=original.index(b'outres,strs,all,');stop=original.index(b'dmpopt,esav,no',start)
    old=original[start:stop]
    assert old.splitlines()==[b'outres,strs,all,',b'outres,epel,all,',b'outres,eppl,all,',
                              b'outres,rsol,all',b'outres,nload,all,',
                              b'mxpand,,,,yes,,yes, ! expand requested element results, and write them to file.mode']
    assert original[:start].endswith(b'outres,nsol,all'+nl) and original.count(b'modopt,lanb,60,1.,4000.')==1
    nodal=b'mxpand,all,,,no,,no ! expand mode displacements for geometric verification'+nl
    deck=original[:start]+nodal+original[stop:];assert deck.replace(nodal,old)==original
    target=INPUTS/CASE;target.mkdir(exist_ok=True)
    write_json(RECORD,dict(case=CASE,parent=PARENT,reference=REFERENCE,input_sha256=seal(target/'model.inp',deck),
               parent_input_sha256=parent['input_sha256'],reference_input_sha256=nominal['input_sha256'],
               step_sha256=STEP_HASH,tab_spacing_mm=1.25,mesh_sha256=parent['mesh_sha256'],size_mm=3,
               installed_sha256=digest(installed_path),static_rst_sha256=proof['rst_sha256'],
               scope='Same bolt-lock perturbation, eigenvalue search, normalization and constraints as the nominal basis. '
                     'Exports nodal motion for the coarse-mesh geometry and frequency comparison.'))


def audit(campaign):
    spec=read(RECORD);proof,folder,modal=source(CASE,campaign)
    verified(folder/'model.inp',spec['input_sha256'])
    receipt=ROOT/'.runtime/receipts'/campaign/CASE
    status=read(receipt/'status.json')
    assert (receipt/'released.txt').is_file() and status['parent']==PARENT and status['shared_scratch']
    verified(AUDIT/(PARENT+'_installed.json'),spec['installed_sha256'])
    log=folder/'solve.out'
    verified(log,next(r['sha256'] for r in read(receipt/'archived.json')['files'] if r['name']=='solve.out'))
    f=modal.time_values
    for axis in 'XYZ':
        g=participation(log.read_text(errors='replace'),axis)
        assert len(f)==len(g) and np.isfinite(g).all() and abs(g).max()>0
    jacobians(BRANCH,campaign)
    nominal=ROOT/'.runtime/archive'/campaign/REFERENCE/'file.rst'
    matches=compare(nominal,folder/'file.rst')
    assert matches['candidate_rst_sha256']==proof['rst_sha256']
    assert matches['reference_rst_sha256']==read(ROOT/'validation/global'/(REFERENCE+'.json'))['rst_sha256']
    assert matches['common_original_solid_nodes']==read(AUDIT/'nylon_modal_mesh_comparison.json')['native_mode_matching']['common_original_solid_nodes']
    for axis in 'XYZ':prepare(BRANCH,axis,campaign)
    write_json(AUDIT/'coarse_geometry_modes_audit.json',dict(case=CASE,registry_sha256=digest(RECORD),
               geometry_sha256=digest(AUDIT/(CASE+'_mesh.json')),matching=matches,frequencies_Hz=f.tolist(),
               reference_integration_sha256={a:digest(ROOT/'validation/independent_motion'/(BRANCH+'_motion_'+a+'.json')) for a in 'XYZ'}))


if __name__=='__main__':stage()
