"""Recover the unit-cell-load reaction paths on the tangent at bolt lock.

The distributed EMAT record layout is documented in ANSYS 2026 R1 Programmer's
Reference, section 1.6. Each operator sums rows only on the named side of a cut.
"""

from collections import defaultdict

import numpy as np
from ansys.mapdl import reader
from ansys.mapdl.reader import _binary_reader
from basis_comparison import field_files
from cell_attachment_force import bodies_and_bonds, locked_pocket
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, ROOT, positions, read
from snug_mount_reactions import ring_nodes


def sections(branch, rst, deck):
    geometry = read(ROOT / "validation/cell_force" / f"{branch}.json")["geometry"]
    bodies, bonds, _ = bodies_and_bonds(rst, geometry)
    regions = defaultdict(dict)

    def add_surface(label, elements, connectivity, targets):
        selected = np.isin(connectivity, targets).any(1)
        assert selected.any() and np.isin(targets, connectivity[selected]).all()
        for element, nodes in zip(elements[selected], connectivity[selected], strict=True):
            regions[int(element)][label] = np.intersect1d(nodes, targets)

    for real, ends in bonds.items():
        material, nodes = ends[1]
        elements, ids, indices = bodies[material]
        add_surface(f"strip {real}", elements, ids[indices.reshape(-1, 10)], nodes)
    faces = []
    if branch != "bare":
        history = read(AUDIT / f"{branch}_static_contacts.json")["contact_history"][-1]
        assert history["loadstep"] == 2 and history["load_time"] == 2
        assert {row["STEP_face"] for row in history["loaded_case_faces"]} == {17}
        faces = sorted(e for row in history["loaded_case_faces"] for e in row["element_ids"])
        _, _, pocket = locked_pocket(rst, faces)
        grid = rst.grid.cell_data
        elements = np.sort(
            grid["ansys_elem_num"][
                (grid["ansys_elem_type_num"] == 187) & (grid["ansys_material_type"] == 850)
            ]
        )
        enum = rst.mesh.enum
        order = np.argsort(enum)
        raw = rst.mesh.elem
        conn = np.stack([raw[i][10:20] for i in order[positions(enum[order], elements)]])
        add_surface("PLA pocket", elements, conn, pocket)
        rings, _ = ring_nodes(deck)
        for pilot, nodes in rings.items():
            add_surface(f"mount {pilot}", elements, conn, nodes)
        for number in faces:
            native = raw[order[positions(enum[order], [number])[0]]]
            assert native[1] == 853
            regions[number][f"contact {number}"] = np.unique(native[10:18])
    return regions, bonds, faces


