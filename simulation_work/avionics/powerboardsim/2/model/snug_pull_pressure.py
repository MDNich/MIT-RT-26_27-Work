"""Audit native cell contact pressures and loaded areas during the snug forward pull."""

from hashlib import sha256

import numpy as np
from ansys.mapdl import reader
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS
from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_directional_result import refined_tab_crossing
from snug_local_checkpoint import CASE
from snug_pocket_faces import BARYCENTRIC, SIX, at_integration_points
from snug_pocket_sampling import shape
from stage_snug_fit import AUDIT, MESH

_, DU, DV = shape(BARYCENTRIC[:, :2])
EMS, ENF, EMN = (ELEMENT_INDEX_TABLE_KEYS.index(tag) for tag in ("EMS", "ENF", "EMN"))


def target_owners(raw, skin_path):
    """Match each rigid target triangle to the exact connectivity of the sealed STEP-body skin."""
    owners = {}
    with np.load(skin_path) as skin:
        for pair, shift, bodies in [
            (861, 1600000, [4]),
            (862, 1800000, [15, 19, 1, 6, 9, 10, 11, 20]),
        ]:
            triangles = {}
            for body in bodies:
                faces = skin[str(body)]
                xyz = raw.mesh.nodes[positions(raw.mesh.nnum, faces.ravel() + shift)]
                np.testing.assert_allclose(xyz, skin["points"][faces.ravel()], rtol=0, atol=1e-6)
                for face in np.sort(faces + shift, axis=1):
                    key = tuple(face)
                    assert key not in triangles
                    triangles[key] = body
            for element in raw.mesh.elem:
                if element[1] == 861 and element[2] == pair and element[12] > 0:
                    owners[int(element[8])] = triangles.pop(tuple(sorted(element[10:13])))
            assert not triangles
    return owners


def dpf_fields(folder, sha):
    request, done = (read(folder / f"{name}.json") for name in ("request", "done"))
    nodes = np.array(request["nodes"])
    assert request["source_sha256"] == done["source_sha256"] == sha
    assert request["sets"] == done["sets"] and len(nodes) == done["nodes"] and done["unit"] == "mm"
    np.testing.assert_array_equal(nodes, np.unique(nodes))
    values = np.fromfile(folder / "displacements.bin", dtype="<f8").reshape(-1, len(nodes), 3)
    return nodes, dict(zip(done["sets"], values, strict=True))


def audit_face(native, stress, forces, xyz):
    """Reconstruct the three pressure samples from independent ENF virtual work and deformed area."""
    status = native[:3] >= 2
    pressure = stress[:3].astype(float)
    assert np.array_equal(status, pressure > 0) and status.any() and len(forces) == 30
    slots = forces[:24].reshape(8, 3).astype(float)
    six = slots[SIX].copy()
    six[2] += slots[[3, 6]].sum(0)
    loads, residual = at_integration_points(six)
    areas = np.linalg.norm(np.cross(DU @ xyz, DV @ xyz), axis=1) / 6
    assert areas.min() > 0
    area = float(native[57])
    pressure_error = float(np.max(abs(np.linalg.norm(loads, axis=1) / areas - pressure)))
    area_error = abs(areas[status].sum() - area)
    np.testing.assert_allclose(-loads.sum(0), native[42:45], rtol=2e-6, atol=1e-6)
    assert pressure_error < 5e-7 * max(1, pressure.max()) and area_error < 2e-7 * area
    return {
        "area": area,
        "normal": float(pressure @ areas),
        "peak": float(pressure.max()),
        "points": int(status.sum()),
        "force": native[42:45].astype(float),
        "pressure_error_MPa": pressure_error,
        "relative_area_error": float(area_error / area),
        "virtual_work_relative_error": residual,
    }


def summarize(faces):
    area = sum(f["area"] for f in faces)
    force = sum(f["normal"] for f in faces)
    return {
        "loaded_faces": len(faces),
        "loaded_points": sum(f["points"] for f in faces),
        "contact_area_mm2": area,
        "normal_load_N": force,
        "mean_pressure_MPa": force / area,
        "peak_pressure_MPa": max(f["peak"] for f in faces),
        "reaction_XYZ_N": np.sum([f["force"] for f in faces], axis=0).tolist(),
    }


def contact_index(raw):
    elements = sorted(
        (e for e in raw.mesh.elem if e[1] == 862 and e[2] in (861, 862)),
        key=lambda e: e[8],
    )
    order = np.argsort(raw._eeqv)
    return elements, order[positions(raw._eeqv[order], [e[8] for e in elements])]


def loaded_faces(raw, index, native_set, signature):
    elements, rows = index
    offsets, _, start = raw._element_solution_header(native_set - 1)
    for e, delta in zip(elements, offsets[rows], strict=True):
        if delta <= 0:
            continue
        record = int(start + delta)
        slots = raw.read_record(record)
        if slots[EMN] <= 0:
            continue
        native = raw.read_record(record + int(slots[EMN]))
        if not np.any(native[:3] >= 2):
            assert native[57] == 0 and np.max(abs(native[42:45])) < 1e-8
            continue
        assert slots[EMS] > 0 and slots[ENF] > 0
        stress, forces = (raw.read_record(record + int(slots[i])) for i in (EMS, ENF))
        packed = np.r_[
            e[8],
            e[2],
            e[10:18],
            native[:3],
            native[42:48],
            native[57],
            stress[:3],
            forces,
        ]
        signature.update(packed.astype("<f8").tobytes())
        yield e, native, stress, forces


def verify_saved_records(source, expected_sha, states):
    verified(source, expected_sha)
    raw = reader.read_binary(source)
    index = contact_index(raw)
    for row in states:
        signature = sha256()
        for _ in loaded_faces(raw, index, row["native_set"], signature):
            pass
        assert signature.hexdigest() == row["native_pressure_records_sha256"]


