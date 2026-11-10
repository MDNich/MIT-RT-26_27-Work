"""Check the active and neighbouring middle-pocket faces through the first unloading cycle."""

import numpy as np
from basis_comparison import field_files
from case_stress import source
from dpf_readback import export
from early_cell_clearance import bezier, outer_faces, subdivision_weights
from film_identity import digest, verified, write_json
from global_contact import pair_summary
from motion_surface import displacement_basis
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, positions, read
from snug_pocket_dynamics import BASIS_PROOF, BRANCH, OUTPUT, STUDY
from snug_pocket_release import certify_pair, witness_elements


def exact_faces(rst, element_ids):
    numbers = rst.mesh.enum
    order = np.argsort(numbers)
    raw = np.stack([rst.mesh.elem[i][10:18] for i in order[positions(numbers[order], element_ids)]])
    assert (raw[:, 2] == raw[:, 3]).all() and (raw[:, 2] == raw[:, 6]).all()
    return raw[:, [0, 1, 2, 4, 5, 7]]


def compare(case, cell, faces, weights):
    checks = {}
    for label, face in faces.items():
        checks[label] = certify_pair(face, cell, weights)
    if any(row["state"] == "intersecting" for row in checks.values()):
        checks["whole_middle"] = {
            "state": "intersecting",
            "witnessed_on": [key for key, v in checks.items() if v["state"] == "intersecting"],
        }
    else:
        checks["whole_middle"] = certify_pair(case, cell, weights)
    return checks


def static_check(case, reference_face, adjacent, weights):
    proof, _, rst = source(case, CAMPAIGN)
    numbers = [reference_face, adjacent["case_contact_element"], adjacent["cell_target_element"]]
    faces = exact_faces(rst, numbers)
    nodes, indices = np.unique(faces, return_inverse=True)
    indices = indices.reshape(faces.shape)
    xyz = rst.mesh.nodes[positions(rst.mesh.nnum, nodes)]

    def check(x):
        return certify_pair(bezier(x[indices[1:2]]), bezier(x[indices[2:3]]), weights)

    rows = []
    fields = export(case, CAMPAIGN, list(range(1, rst.nsets + 1)))
    for k, time in enumerate(rst.time_values):
        stem = fields / f"set_{k + 1:04d}"
        ids = np.fromfile(stem.with_suffix(".ids"), "<i4")
        order = np.argsort(ids)
        u = np.fromfile(stem.with_suffix(".u"), "<f8").reshape(-1, 3)[
            order[positions(ids[order], nodes)]
        ]
        enum, records, n = rst.element_solution_data(k, "ECT")
        direct = {
            key: pair_summary(k, time, np.array([element]), enum, records, n)
            for key, element in zip(("original", "adjacent"), numbers[:2], strict=True)
        }
        rows.append(
            {
                "native_set": k + 1,
                "load_time": float(time),
                "adjacent_quadratic_pair": check(1000 * (xyz + u)),
                "native_contact": direct,
                "displacements_sha256": digest(stem.with_suffix(".u")),
                "ids_sha256": digest(stem.with_suffix(".ids")),
            }
        )
    return {
        "case": case,
        "static_rst_sha256": proof["rst_sha256"],
        "initial_pair": check(1000 * xyz),
        "stations": rows,
    }


def run():
    study = read(STUDY)
    release = read(AUDIT / (BRANCH + "_released_pocket_tangent.json"))
    basis = read(BASIS_PROOF)
    verified(BASIS_PROOF, study["basis_audit_sha256"])
    (closed,) = release["nonzero_contact_elements"]
    previous = release["single_contact_prediction"]["curved_cell_surfaces"]["middle_surface_transition"][
        "tests"
    ]
    witness = next(row["whole_shell"]["witness"] for row in previous if "witness" in row["whole_shell"])
    adjacent = {k: witness[k] for k in ("case_contact_element", "cell_target_element")}
    assert closed != adjacent["case_contact_element"]
    proof, _, rst = source(BRANCH + "_basis", CAMPAIGN)
    assert proof["rst_sha256"] == basis["modal_rst_sha256"] == release["modal_rst_sha256"]
    physical = [outer_faces(rst, [m]) for m in (850, *BODIES)]
    named = exact_faces(rst, [closed, adjacent["case_contact_element"], adjacent["cell_target_element"]])
    np.testing.assert_equal(witness_elements(rst, named[1], named[2]), adjacent)
    path = OUTPUT / "reduction.npz"
    verified(path, basis["basis_sha256"])
    with np.load(path) as saved:
        ids = saved["nodes"]
        extra = saved["fields"]
    np.testing.assert_array_equal(ids, np.unique(np.concatenate([s.ravel() for s in physical])))
    shapes = displacement_basis(
        rst, ids, field_files(proof["case"], CAMPAIGN, proof["rst_sha256"], rst.nsets)
    )
    xyz = rst.mesh.nodes[positions(rst.mesh.nnum, ids)]
    face_idx = [positions(ids, rows) for rows in physical]
    subset = positions(ids, named)
    weights = subdivision_weights()
    states = {}
    for axis, data in study["axes"].items():
        series = OUTPUT / f"{axis}_response.npz"
        verified(series, data["history_sha256"])
        with np.load(series) as sim:
            selected = sim["selected"]
            fields = 1000 * (
                xyz
                + np.tensordot(sim["selected_q"], shapes, axes=(1, 0))
                + np.einsum("nca,ta->tnc", extra, sim["selected_residual"])
            )
            t = sim["time_s"][selected]
        rows = []
        for label, time, x in zip(
            ("first_open_sample", "peak_spring_opening", "first_reclosed_sample"), t, fields, strict=True
        ):
            case, left, cell, right = [bezier(x[s]) for s in face_idx]
            a, neighbour, target = bezier(x[subset])
            checks = compare(case, cell, {"original_face": a[None]}, weights)
            checks["registered_adjacent_pair"] = certify_pair(neighbour[None], target[None], weights)
            checks["left_cell"] = certify_pair(case, left, weights)
            checks["right_cell"] = certify_pair(case, right, weights)
            rows.append({"station": label, "time_s": float(time), "surfaces": checks})
        states[axis] = rows
        print(
            axis,
            [
                (
                    r["station"],
                    r["surfaces"]["original_face"]["state"],
                    r["surfaces"]["registered_adjacent_pair"]["state"],
                )
                for r in rows
            ],
            flush=True,
        )
    sta = static_check(BRANCH + "_static", closed, adjacent, weights)
    write_json(
        AUDIT / "aluminium_unilateral_surfaces.json",
        {
            "branch": BRANCH,
            "startup_sha256": digest(STUDY),
            "release_sha256": digest(AUDIT / (BRANCH + "_released_pocket_tangent.json")),
            "basis_sha256": digest(BASIS_PROOF),
            "original_contact_element": closed,
            "adjacent_pair": adjacent,
            "static": sta,
            "axes": states,
            "scope": "Quadratic surface checks at selected finite-element poses. A shared interior point with nonparallel normals "
            "confirms an intersection and disjoint subdivided Bernstein hulls establish separation. A crossing alone gives no force.",
        },
    )


