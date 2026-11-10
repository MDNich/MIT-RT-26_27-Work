"""Apply native cylindrical contact geometry correction to the middle pocket and middle cell."""

import hashlib

import numpy as np
from case_stress import source
from early_cell_clearance import outer_faces
from film_identity import digest, verified, write_json
from installed_cell_gap import target_connectivity
from snug_board_pull import CAMPAIGN, positions, read
from snug_locked_contact import surface_owners
from snug_unilateral_geometry import REFERENCE, exact_faces
from stage_local_jobs import seal
from stage_snug_fit import AUDIT, INPUTS, MESH, STEP, STEP_HASH, input_record

CASE = "snug125_aluminium_cylinder_static"
MANIFEST = AUDIT / "aluminium_cylinder_input.json"


def id_hash(numbers):
    return hashlib.sha256(np.array(sorted(numbers), "<i8").tobytes()).hexdigest()


def corrected_groups(rst, proof, ref):
    xyz = rst.mesh.nodes * 1000
    origin = np.array(proof["chart_origin_mm"])
    axes = np.array(proof["chart_axes"])
    owners = surface_owners(rst, MESH / "case_2.npz")
    cap_ids = np.array(sorted(e for e, tag in owners.items() if tag == owners[proof["case_faces"][0]]))
    assert set(proof["case_faces"]) <= set(cap_ids)
    cap = exact_faces(rst, cap_ids)
    middle = set(map(tuple, np.sort(outer_faces(rst, [191]), axis=1)))
    targets = target_connectivity(rst)
    cell_ids = np.array(
        sorted(
            e
            for e, n in targets.items()
            if n[2] == n[3] and tuple(sorted(n[i] for i in (0, 1, 2, 4, 5, 7))) in middle
        )
    )
    cell = exact_faces(rst, cell_ids)
    assert len(cell) == proof["target_face_count"]
    assert proof["registered_CAD"]["native_step_sha256"] == ref["step_sha256"]
    for k, (numbers, faces, cylinder) in enumerate(
        zip((cap_ids, cell_ids), (cap, cell), proof["registered_CAD"]["cylinders"], strict=True)
    ):
        tv = np.array(cylinder["cylinder_axes_in_chart"])
        centre = np.array(cylinder["centre_t_v_mm"])
        radius = cylinder["radius_mm"]
        loc = ((xyz[positions(rst.mesh.nnum, faces)] - origin) @ axes) @ tv - centre
        deviations = abs(np.linalg.norm(loc, axis=2) - radius)
        select = deviations.max(1) < 2e-6
        if k == 0:
            assert select.all()
        else:
            assert select.any() and not select.all()
        group = numbers[select]
        nodes = np.unique(faces[select])
        kind = 853 - k
        all_type = rst.grid.cell_data["ansys_elem_num"][rst.grid.cell_data["ansys_etype"] == kind]
        order = np.argsort(rst.mesh.enum)
        selected = [
            int(e)
            for e, i in zip(all_type, order[positions(rst.mesh.enum[order], all_type)], strict=True)
            if np.isin(rst.mesh.elem[i][10:18], nodes).all()
        ]
        assert set(selected) == set(group)
        ctr = origin + (tv @ centre) @ axes.T
        direction = axes @ np.array(cylinder["axial_direction_in_chart"])
        ends = (ctr[None, :] + np.array([[-50.0], [50.0]]) * direction) * 1e-3
        yield (
            nodes,
            {
                "section": 8861 + k,
                "type": kind,
                "faces": len(group),
                "element_ids_sha256": id_hash(group),
                "node_ids_sha256": id_hash(nodes),
                "axis_points_m": ends.tolist(),
                "max_node_radial_error_mm": float(deviations[select].max()),
            },
        )


