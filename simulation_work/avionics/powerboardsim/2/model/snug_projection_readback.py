"""Prepare a serial POST1 inventory to reconcile the projection control's extended records.

This reads an immutable completed result. It does not solve or release the physical control.
CONTA174 corner sequences follow the 2026 R1 Element Reference, Table 174.3:
https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_elem/Hlp_E_CONTA174.html
"""
import argparse
import csv
import ctypes
import os
import re
import shutil

import numpy as np

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from native_rst import read_rst
from stage_local_jobs import seal

CASE = 'snug125_aluminium_project3_static'
CAMPAIGN = 'nov08_01'
OUT = ROOT / '.runtime' / ('projection_readback_' + CASE + '_' + CAMPAIGN)


def corner_table(all_ids, nsets):
    """Recover only the overflowing corner label from the sealed nested-loop order.

    MAPDL F1.0 prints '*' because even '1.' requires two characters. Every
    numerical field remains native output; no missing field value is inferred.
    """
    path = OUT / 'corners.csv'
    deck = (OUT / 'control.inp').read_text()
    assert '*do,ii,1,ns' in deck and '*do,kk,1,4' in deck
    assert "(F3.0,',',F10.0,',',F1.0,',',F5.1,2(',',E18.10))" in deck
    with path.open(newline='') as handle:
        rows = list(csv.reader(handle))
    names = ('set', 'element', 'corner', 'status', 'signed_pen_m', 'pressure_Pa')
    assert tuple(rows[0]) == names
    assert len(rows) - 1 == nsets * 4 * len(all_ids)
    assert np.all(np.diff(all_ids) > 0)
    values = np.empty(len(rows) - 1, dtype=[(name, float) for name in names])
    recovered = 0
    for j, row in enumerate(rows[1:]):
        assert len(row) == len(names)
        block, index = divmod(j, len(all_ids))
        station, corner = divmod(block, 4)
        assert float(row[0]) == station + 1 and float(row[1]) == all_ids[index]
        if row[2].strip() == '*':
            recovered += 1
            row[2] = str(corner + 1)
        else:
            assert float(row[2]) == corner + 1
        values[j] = tuple(map(float, row))
    assert recovered in (0, len(values))
    assert np.isfinite(values.view(float)).all()
    return values, dict(recovered_corner_labels=recovered, numerical_fields_recovered=0,
                        method='Verified complete set/corner/ascending-element loop order from sealed input; '
                               'each set and element ID checked. Raw CSV preserved unchanged.')


