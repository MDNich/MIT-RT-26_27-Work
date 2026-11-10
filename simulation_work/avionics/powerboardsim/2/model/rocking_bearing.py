"""Test the flush nylon fixture with moment-free shank ends on the same four printed bearing patches."""
import argparse
import json
import re

import numpy as np

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from stage_local_jobs import seal

CONTROL = 'spherical_bearing_control_v1'
BASE = 'flush_nylon_lateral_friction_locked_seatfaces1'
CASE = 'flush_nylon_lateral_friction_locked_rock1_seatfaces1'
PILOTS = (950001, 950003, 950005, 950007)
COPIES = (955001, 955002, 955003, 955004)


def joint(element, left, right, xyz, section, cs):
    # An initially coincident spherical joint, without stops, springs, friction or applied moment.
    return [f'LOCAL,{cs},0,{xyz}', 'CSYS,0', f'SECTYPE,{section},JOINT,SPHE',
            f'SECJOINT,LSYS,{cs},{cs}', 'TYPE,855', f'SECNUM,{section}', f'EN,{element},{left},{right}']


def control_deck():
    lines = ['/BATCH', '/PREP7', 'ET,1,BEAM188', 'KEYOPT,1,3,3', 'MP,EX,1,69000', 'MP,PRXY,1,0.33',
             'SECTYPE,1,BEAM,CSOLID', 'SECDATA,2,12,2', 'ET,855,MPC184', 'KEYOPT,855,1,15',
             'N,1,0,0,0', 'N,2,80,0,0', 'N,3,80,0,0', 'N,4,240,0,0',
             'N,11,0,20,0', 'N,12,80,20,0', 'N,14,240,20,0', 'TYPE,1', 'MAT,1', 'SECNUM,1',
             'EN,1,1,2', 'EN,2,3,4', 'EN,11,11,12', 'EN,12,12,14']
    lines += joint(3, 2, 3, '80,0,0', 901, 901)
    lines += ['D,1,ALL,0', 'D,4,ALL,0', 'D,4,UZ,.1', 'D,11,ALL,0', 'D,14,ALL,0', 'D,14,UZ,.1',
              'FINISH', '/SOLU', 'ANTYPE,STATIC', 'EQSLV,SPARSE', 'NLGEOM,ON', 'NSUBST,4,20,4',
              'OUTRES,ALL,ALL', 'SOLVE', 'FINISH', '/POST1', 'SET,LAST', 'RSYS,0',
              '*GET,FA,NODE,4,RF,FZ', '*GET,FB,NODE,14,RF,FZ', '*GET,RA,NODE,2,ROT,Y',
              '*GET,RB,NODE,3,ROT,Y', '*GET,UA,NODE,2,U,Z', '*GET,UB,NODE,3,U,Z',
              'ESEL,S,TYPE,,855', 'ETABLE,JFX,SMISC,1', 'ETABLE,JFY,SMISC,2', 'ETABLE,JFZ,SMISC,3',
              'ETABLE,JMX,NMISC,22', 'ETABLE,JMY,NMISC,23', 'ETABLE,JMZ,NMISC,24',
              '*GET,QZ,ELEM,3,ETAB,JFZ', '*GET,AX,ELEM,3,ETAB,JMX',
              '*GET,AY,ELEM,3,ETAB,JMY', '*GET,AZ,ELEM,3,ETAB,JMZ',
              '*CFOPEN,bearing_control,csv', '*VWRITE',
              "('free_N,fixed_N,angle_i,angle_j,uz_i,uz_j,force_z,mx,my,mz')",
              '*VWRITE,FA,FB,RA,RB,UA,UB,QZ,AX,AY,AZ', "(E11.4,9(',',E11.4))", '*CFCLOS',
              '/COM,BEARING_CONTROL_FINISHED', 'FINISH', '/EXIT,NOSAVE', '']
    return '\n'.join(lines).encode()