def stage():
    verified(STEP, STEP_HASH)
    ref = input_record(REFERENCE)
    depth_path = AUDIT / "aluminium_curved_pocket_depth.json"
    depth = read(depth_path)
    orig, _, rst = source("snug125_aluminium_static", CAMPAIGN)
    assert orig["rst_sha256"] == depth["static_rst_sha256"]
    folder = INPUTS / REFERENCE
    verified(folder / "model.inp", ref["input_sha256"])
    post = folder / "snug_force_post.inp"
    verified(post, ref["post_sha256"])
    raw = (folder / "model.inp").read_bytes()
    anchor = b"CM,CASECONTACT,ELEM\r\nALLSEL,ALL\r\n"
    assert raw.count(anchor) == 1
    lines = []
    groups = []
    for nodes, g in corrected_groups(rst, depth, ref):
        section = g["section"]
        name = f"CYLN{section}"
        assert f"SECTYPE,{section},".encode() not in raw.upper()
        lines.extend(
            [
                f"SECTYPE,{section},CONTACT,CYLINDER",
                "SECDATA," + ",".join(f"{v:.15g}" for endpoint in g["axis_points_m"] for v in endpoint),
                f"CMBLOCK,{name},NODE,{len(nodes)}",
                "(8i10)",
            ]
        )
        lines.extend("".join(f"{int(n):10d}" for n in nodes[i : i + 8]) for i in range(0, len(nodes), 8))
        lines.extend(
            [
                f"CMSEL,S,{name}",
                "ESLN,S,1",
                f"ESEL,R,TYPE,,{g['type']}",
                "*GET,NCYL,ELEM,0,COUNT",
                f"*IF,NCYL,NE,{g['faces']},THEN",
                "/COM,Incorrect cylindrical face selection",
                "/EXIT,NOSAVE",
                "*ENDIF",
                f"EMODIF,ALL,SECN,{section}",
                "ALLSEL,ALL",
            ]
        )
        groups.append(g)
    extra = ("\r\n".join(lines) + "\r\n").encode("ascii")
    candidate = raw.replace(anchor, anchor + extra)
    assert candidate.replace(extra, b"") == raw
    dst = INPUTS / CASE
    dst.mkdir(exist_ok=True)
    entry = dict(
        ref,
        case=CASE,
        reference_case=REFERENCE,
        reference_input_sha256=ref["input_sha256"],
        input_sha256=seal(dst / "model.inp", candidate),
        post_sha256=seal(dst / post.name, post.read_bytes()),
        depth_audit_sha256=digest(depth_path),
        groups=groups,
        detection_keyopt_4=0,
    )
    write_json(MANIFEST, entry)


def audit_sections(case, campaign):
    entry = input_record(case)
    assert case == entry["case"]
    assert entry['groups'] == read(MANIFEST)['groups']
    _, _, rst = source(case, campaign)
    for g in entry["groups"]:
        elements = [int(e[8]) for e in rst.mesh.elem if e[3] == g["section"]]
        assert len(elements) == g["faces"] and id_hash(elements) == g["element_ids_sha256"]
    return entry["groups"]


def stage_tolerance():
    from stage_snug_contact_refinement import tolerance_input
    seats = AUDIT / (CASE + '_seats.json')
    verdict = read(seats)
    assert verdict['case'] == CASE and not verdict['states'][-1]['within_force_screens']
    candidate = 'snug125_aluminium_cylinder_tol0001_static'
    entry = tolerance_input(CASE, candidate, absolute_force_criterion_N=0.0001)
    entry.update(reference_bearing_sha256=digest(seats),
        reason='The original final pocket/tab vector discrepancy was 22.1% of the pocket resultant. '
               'A 0.0001 N absolute L2 criterion tests convergence below the millinewton scale. '
               'All original independent force screens still apply.',
        scheduled='At the next audited serial case boundary; do not interrupt the active local pull.')
    write_json(AUDIT / 'aluminium_cylinder_tolerance_input.json', entry)


if __name__ == "__main__":
    stage()
