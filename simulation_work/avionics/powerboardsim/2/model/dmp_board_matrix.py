"""Recover symmetric K, M and displacement constraints from the twelve original modal FULL files.

Record layouts follow the ANSYS 2026 R1 Programmer's Reference, section 1.9.
The modal-reuse FULL used for enforced base motion has a different constraint set.
"""
import numpy as np
from ansys.mapdl import reader
from ansys.mapdl.reader import _binary_reader
from scipy.sparse import coo_matrix, diags

from film_identity import verified


def records(stream, pointer):
    while True:
        values, words = stream.read_record(int(pointer), True)
        yield values
        pointer += words


def doubles(stream, count):
    values = next(stream)
    # Reader 0.56 can expose a word count for an uncompressed double record.
    # This record has exactly one value per declared column.
    assert values.dtype == np.float64 and len(values) in (count, 2*count)
    return values[:count]


def symmetric_part(stream, header, pointer_key, count_key, equation_map):
    count = int(header[count_key])
    n = int(header['GlbnVars'])
    rows = np.empty(count, dtype=np.int32)
    columns = np.empty(count, dtype=np.int32)
    values = np.empty(count)
    blocks = records(stream, header[pointer_key])
    offset = 0
    for local_col in range(int(header['neqn'])):
        local_rows = next(blocks).astype(np.int32)-1
        assert np.all((local_rows >= 0) & (local_rows < len(equation_map)))
        stop = offset + len(local_rows)
        assert stop <= count
        target_rows = equation_map[local_rows]
        target_col = equation_map[local_col]
        rows[offset:stop] = np.minimum(target_rows, target_col)
        columns[offset:stop] = np.maximum(target_rows, target_col)
        values[offset:stop] = doubles(blocks, len(local_rows))
        offset = stop
    assert offset == count and np.isfinite(values).all()
    part = coo_matrix((values, (rows, columns)), shape=(n, n)).tocsc()
    part.eliminate_zeros()
    return part


def read_constraints(stream, header, mapping):
    count = int(header['ncefull'])
    if count == 0:
        return None
    blocks = records(stream, header['ptrCE'])
    dependent = mapping[next(blocks)[:count]-1]
    assert np.max(abs(doubles(blocks, count))) < 1e-12
    dims = next(blocks)
    assert dims[0] == dims[1] == count and (next(blocks) == 1).all()
    widths = next(blocks)
    assert len(widths) == count and np.all(widths > 0)
    columns = np.empty(int(widths.sum()), dtype=np.int32)
    values = np.empty(len(columns))
    offset = 0
    for width in widths:
        idx = next(blocks)
        assert len(idx) == width
        columns[offset:offset+width] = mapping[idx-1]
        values[offset:offset+width] = doubles(blocks, width)
        offset += width
    n = int(header['GlbnVars'])
    local = coo_matrix((values, (np.repeat(dependent,widths),columns)), shape=(n,n)).tocsr()
    assert np.isfinite(values).all() and len(np.unique(dependent)) == count
    return dependent, local


def assemble(folder, hashes):
    stiffness = mass = dofs = None
    fixed = set()
    constraints = []
    sources = {}
    for rank in range(12):
        path = folder/f'file{rank}.full'
        sources[path.name] = verified(path, hashes[path.name])
        header = reader.read_binary(path)._header
        assert header['distKey'] == 1 and header['keyuns'] == header['lumpm'] == 0
        stream = _binary_reader.AnsysFile(str(path))
        try:
            intro = records(stream,0)
            next(intro)
            native_header = next(intro)
            next(intro)  # native DOF labels
            local_nodes = next(intro)
            if rank == 0:
                global_nodes = next(intro)
                dofs = np.full((int(header['GlbnVars']),2),-1,dtype=np.int32)
                expected_free = int(header['Glbneqn'])
                expected_constraints = int(header['GlbfCE'])
            assert len(local_nodes) == header['lenbac'] and len(dofs) == header['GlbnVars']
            table = records(stream,header['ptrDOF'])
            widths, labels, node_map = next(table), next(table), next(table)
            next(table)  # owner ranks of extended nodes
            mapping = np.abs(next(table))-1
            assert (len(widths),len(mapping)) == tuple(native_header[117:119])
            assert np.all((mapping >= 0) & (mapping < len(dofs)))
            assert np.all((node_map >= 1) & (node_map <= len(global_nodes)))
            local_dofs = np.column_stack((np.repeat(global_nodes[node_map-1],widths),abs(labels)-1))
            known = dofs[mapping,0] >= 0
            assert np.array_equal(dofs[mapping[known]],local_dofs[known])
            dofs[mapping] = local_dofs
            fixed.update(mapping[labels<0].tolist())
            for pointer, count in [('ptrSTF','ntermKl'),('ptrMAS','ntermMl')]:
                part = symmetric_part(stream,header,pointer,count,mapping)
                if pointer == 'ptrSTF':
                    stiffness = part if stiffness is None else stiffness+part
                else:
                    mass = part if mass is None else mass+part
            block = read_constraints(stream,header,mapping)
            if block is not None:
                constraints.append(block)
        finally:
            stream.close()
    assert (dofs>=0).all() and len(np.unique(dofs[:,0].astype(np.int64)*8+dofs[:,1]))==len(dofs)
    dependencies = np.concatenate([idx for idx,_ in constraints])
    copies = np.bincount(dependencies,minlength=len(dofs))
    dependent = np.flatnonzero(copies)
    transfer = diags(1/np.maximum(copies,1)) @ sum(mat for _,mat in constraints)
    worst_copy = max(float(abs((mat-transfer)[idx]).max()) for idx,mat in constraints)
    assert worst_copy < 1e-8 and len(dependent)==expected_constraints
    assert transfer[:,dependent].nnz == 0
    fixed = np.array(sorted(fixed),dtype=np.int32)
    assert not np.intersect1d(dependent,fixed).size
    free = np.setdiff1d(np.arange(len(dofs)),np.r_[dependent,fixed])
    assert len(free)==expected_free
    checks = dict(files=sources,equations=len(dofs),free=len(free),prescribed=len(fixed),
                  dependent=len(dependent),max_duplicate_constraint_coefficient_difference=worst_copy)
    return dofs,free,fixed,dependent,transfer,stiffness[free][:,free],mass[free][:,free],checks