def joint_post():
    lines = ['ALLSEL,ALL', 'RSYS,0', 'SET,LAST', '*GET,NSAV,ACTIVE,0,SET,NSET',
             '*CFOPEN,bearing_joints,csv', '*VWRITE', "('set,foot,time,translation_error_mm,rotation_rad,force_N,moment_Nmm')",
             '*DO,IK,1,NSAV', 'SET,,,,,,,IK', '*GET,SB,ACTIVE,0,SET,SBST', '*IF,SB,EQ,999999,THEN',
             '*CYCLE', '*ENDIF', '*GET,TK,ACTIVE,0,SET,TIME', 'ESEL,S,TYPE,,855', 'ETABLE,ERAS']
    for axis, xyz in enumerate('XYZ'):
        lines += [f'ETABLE,JF{xyz},SMISC,{1+axis}', f'ETABLE,JM{xyz},NMISC,{22+axis}', f'ETABLE,JR{xyz},SMISC,{64+axis}']
    lines += ['*DO,JJ,1,4', 'EI=1900009+JJ', 'PA=949999+2*JJ', 'PB=955000+JJ']
    for xyz in 'XYZ':
        lines += [f'*GET,UA{xyz},NODE,PA,U,{xyz}', f'*GET,UB{xyz},NODE,PB,U,{xyz}', f'DU{xyz}=UA{xyz}-UB{xyz}']
        for group in ('JF','JM','JR'):
            lines.append(f'*GET,{group}{xyz}V,ELEM,EI,ETAB,{group}{xyz}')
    lines += ['TD=SQRT(DUX**2+DUY**2+DUZ**2)', 'FJ=SQRT(JFXV**2+JFYV**2+JFZV**2)',
              'MJ=SQRT(JMXV**2+JMYV**2+JMZV**2)', 'RJ=SQRT(JRXV**2+JRYV**2+JRZV**2)',
              '*VWRITE,IK,JJ,TK,TD,RJ,FJ,MJ', "(F7.0,',',F3.0,5(',',E17.10))",
              '*ENDDO', '*ENDDO', '*CFCLOS', 'ALLSEL,ALL', '']
    return '\n'.join(lines)


def release_tab_rotations(original):
    """Introduce four coincident, translation-coupled bearing pilots in an existing tied-tab deck."""
    deck = original
    marker = 'SAVE,model,db'
    assert deck.count(marker) == 1 and deck.count('\nET,855,') == 0
    cards = ['! Only the four tab bearing rotations are released.', 'ALLSEL,ALL', 'CSYS,0',
             'ET,855,MPC184', 'KEYOPT,855,1,15', 'MAT,851']
    matrix = {}
    for i, (old, new) in enumerate(zip(PILOTS, COPIES, strict=True)):
        assert not re.search(rf'(?m)^N,{new},|^(?:CS|LOCAL),{901+i},|^SECTYPE,{901+i},|^EN,{1900010+i},', deck)
        (xyz,) = re.findall(rf'(?m)^N,{old},([^\n]+)$', deck)
        pattern = rf'(?m)^CERIG,{old},(\d+),UXYZ\n'
        nodes = re.findall(pattern, deck)
        assert len(nodes) > 3 and len(set(nodes)) == len(nodes)
        deck = re.sub(pattern, '', deck)
        cards.append(f'N,{new},{xyz}')
        cards += joint(1900010+i, old, new, xyz, 901+i, 901+i)
        cards += [f'CERIG,{new},{number},UXYZ' for number in nodes]
        matrix[str(old)] = dict(coincident_patch_pilot=new, coupled_PLA_nodes=len(nodes), joint_element=1900010+i)
    addition = '\n'.join(cards + ['ALLSEL,ALL', ''])
    modified = deck.replace(marker, addition + marker)
    assert modified.split(marker)[1] == original.split(marker)[1]
    return modified, matrix