PROJECTED = BRANCH + "_project3_static"
REFERENCE = BRANCH + "_out2_static"
SURFACES = AUDIT / "aluminium_unilateral_surfaces.json"
PROJECTION_INPUT = AUDIT / "aluminium_projection_input.json"


def stage_projection():
    from stage_local_jobs import seal
    from stage_snug_fit import INPUTS, STEP, STEP_HASH, input_record

    proof = read(SURFACES)
    locked = proof["static"]["stations"][-1]
    assert locked["adjacent_quadratic_pair"]["state"] == "intersecting"
    assert locked["native_contact"]["adjacent"]["p_max"] == 0
    ref = input_record(REFERENCE)
    assert ref["step_sha256"] == STEP_HASH and ref["case"] == REFERENCE
    assert ref["tab_spacing_mm"] == 1.25 and ref["material"] == "aluminium" and ref["size_mm"] == 2
    verified(STEP, STEP_HASH)
    folder = INPUTS / REFERENCE
    verified(folder / "model.inp", ref["input_sha256"])
    post = folder / "snug_force_post.inp"
    verified(post, ref["post_sha256"])
    data = (folder / "model.inp").read_bytes()
    anchor = b"ET,853,CONTA174\r\n"
    change = b"KEYOPT,853,4,3\r\n"
    assert data.count(anchor) == 1 and b"KEYOPT,853,4," not in data.upper()
    candidate = data.replace(anchor, anchor + change)
    assert candidate.replace(change, b"") == data
    out = INPUTS / PROJECTED
    out.mkdir(exist_ok=True)
    entry = dict(
        ref,
        case=PROJECTED,
        reference_case=REFERENCE,
        reference_input_sha256=ref["input_sha256"],
        input_sha256=seal(out / "model.inp", candidate),
        post_sha256=seal(out / post.name, post.read_bytes()),
        detection_keyopt_4=3,
        witness_geometry_sha256=digest(SURFACES),
    )
    write_json(PROJECTION_INPUT, entry)


def audit_projection(campaign):
    import re

    from snug_board_pull import ROOT
    from stage_snug_fit import input_record

    assert campaign == CAMPAIGN
    entry = input_record(PROJECTED)
    verified(SURFACES, entry["witness_geometry_sha256"])
    ref = input_record(REFERENCE)
    assert (
        entry["reference_input_sha256"] == ref["input_sha256"]
        and entry["mesh_sha256"] == ref["mesh_sha256"]
    )
    proof = read(SURFACES)
    rows = {}
    for name, detection in (
        (REFERENCE, "Gauss integration point"),
        (PROJECTED, "nodal point (surface projection based)"),
    ):
        listing = ROOT / ".runtime/archive" / campaign / name / "solve.out"
        residuals = read(AUDIT / (name + "_residuals.json"))
        verified(listing, residuals["listing_sha256"])
        text = listing.read_text(errors="replace")
        assert re.search(
            r"contact element type 853 has been set up\.[^*]{0,550}?Contact detection at:\s*"
            + re.escape(detection),
            text,
            re.IGNORECASE,
        )
        contact = read(AUDIT / (name + "_contacts.json"))
        equilibrium = read(AUDIT / (name + "_installed.json"))
        geometry = static_check(
            name, proof["original_contact_element"], proof["adjacent_pair"], subdivision_weights()
        )
        assert (
            geometry["static_rst_sha256"]
            == contact["rst_sha256"]
            == equilibrium["rst_sha256"]
            == residuals["rst_sha256"]
        )
        rows[name] = {
            "detection": detection,
            "geometry": geometry,
            "locked_force": contact["resultant_force_check"][-1],
            "locked_faces": contact["contact_history"][-1]["loaded_case_faces"],
            "locked_bolts_N": equilibrium["locked_bolt_forces_N"],
            "locked_residual": residuals["states"][-1],
        }
    write_json(
        AUDIT / "aluminium_projection_comparison.json",
        {
            "input_audit_sha256": digest(PROJECTION_INPUT),
            "adjacent": proof["adjacent_pair"],
            "cases": rows,
        },
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", action="store_true", help="Seal the matched nodal-projection preload control"
    )
    if parser.parse_args().stage:
        stage_projection()
    else:
        run()