def prepare():
    assert shutil.disk_usage(ROOT).free >= 400_000_000_000
    archive = ROOT / '.runtime/archive' / CAMPAIGN / CASE
    receipt = ROOT / '.runtime/receipts' / CAMPAIGN / CASE
    assert (receipt / 'released.txt').is_file()
    meta = read(receipt / 'archived.json')
    status = read(receipt / 'status.json')
    assert meta['case'] == status['case'] == CASE and status['phase'] == 'solver_complete'
    assert status['exit'] == 0
    hashes = {f['name']: f['sha256'] for f in meta['files']}
    OUT.mkdir(exist_ok=True)
    clone = ctypes.CDLL(None, use_errno=True).clonefile
    for name in ('file.rdb', 'file.rst'):
        source, dest = archive / name, OUT / name
        verified(source, hashes[name])
        if not dest.exists() and clone(os.fsencode(source), os.fsencode(dest), 0):
            raise OSError(ctypes.get_errno(), 'Independent readback clone failed')
        assert source.stat().st_ino != dest.stat().st_ino
        verified(dest, hashes[name])
    lines = ['/batch', 'resume,file,rdb', '/post1', 'file,file,rst', 'rsys,0',
             'allsel,all', 'set,last', '*get,ns,active,0,set,nset',
             'esel,s,type,,853', '*get,nc,elem,0,count',
             '*cfopen,selection,csv', '*vwrite',
             "('element,real,material,n1,n2,n3,n4,n5,n6,n7,n8')", 'ee=0', '*do,j,1,nc',
             'ee=elnext(ee)', '*get,rr,elem,ee,attr,real', '*get,mm,elem,ee,attr,mat']
    lines += [f'*get,nn{i},elem,ee,node,{i}' for i in range(1, 9)]
    lines += ['*vwrite,ee,rr,mm,nn1,nn2,nn3,nn4,nn5,nn6,nn7,nn8',
              "(F10.0,10(',',F9.0))", '*enddo', '*cfclos',
              '*cfopen,corners,csv', '*vwrite', "('set,element,corner,status,signed_pen_m,pressure_Pa')",
              '*do,ii,1,ns', 'allsel,all', 'set,,,,,,,ii', 'esel,s,type,,853',
              '*get,nc,elem,0,count', '*do,kk,1,4', 'etable,eras',
              'etable,cstat,nmisc,kk', 'jp=kk+8', 'etable,cpen,nmisc,jp', 'etable,cpres,smisc,kk',
              'ee=0', '*do,j,1,nc', 'ee=elnext(ee)',
              '*get,ss,elem,ee,etab,cstat', '*get,pp,elem,ee,etab,cpen', '*get,pr,elem,ee,etab,cpres',
              '*vwrite,ii,ee,kk,ss,pp,pr', "(F3.0,',',F10.0,',',F1.0,',',F5.1,2(',',E18.10))",
              '*enddo', '*enddo', '*enddo', '*cfclos', '*cfopen,forces,csv', '*vwrite',
              "('set,element,status,mean_pressure_Pa,fx_N,fy_N,fz_N')",
              '*do,ii,1,ns', 'allsel,all', 'set,,,,,,,ii', 'esel,s,type,,853',
              '*get,nc,elem,0,count', 'etable,eras', 'etable,cstat,nmisc,41',
              'etable,cpres,smisc,13', 'etable,cfx,nmisc,43', 'etable,cfy,nmisc,44', 'etable,cfz,nmisc,45',
              'ee=0', '*do,j,1,nc', 'ee=elnext(ee)',
              '*get,ss,elem,ee,etab,cstat', '*get,pp,elem,ee,etab,cpres',
              '*get,fx,elem,ee,etab,cfx', '*get,fy,elem,ee,etab,cfy', '*get,fz,elem,ee,etab,cfz',
              '*vwrite,ii,ee,ss,pp,fx,fy,fz', "(F3.0,',',F10.0,',',F5.1,4(',',E18.10))",
              '*enddo', '*enddo', '*cfclos', 'allsel,all',
              '/com,PROJECTION_READBACK_FINISHED', 'finish', '/exit,nosave']
    sha = seal(OUT / 'control.inp', ('\r\n'.join(lines) + '\r\n').encode())
    spec = dict(case=CASE, campaign=CAMPAIGN, source_rst_sha256=hashes['file.rst'],
                source_rdb_sha256=hashes['file.rdb'], post_input_sha256=sha,
                native_contact_table_sha256=hashes['case_contact.csv'],
                scope='Inventory all resumed TYPE 853 entities and recover each corner and element force. '
                      'No physical result is accepted by this preparation.')
    if (OUT / 'request.json').exists():
        assert read(OUT / 'request.json') == spec
    else:
        write_json(OUT / 'request.json', spec)
    write_json(ROOT/'validation/snug125/projection_readback_input.json',
               dict(**spec, workdir=str(OUT.relative_to(ROOT)), structural_solve_requested=False,
                    scheduled='Serial POST1 inspection after the current native case boundary',
                    outputs=['selection.csv', 'corners.csv', 'forces.csv']))
    print(OUT, flush=True)