def stage():
    rt = ROOT / '.runtime'
    control = rt / CONTROL
    control.mkdir(exist_ok=True)
    control_sha = seal(control / 'control.inp', control_deck())
    source = rt / 'inputs' / BASE
    source_spec = read(source / 'local_job.json')
    registered = read(ROOT / 'validation/local_seat_jobs.json')[BASE]
    verified(source / 'local_job.json', registered['spec_sha256'])
    for name, sha in source_spec['files'].items():
        verified(source / name, sha)
    original = (source / 'model.inp').read_text()
    modified, matrix = release_tab_rotations(original)
    dest = rt / 'inputs' / CASE
    dest.mkdir(exist_ok=True)
    moving = (source/'moving.inp').read_text()
    end = 'finish\n/exit,nosave'
    assert moving.count(end) == 1
    files = {'local_post.inp': seal(dest/'local_post.inp', (source/'local_post.inp').read_bytes()),
             'moving.inp': seal(dest/'moving.inp', moving.replace(end, joint_post() + end).encode())}
    files['model.inp'] = seal(dest/'model.inp', modified.encode())
    spec = dict(source_spec, case=CASE, files=files, rigid_reference=BASE, bearing_pilots=list(COPIES),
                bearing_control_sha256=control_sha, joints=matrix)
    spec_sha = seal(dest/'local_job.json', (json.dumps(spec, indent=2) + '\n').encode())
    write_json(ROOT/'validation/rocking_bearing_input.json', {CASE:dict(spec_sha256=spec_sha, input_sha256=files['model.inp'],
        control_sha256=control_sha, original_input_sha256=source_spec['files']['model.inp'], original_spec_sha256=registered['spec_sha256'],
        scope='Local fixed-PCB flush nylon sensitivity with coincident spherical shank/tab joints. Three translations '
              'are transmitted. The same nodal footprint, substrate contact, screw grip and loading path are retained.')})
    print(CASE, spec_sha)


def audit_control():
    folder = ROOT/'.runtime'/CONTROL
    record = read(ROOT/'validation/rocking_bearing_input.json')[CASE]
    verified(folder/'control.inp', record['control_sha256'])
    assert int((folder/'exit.txt').read_text(encoding='utf-8-sig').strip()) == 0
    listing = (folder/'control.out').read_text(errors='replace')
    assert 'BEARING_CONTROL_FINISHED' in listing and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b', listing)
    row, = table(folder/'bearing_control.csv')
    flexural_rigidity = 69000 * np.pi * 2**4 / 4
    free = 3 * flexural_rigidity * .1 / (80**3 + 160**3)
    fixed = 12 * flexural_rigidity * .1 / 240**3
    assert np.allclose([row['free_N'], row['fixed_N']], [free, fixed], rtol=.02, atol=1.e-8)
    assert np.isclose(abs(row['force_z']), abs(row['free_N']), rtol=.002)
    assert abs(row['uz_i']-row['uz_j']) < 1.e-7 and abs(row['angle_i']-row['angle_j']) > 1.e-5
    assert max(abs(row[k]) for k in ('mx','my','mz')) < 1.e-6
    write_json(ROOT/'validation/spherical_bearing_control.json', dict(input_sha256=record['control_sha256'],
        listing_sha256=digest(folder/'control.out'), table_sha256=digest(folder/'bearing_control.csv'),
        analytical_free_N=free, analytical_fixed_N=fixed, native={k:float(row[k]) for k in row.dtype.names},
        scope='Two clamped beams of unequal span with prescribed support translation. One pair shares an ordinary '
              'beam node. The other pair meets at a spherical joint with free relative rotations.'))


