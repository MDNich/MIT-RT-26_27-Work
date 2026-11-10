"""Stage the driven-cell target refinement on the existing increment-controlled pull, through +0.040 mm."""

import json

import numpy as np
from audit_local import read
from film_identity import digest, verified, write_json
from snug_pull_resolution import GEOMETRY_CASE
from snug_pull_steps import CASE as PARENT
from snug_pull_steps import REGISTRY as PARENT_REGISTRY
from snug_pull_target_geometry import generated_skin
from stage_local_jobs import seal
from stage_snug_fit import AUDIT, INPUTS, MESH

REGISTRY = AUDIT / "local_target_control.json"


def rigid_triangles(data):
    faces = data["4"]
    xyz = data["points"]
    nodes = np.unique(faces)
    assert nodes.min() >= 0 and 1600000 + nodes.max() < 1800000
    lines = [f"N,{1600000 + i}," + ",".join(f"{x:.9g}" for x in xyz[i]) for i in nodes]
    lines.append("TSHAP,TRIA")
    lines.extend("E," + ",".join(map(str, 1600000 + f)) for f in faces)
    return ("\n".join(lines) + "\n").encode()


def stage():
    geometry_path = AUDIT / "moving_cell_target_resolution.json"
    geometry = read(geometry_path)
    info = read(PARENT_REGISTRY)[PARENT]
    assert geometry["case"] == info["parent"]
    parent = INPUTS / PARENT
    verified(parent / "local_job.json", info["spec_sha256"])
    job = read(parent / "local_job.json")
    for name, sha in job["files"].items():
        verified(parent / name, sha)
    deck = (parent / "model.inp").read_bytes()
    assert digest(parent / "model.inp") == info["input_sha256"]
    original_path = MESH / "fixture_targets_0005.npz"
    verified(original_path, geometry["cell_skins"]["native"]["skin_sha256"])
    assert digest(original_path) == info["target_sha256"]
    finer = geometry["cell_skins"]["finer"]
    finer_path = generated_skin(
        "finer", (finer["linear_deflection_mm"], finer["angular_deflection_rad"]), expected=finer["skin_sha256"]
    )
    with np.load(original_path) as data:
        old = rigid_triangles(data)
    with np.load(finer_path) as data:
        new = rigid_triangles(data)
    start = b"TYPE,861\nREAL,861\nTSHAP,PILO\nE,2481\n"
    end = b"TSHAP\nALLSEL,ALL\nESEL,S,TYPE,,850\n"
    assert deck.count(start + old + end) == 1
    first, after = deck.split(start + old, 1)
    assert after.startswith(end) and b"REAL,862\nTSHAP,PILO\nE,959001" in after
    last = b"D,2481,UX,0.04\nSOLVE\n"
    finish = b"FINISH\nSAVE,solved,db\n"
    assert after.count(last) == after.count(finish) == 1
    middle, tail = after.split(last)
    later, post = tail.split(finish)
    # Only discard the eight complete later displacement increments after the common +0.04 mm endpoint.
    retained = [s for s in info["steps"] if s["travel_mm"] <= 0.04]
    assert len(retained) == 5 and retained[-1]["travel_mm"] == 0.04
    omitted = []
    for step in info["steps"][len(retained) :]:
        x = step["travel_mm"]
        n = step["subdivisions"]
        omitted.extend(
            [f"TIME,{2 + 2 * x:.12g}", f"NSUBST,{n},{max(2 * n, 64)},{n}", f"D,2481,UX,{x:.12g}", "SOLVE"]
        )
    assert later == ("\n".join(omitted) + "\n").encode()
    fresh = first + start + new + middle + last + finish + post
    assert (
        fresh.replace(start + new + end, start + old + end).replace(last + finish, last + later + finish) == deck
    )
    dst = INPUTS / GEOMETRY_CASE
    dst.mkdir(exist_ok=True)
    files = {"model.inp": seal(dst / "model.inp", fresh)}
    for name in ("local_post.inp", "moving.inp"):
        files[name] = seal(dst / name, (parent / name).read_bytes())
    selected = dict(
        job, case=GEOMETRY_CASE, snug_target_parent=PARENT, end_time=2.08, displacement_mm=0.04, files=files
    )
    spec_sha = seal(dst / "local_job.json", (json.dumps(selected, indent=2) + "\n").encode())
    write_json(
        REGISTRY,
        {
            GEOMETRY_CASE: {
                "case": GEOMETRY_CASE,
                "parent": PARENT,
                "geometry_audit_sha256": digest(geometry_path),
                "parent_input_sha256": info["input_sha256"],
                "mesh_sha256": info["mesh_sha256"],
                "spec_sha256": spec_sha,
                "input_sha256": files["model.inp"],
                "bare_reference": info["bare_reference"],
                "steps": retained,
                "moving_cell_skins": {key: geometry["cell_skins"][key] for key in ("native", "finer")},
                "fixed_hardware_skin_sha256": info["target_sha256"],
                "cores": job["cores"],
                "scope": "Same clamp and lock, 1.5 mm PLA mesh, fixed neighbours, four-core SMP and displacement "
                "increments as the matched time-step control through +0.040 mm. Only the driven rigid cell "
                "changes from 8,856 to 35,162 target triangles.",
            }
        },
    )


if __name__ == "__main__":
    stage()
