"""Recover external forces and moments for every converged local-fixture RST set, in N and mm."""
import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

SCREW_PILOTS = (950002, 950004, 950006, 950008)
NEIGHBOR_PILOT = 959001
DOFS = ['UX', 'UY', 'UZ', 'ROTX', 'ROTY', 'ROTZ']


def positions(numbers, selected):
    index = np.searchsorted(numbers, selected)
    if np.any(index >= len(numbers)) or not np.array_equal(numbers[index], selected):
        raise ValueError('Missing fixture nodes in the native result')
    return index


def movement_table(path):
    """Read the three translations exported by native POST1 at moving physical supports."""
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    return {(int(float(r['set'])), int(float(r['node']))): [float(r[k]) for k in ('ux_mm','uy_mm','uz_mm')] for r in rows}


def reference_movements(folder, source):
    config = json.loads((source / 'config.json').read_text())
    pilot = json.loads((source / 'mesh.json').read_text())['pilot']
    with (folder / 'history.csv').open() as stream:
        movements = {(int(float(r['set'])), pilot): [float(r[k]) for k in ('ux_mm','uy_mm','uz_mm')]
                     for r in csv.DictReader(stream)}
    bottom = config.get('bottom_pilots', [])
    if bottom:
        with (folder / 'contact_history.csv').open() as stream:
            for r in csv.DictReader(stream):
                for i, node in enumerate(bottom, 1):
                    movements[int(float(r['set'])),node] = [0.,0.,float(r[f'washer{i}_uz'])]
    return movements


def movement_deck(source, job):
    config = json.loads((source / 'config.json').read_text())
    pilot = json.loads((source / 'mesh.json').read_text())['pilot']
    moving = [pilot, *config.get('bottom_pilots', [])]
    lines = ['/batch','resume,model,db','/post1',f'file,{job},rst','/nopr','allsel,all','rsys,0',
             'set,last','*get,nsets,active,0,set,nset','*cfopen,moving_supports,csv','*vwrite',
             "('set,node,ux_mm,uy_mm,uz_mm')", '*do,kk,1,nsets','set,,,,,,,kk',
             '*get,sb,active,0,set,sbst','*if,sb,eq,999999,then','*cycle','*endif']
    for node in moving:
        lines += [f'*get,d{a},node,{node},u,{a}' for a in 'xyz']
        lines += [f'*vwrite,kk,{node},dx,dy,dz',"(F9.0,',',F10.0,3(',',E20.12))"]
    return '\n'.join([*lines, '*enddo','*cfclos','finish','/exit,nosave',''])


def recover(path, source, movements, cased=False):
    config = json.loads((source / 'config.json').read_text())
    pilot = json.loads((source / 'mesh.json').read_text())['pilot']
    model = (source / 'model.inp').read_text()
    # Only physical restraints and external loading enter whole-fixture equilibrium.
    # Contact-generated constraint nodes may also carry RF entries in the RST.
    restraints = {int(x) for x in re.findall(r'^D,(\d+),', model, re.M | re.I)}
    restraints.add(pilot)
    if cased:
        restraints.update(SCREW_PILOTS)
        restraints.add(NEIGHBOR_PILOT)
    ids = np.array(sorted(restraints))
    result = reader.read_binary(str(path))
    geom_index = positions(result.mesh.nnum, ids)
    initial = result.mesh.nodes[geom_index]
    cell = positions(ids, np.array([pilot]))[0]
    bottom = positions(ids, np.array(config.get('bottom_pilots', []), dtype=int))
    records = []
    for k, ((step, substep, _), time) in enumerate(zip(result._resultheader['ls_table'], result.time_values, strict=True)):
        if substep == 999999:
            continue
        if result.result_dof(k) != DOFS:
            raise ValueError(f'Unexpected fixture DOF layout at set {k+1}')
        disp = np.zeros((len(ids),3))
        for index in [cell,*bottom]:
            disp[index] = movements[k+1,int(ids[index])]
        if not np.isfinite(disp).all():
            raise ValueError(f'Missing support motion at set {k+1}')
        values, nodes, dofs = result.nodal_reaction_forces(k)
        keep = np.isin(nodes, ids)
        applied = np.zeros((len(ids), 6))
        np.add.at(applied, (positions(ids, nodes[keep]), dofs[keep]-1), values[keep])
        cell_force = float(applied[cell, 0])
        # In step 1 each of the two moving bottom washers carries a ramped +Z load.
        if step == 1 and len(bottom):
            applied[bottom, 2] += config['preload_N'] * time
        xyz = initial + disp
        forces = applied[:, :3]
        total_force = forces.sum(axis=0)
        moment = (applied[:, 3:] + np.cross(xyz, forces)).sum(axis=0)
        moment_cell = moment - np.cross(xyz[cell], total_force)
        row = dict(native_set=k+1, loadstep=int(step), substep=int(substep), time=float(time),
                   ux_mm=float(disp[cell, 0]), cell_fx_N=cell_force)
        for stem, vector in [('force_N', total_force), ('moment_origin_Nmm',moment), ('moment_cell_Nmm',moment_cell)]:
            row.update({f'{stem}_{axis}': float(v) for axis, v in zip('xyz', vector)})
        if cased:
            screw_forces = forces[positions(ids, SCREW_PILOTS)]
            neighbor = forces[positions(ids, [NEIGHBOR_PILOT])][0]
            for axis, value in zip('xyz', screw_forces.sum(axis=0)):
                row['screw_support_N_'+axis] = float(value)
            for axis, value in zip('xyz', neighbor):
                row['neighbor_support_N_'+axis] = float(value)
        records.append(row)
    if not records or np.any(np.diff([row['time'] for row in records]) <= 0):
        raise ValueError('Missing or nonmonotonic converged fixture history')
    return records


def write_csv(records, path):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rst', type=Path)
    parser.add_argument('source', type=Path)
    parser.add_argument('native_movements', type=Path)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--cased', action='store_true')
    args = parser.parse_args()
    write_csv(recover(args.rst, args.source, movement_table(args.native_movements), args.cased), args.csv)