def audit_joint(case, campaign):
    """Check the four actual fixture joints against the forces at the free shank ends."""
    from ansys.mapdl import reader
    from local_equilibrium import positions
    folder = ROOT/'.runtime/archive'/campaign/case
    receipt = ROOT/'.runtime/receipts'/campaign/case
    ledger = read(receipt/'archived.json')
    assert (receipt/'released.txt').is_file() and (ledger['case'], ledger['campaign']) == (case, campaign)
    hashes = {v['name']:v['sha256'] for v in ledger['files']}
    for name in ('pull.rst','bearing_joints.csv','local_job.json','model.inp'):
        verified(folder/name, hashes[name])
    spec = read(folder/'local_job.json')
    ctrl = ROOT/'validation/spherical_bearing_control.json'
    assert read(ctrl)['input_sha256'] == spec['bearing_control_sha256'] and spec['case'] == case
    assert spec['files']['model.inp']==hashes['model.inp']
    assert case==CASE or spec.get('snug_bearing_control') is True
    r = reader.read_binary(folder/'pull.rst')
    geom = r.grid.cell_data
    mesh = r.mesh.elem
    order = np.argsort(r.mesh.enum)
    def connectivity(etype):
        en = np.sort(geom['ansys_elem_num'][geom['ansys_etype'] == etype])
        return en, np.stack([mesh[j][10:12] for j in order[positions(r.mesh.enum[order], en)]])
    beam, ends = connectivity(851)
    seats = np.sort(geom['ansys_elem_num'][geom['ansys_etype']==854])
    if len(seats):
        assert len(seats)==4 and np.array_equal(connectivity(854)[1],ends)
    jnums, pairs = connectivity(855)
    assert np.array_equal(jnums, np.arange(1900010,1900014))
    assert np.array_equal(ends, np.arange(950001,950009).reshape(4,2))
    assert np.array_equal(pairs[:,0], PILOTS) and np.array_equal(pairs[:,1], COPIES)
    assert np.array_equal(r.mesh.nodes[positions(r.mesh.nnum,pairs[:,0])],r.mesh.nodes[positions(r.mesh.nnum,pairs[:,1])])
    post = table(folder/'bearing_joints.csv')
    valid = np.flatnonzero(r._resultheader['ls_table'][:,1] != 999999) + 1
    assert np.array_equal(post['set'],np.repeat(valid,4)) and np.array_equal(post['foot'],np.tile(np.arange(1,5),len(valid)))
    assert np.allclose(post['time'],np.repeat(r.time_values[valid-1],4),rtol=0,atol=1.e-8)
    assert post['translation_error_mm'].max() < 2.e-6 and post['moment_Nmm'].max() < 1.e-5
    force_error = 0.
    max_end_moment = 0.
    for k in valid:
        en, values, _ = r.element_solution_data(int(k-1), 'ENF')
        first_end = np.stack([values[j].reshape(-1,6)[0] for j in positions(en,beam)])
        joint_force = post['force_N'][post['set']==k]
        transmitted=first_end[:,:3].astype(float)
        for i,j in enumerate(positions(en,seats)):
            spring=values[j]
            if spring is not None and len(spring):
                transmitted[i]+=spring.reshape(2,3)[0]
        magnitude = np.linalg.norm(transmitted,axis=1)
        delta = abs(magnitude-joint_force)
        assert np.all(delta < .005 + 2.e-4*joint_force), (k,delta)
        end_moment = float(np.max(np.linalg.norm(first_end[:,3:],axis=1)))
        assert end_moment < .005 + 2.e-4*max(joint_force), (k,end_moment)
        max_end_moment = max(max_end_moment, end_moment)
        force_error = max(force_error, float(delta.max()))
    loaded = post['force_N'] > 1.
    if loaded.any():
        assert post['rotation_rad'][loaded].max() > 1.e-7
    out = ROOT/'validation/bearing_joints'/(case+'.json')
    write_json(out,dict(case=case,campaign=campaign,sets=len(valid),rst_sha256=hashes['pull.rst'],
                        post_sha256=hashes['bearing_joints.csv'],control_sha256=digest(ctrl),joints=spec['joints'],
                        maximum_translation_error_mm=float(post['translation_error_mm'].max()),
                        maximum_relative_rotation_rad=float(post['rotation_rad'].max()),
                        maximum_joint_moment_Nmm=float(post['moment_Nmm'].max()),
                        maximum_shank_tip_moment_Nmm=max_end_moment, maximum_end_force_difference_N=force_error,
                        scope='Translation continuity, released moment and force transfer at four modeled shank/tab joints.'))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['stage', 'audit'])
    args = parser.parse_args()
    if args.operation == 'stage':
        stage()
    else:
        audit_control()