def audit():
    spec = read(OUT / 'request.json')
    for name, key in [('file.rst', 'source_rst_sha256'), ('file.rdb', 'source_rdb_sha256'),
                      ('control.inp', 'post_input_sha256')]:
        verified(OUT / name, spec[key])
    assert (OUT / 'exit.txt').read_text(encoding='utf-8-sig').strip() == '0'
    log = (OUT / 'control.out').read_text(errors='replace')
    assert 'PROJECTION_READBACK_FINISHED' in log
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b', log)
    raw = read_rst(OUT / 'file.rst')
    selected, force = [table(OUT / (name + '.csv')) for name in ('selection', 'forces')]
    grid = raw.grid.cell_data
    ids = np.sort(grid['ansys_elem_num'][grid['ansys_etype'] == 853])
    all_ids = selected['element'].astype(int)
    corner, label_recovery = corner_table(all_ids, raw.nsets)
    assert len(np.unique(all_ids)) == len(all_ids) and np.isin(ids, all_ids).all()
    extra = np.setdiff1d(all_ids, ids)
    original = selected[np.isin(all_ids, ids)]
    by_nodes = {tuple(int(row[f'n{i}']) for i in range(1, 9)): row for row in original}
    assert len(by_nodes) == len(ids)
    duplicates = []
    for row in selected[np.isin(all_ids, extra)]:
        parent = by_nodes[tuple(int(row[f'n{i}']) for i in range(1, 9))]
        assert row['material'] == parent['material']
        assert row['real'] != parent['real']
        duplicates.append(dict(element=int(row['element']), original_element=int(parent['element']),
                               real=int(row['real']), original_real=int(parent['real'])))
    assert len(corner) == raw.nsets * len(all_ids) * 4 and len(force) == raw.nsets * len(all_ids)
    archive = ROOT / '.runtime/archive' / CAMPAIGN / CASE
    native_summary = table(archive / 'case_contact.csv')
    verified(archive / 'case_contact.csv', spec['native_contact_table_sha256'])
    native_force = table(archive / 'snug_contact_force.csv')
    rows = []
    for k in range(raw.nsets):
        enum, data, nodes = raw.element_solution_data(k, 'ECT')
        loc = np.searchsorted(enum, ids)
        np.testing.assert_array_equal(enum[loc], ids)
        observed = np.empty((len(ids), 4, 3))
        expected = np.zeros_like(observed)
        layouts = {}
        for j, i in enumerate(loc):
            values = data[i]
            if values is None or not len(values):
                continue
            assert len(nodes[i]) == 4 and len(values) >= 40
            fields = values[:40].reshape(4, 10)
            expected[j] = fields[:, :3]
            layouts[str(len(values))] = layouts.get(str(len(values)), 0) + 1
        for c in range(1, 5):
            q = corner[(corner['set'] == k + 1) & (corner['corner'] == c)]
            order = np.argsort(q['element']);q = q[order]
            pos = np.searchsorted(q['element'], ids)
            np.testing.assert_array_equal(q['element'][pos], ids)
            q = q[pos]
            observed[:, c-1, :] = np.column_stack((q['status'], np.maximum(q['signed_pen_m'], 0), q['pressure_Pa']))
        np.testing.assert_allclose(observed, expected, rtol=3e-6, atol=1e-12)
        f = force[force['set'] == k + 1]
        np.testing.assert_array_equal(np.sort(f['element']), np.sort(all_ids))
        aux = f[np.isin(f['element'], extra)]
        q = corner[corner['set'] == k + 1]
        statuses = q['status'].reshape(4, len(all_ids))
        means = statuses.mean(0)
        # CONT,STAT in the original table averages the corner values, including
        # fractional means. Its integer ESEL bins therefore omit mixed faces.
        bins = [int(np.count_nonzero(means == j)) for j in range(4)]
        native_row = native_summary[k]
        assert native_row['set'] == k + 1 and native_row['n_contact'] == len(all_ids)
        assert bins == [int(native_row[key]) for key in ('far', 'near', 'sliding', 'sticking')]
        np.testing.assert_allclose([f['f'+a+'_N'].sum() for a in 'xyz'],
                                   [native_force[k]['f'+a+'_N'] for a in 'xyz'], rtol=1e-8, atol=1e-12)
        # This audit is deliberately scoped to the all-open projection control.
        assert np.all(statuses < 2) and np.all(f['status'] < 2)
        assert np.all(q['pressure_Pa'] == 0) and np.all(f['mean_pressure_Pa'] == 0)
        assert all(np.all(f['f'+a+'_N'] == 0) for a in 'xyz')
        rows.append(dict(native_set=k+1, ECT_record_lengths=layouts,
                         maximum_corner_difference=np.max(abs(observed-expected), axis=(0, 1)).tolist(),
                         auxiliary_closed=int(np.count_nonzero(aux['status'] >= 2)),
                         auxiliary_max_pressure_Pa=float(aux['mean_pressure_Pa'].max(initial=0)),
                         auxiliary_force_N=[float(aux['f'+a+'_N'].sum()) for a in 'xyz'],
                         native_integer_status_bins=bins, mixed_corner_entities=int(np.count_nonzero(means % 1)),
                         all_native_entities_open_and_force_free=True))
    write_json(OUT / 'inventory_audit.json', dict(**spec, original_faces=len(ids),
               resumed_type853_entities=len(all_ids), additional_entities=extra.tolist(), states=rows,
               additional_entity_original_face_mapping=duplicates,
               additional_entity_scope='Every added entity has the same ordered eight-node connectivity and '
                                       'material as one original face, with a different real-constant ID. '
                                       'Both original and additional entities have zero native force at all states.',
               selection_sha256=digest(OUT/'selection.csv'), corners_sha256=digest(OUT/'corners.csv'),
               forces_sha256=digest(OUT/'forces.csv'), corner_label_recovery=label_recovery,
               physical_control_accepted=False,
               next_action='Reconcile additional native entities, record extensions, and whole-state balances '
                           'before integrating this inventory into the global audit.'))
    print('Projection inventory checked; physical acceptance still pending', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'audit'))
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else audit)()