def run(folder):
    base = f"{CASE}_{folder.name}"
    checkpoint = AUDIT / f"{base}_checkpoint.json"
    fixed_path = AUDIT / f"{base}_fixed_targets.json"
    local_path = AUDIT / "nylon_forward_tab_submodel.json"
    c, fixed, local = map(read, (checkpoint, fixed_path, local_path))
    assert fixed["checkpoint_sha256"] == digest(checkpoint) and local["input_sha256"] == c["input_sha256"]
    later = AUDIT / f"{CASE}_{local['checkpoint']}_checkpoint.json"
    verified(later, local["checkpoint_sha256"])
    assert read(later)["states"][: len(c["states"])] == c["states"]
    first_above = refined_tab_crossing(
        CASE, c["input_sha256"], {r["native_set"]: r["travel_mm"] for r in c["states"]}
    )["native_set"]
    fixed_reference = {r["native_set"]: r["possible_target_bodies"] for r in fixed["loaded_states"]}
    verified(folder / "pull.rst", c["rst_sha256"])
    skin_path = MESH / "fixture_targets_0005.npz"
    verified(skin_path, fixed["skin_sha256"])
    verified(folder / "dpf_fixed_faces/displacements.bin", fixed["DPF_displacements_sha256"])
    raw = reader.read_binary(folder / "pull.rst")
    owners = target_owners(raw, skin_path)
    index = contact_index(raw)
    fields = {
        pair: dpf_fields(folder / name, c["rst_sha256"])
        for pair, name in [(861, "dpf_points"), (862, "dpf_fixed_faces")]
    }
    errors = dict.fromkeys(
        ("pressure_error_MPa", "relative_area_error", "virtual_work_relative_error"),
        0.0,
    )
    states = []
    for row in c["states"]:
        k = row["native_set"]
        if k >= first_above or not row["within_screens"]:
            break
        if row["loadstep"] != 3:
            continue
        grouped = {}
        signature = sha256()
        for e, native, stress, forces in loaded_faces(raw, index, k, signature):
            pair = e[2]
            nodes, field = fields[pair]
            face = e[10:18]
            assert face[2] == face[3] == face[6]
            xyz = raw.mesh.nodes[positions(raw.mesh.nnum, face[SIX])] + field[k][positions(nodes, face[SIX])]
            f = audit_face(native, stress, forces, xyz)
            # Target IDs in single-precision records are exact integers throughout this fixture.
            targets = native[45:48][native[:3] >= 2]
            assert np.all((targets > 0) & (targets < 2**24) & (targets == targets.astype(int)))
            bodies = {owners[int(i)] for i in targets}
            assert len(bodies) == 1
            body = bodies.pop()
            assert (body == 4) == (pair == 861)
            grouped.setdefault(str(body), []).append(f)
            for key in errors:
                errors[key] = max(errors[key], f[key])
        cells = {key: summarize(f) for key, f in sorted(grouped.items())}
        reference = fixed_reference.get(k, {})
        assert set(cells) - {"4"} == set(reference)
        for key, data in reference.items():
            assert cells[key]["loaded_faces"] == data["faces"]
            np.testing.assert_allclose(cells[key]["reaction_XYZ_N"], data["force_N"], rtol=1e-7, atol=1e-7)
        for pair in (861, 862):
            members = [g for key, g in cells.items() if (key == "4") == (pair == 861)]
            expected = row["both_contact_pairs"][str(pair)]
            assert sum(g["loaded_faces"] for g in members) == expected["closed_faces"]
            force = sum((np.array(g["reaction_XYZ_N"]) for g in members), np.zeros(3))
            np.testing.assert_allclose(force, expected["force_N"], rtol=1e-6, atol=1e-6)
        states.append(
            {
                "native_set": k,
                "travel_mm": row["travel_mm"],
                "actuator_N": row["cell_force_N"],
                "cells": cells,
                "native_pressure_records_sha256": signature.hexdigest(),
            }
        )
    assert states and states[-1]["native_set"] == first_above - 1
    later_sha = read(later)["rst_sha256"]
    verify_saved_records(folder.parent / local["checkpoint"] / "pull.rst", later_sha, states)
    result = {
        "case": CASE,
        "later_rst_crosscheck_sha256": later_sha,
        "rst_sha256": c["rst_sha256"],
        "checkpoint_sha256": digest(checkpoint),
        "fixed_body_check_sha256": digest(fixed_path),
        "refined_tab_check_sha256": digest(local_path),
        "field_hashes": {n: digest(folder / n / "displacements.bin") for n in ("dpf_points", "dpf_fixed_faces")},
        "bodies": {
            "4": "driven left cell",
            "19": "fixed middle cell",
            "15": "fixed right cell",
        },
        "largest_face_errors": errors,
        "states": states,
        "scope": "Native frictionless quadrature on a 1.5 mm PLA mesh against rigid battery surfaces. "
        "Mean pressure is total normal load divided by the native loaded area. Peak is the largest "
        "saved quadrature pressure. States stop before the first refined PLA coupon crossing.",
    }
    write_json(AUDIT / f"{base}_cell_pressure.json", result)
    print(errors)
    for state in states:
        print(
            state["native_set"],
            {
                b: (
                    round(d["contact_area_mm2"], 3),
                    round(d["mean_pressure_MPa"], 3),
                    round(d["peak_pressure_MPa"], 3),
                )
                for b, d in state["cells"].items()
            },
        )


if __name__ == "__main__":
    run(ROOT / ".runtime/qa/snug125/forward-readback/ls3_ss18")