def element_matrices(folder, elements, hashes, *, nonzero_only=False):
    """Read symmetric stiffness, mass and stress-stiffening blocks in physical DOF order.

    A contact element can repeat a node in its local face definitions. Callers sum
    the repeated rows and columns when assembling that element.
    """
    elements = np.asarray(list(elements))
    seen = set()
    for rank in range(12):
        path = folder / f"file{rank}.emat"
        verified(path, hashes[path.name])
        header = reader.read_binary(path).header
        stream = _binary_reader.AnsysFile(str(path))
        try:
            numbers = stream.read_record(int(header["ptrElm"]))
            pointers = stream.read_record(int(header["ptrIDX"]))
            nodes = stream.read_record(int(header["ptrBAC"]))
            assert len(pointers) == 2 * len(numbers) and len(nodes) == header["lenbac"]
            for i in np.flatnonzero(np.isin(numbers, elements)):
                element = int(numbers[i])
                assert element not in seen
                seen.add(element)
                start = (int(pointers[i]) & 0xFFFFFFFF) + (int(pointers[i + len(numbers)]) << 32)
                assert 0 < start < path.stat().st_size // 4
                info, length = stream.read_record(start, True)
                start += length
                local, length = stream.read_record(start, True)
                start += length
                width = int(-info[9])
                assert width == len(local) and width > 0 and info[0] == 1
                valid = local > 0
                native = np.full(width, -1)
                component = (local - 1) % int(header["numdof"])
                native[valid] = nodes[(local[valid] - 1) // int(header["numdof"])]
                keys = 8 * native + component
                for code in range(4):
                    if not info[code]:
                        continue
                    vals, length = stream.read_record(start, True)
                    start += length
                    if code == 2:
                        continue  # static loads and undamped modes
                    entries = width * (width + 1) // 2
                    # Each stored real occupies two 32-bit words. The legacy reader may
                    # expose a view sized by words; only the declared payload is valid.
                    assert length == 2 * entries + 3 and vals.dtype == np.float64
                    assert len(vals) in (entries, 2 * entries)
                    if nonzero_only and not np.any(vals[:entries]):
                        continue
                    matrix = np.zeros((width, width))
                    matrix[np.tril_indices(width)] = vals[:entries]
                    matrix += np.tril(matrix, -1).T
                    assert np.isfinite(matrix).all()
                    if not valid.all():
                        assert abs(matrix[:, ~valid]).max() < 1e-10
                    yield element, code, keys[valid], matrix[np.ix_(valid,valid)]
        finally:
            stream.close()
    assert seen == set(elements)


def force_operators(folder, regions, hashes):
    rows = {}
    files = {f'file{rank}.emat': hashes[f'file{rank}.emat'] for rank in range(12)}
    for element, code, keys, matrix in element_matrices(folder, regions, hashes):
        native, component = np.divmod(keys,8)
        for label, targets in regions[element].items():
            use = np.isin(native, targets)
            assert np.isin(targets, native[use]).all()
            result = rows.setdefault(label, defaultdict(lambda: np.zeros((2, 3))))
            block = np.stack([matrix[use & (component == axis)].sum(0) for axis in range(3)])
            kind = 1 if code == 1 else 0
            for j, key in enumerate(keys):
                result[int(key)][kind] += block[:, j]
    keys = np.unique([k for row in rows.values() for k in row])
    assert np.all(keys % 8 < 3)
    operators = {}
    for label, row in rows.items():
        op = np.zeros((2, 3, len(keys)))
        op[:, :, positions(keys, list(row))] = np.stack(list(row.values()), axis=2)
        operators[label] = op
    return keys, operators, files


def modal_check(branch, rst, proof, keys, operators, bonds, faces):
    field = (
        field_files(proof["case"], CAMPAIGN, proof["rst_sha256"], rst.nsets) if branch != "bare" else None
    )
    ids = np.unique(keys // 8)
    modes = displacement_basis(rst, ids, field)[:, positions(ids, keys // 8), keys % 8].T
    omega2 = (2 * np.pi * rst.time_values) ** 2
    dynamic = {label: (op[0] @ modes) - (op[1] @ modes) * omega2 for label, op in operators.items()}
    audit = read(ROOT / "validation/cell_attachment" / f"{branch}.json")
    assert audit["modal_rst_sha256"] == proof["rst_sha256"]
    path = ROOT / ".runtime/post" / CAMPAIGN / proof["case"] / "attachment_modes.npz"
    verified(path, audit["shape_force_sha256"])
    errors = {}

    def check(name, actual, reference):
        err = float(np.linalg.norm(actual - reference) / np.linalg.norm(reference))
        assert err < 1e-5, (name, err)
        errors[name] = err

    with np.load(path) as cache:
        assert np.array_equal(rst.time_values, cache["frequency_Hz"])
        assert set(bonds) == set(cache["pairs"])
        for i, real in enumerate(cache["pairs"]):
            check(f"strip {real}", dynamic[f"strip {real}"], cache["force"][i])
        if faces:
            ref = cache["middle_cell_pocket_force"]
            check("PLA pocket", dynamic["PLA pocket"], ref)
            check("contact elements", -sum(dynamic[f"contact {e}"] for e in faces), ref)
    return {
        "rst_sha256": proof["rst_sha256"],
        "native_force_shapes_sha256": audit["shape_force_sha256"],
        "modes": rst.nsets,
        "relative_force_errors": errors,
    }


def recover(branch, basis, folder, rst, static, static_folder, dofs, u, compliance):
    previous = AUDIT / f"{branch}_full_board_tangent.json"
    reference = read(previous)
    assert (
        basis["rst_sha256"] == reference["basis_rst_sha256"]
        and static["rst_sha256"] == reference["static_rst_sha256"]
    )
    assert np.allclose(compliance, reference["cell_X_um_per_N"], rtol=1e-8, atol=1e-9)
    manifest = read(ROOT / ".runtime/receipts" / CAMPAIGN / basis["case"] / "archived.json")
    parent = read(ROOT / ".runtime/receipts" / CAMPAIGN / static["case"] / "archived.json")
    deck = static_folder / "model.inp"
    verified(deck, next(r["sha256"] for r in parent["files"] if r["name"] == deck.name))
    regions, bonds, faces = sections(branch, rst, deck.read_text())
    keys, ops, files = force_operators(folder, regions, {r["name"]: r["sha256"] for r in manifest["files"]})
    checks = modal_check(branch, rst, basis, keys, ops, bonds, faces)
    axis = dofs[:, 0].astype(np.int64) * 8 + dofs[:, 1]
    order = np.argsort(axis)
    field = u[order[positions(axis[order], keys)]]
    result = {label: op[0] @ field for label, op in ops.items()}
    cell_residual = []
    records = []
    zero = np.zeros((3, 3))
    pocket = result.get("PLA pocket", zero)
    for i, cell in enumerate(BODIES):
        pairs = sorted(k for k, v in bonds.items() if v[0][0] == cell)
        assert len(pairs) == 2
        nickel = sum(result[f"strip {k}"] for k in pairs)
        case_force = pocket if cell == BODIES[1] else zero
        applied = zero.copy()
        applied[0, i] = 1.0
        cell_residual.append(float(abs(nickel + case_force - applied).max()))
        records.append(
            {
                "material": cell,
                "bond_pairs": pairs,
                "strip_XYZ_N_per_N": nickel.tolist(),
                "case_XYZ_N_per_N": case_force.tolist(),
            }
        )
    # The contact-element reaction and the four mounting reactions independently close the case balance.
    contact = sum((result[f"contact {e}"] for e in faces), zero.copy())
    mounts = sum((v for k, v in result.items() if k.startswith("mount ")), zero.copy())
    closure = {
        "each_cell": cell_residual,
        "pocket_against_contact_elements": float(abs(pocket + contact).max()),
        "pocket_against_four_mounts": float(abs(pocket + mounts).max()),
    }
    assert (
        max(cell_residual) < 1e-6
        and max(closure[k] for k in ("pocket_against_contact_elements", "pocket_against_four_mounts"))
        < 1e-6
    ), closure
    out = {
        "case": basis["case"],
        "branch": branch,
        "full_tangent_sha256": digest(previous),
        "elements": len(regions),
        "emat_sha256": files,
        "modal_check": checks,
        "closure_N_per_N": closure,
        "load_order": ["left", "middle", "right"],
        "installed_contact_elements": faces,
        "cell_load_paths": records,
        "element_group_XYZ_N_per_N": {k: v.tolist() for k, v in result.items()},
        "scope": "Increment from bolt lock per unit PCB-X load on each cell, with installed contact held fixed. "
        "Positive X in a strip or PLA pocket is force carried from cell into that part. Mount rows use force on the shell.",
    }
    write_json(AUDIT / f"{branch}_initial_cell_load_paths.json", out)
    print(branch, "middle case share", pocket[0, 1], "closure", closure, flush=True)
