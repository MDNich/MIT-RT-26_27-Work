"""Integrate the distributed side-load work over the native complete-board loading and unloading path."""

import re

import numpy as np
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, read


def audit(branch):
    name = branch + "_cellpush_x"
    proof_path = AUDIT / (name + ".json")
    proof = read(proof_path)
    folder = ROOT / ".runtime/archive" / CAMPAIGN / name
    deck = folder / "model.inp"
    verified(deck, proof["input_sha256"])
    steps = re.findall(r"(?ims)^TIME,([3456])\s*\n(.*?)^SOLVE\s*$", deck.read_text())
    assert [int(k) for k, _ in steps] == [3, 4, 5, 6]
    forces = []
    loaded = None
    for k, block in steps[1:]:
        cards = re.findall(r"(?im)^F,(\d+),FX,([^\s]+)\s*$", block)
        ids = np.array([int(r[0]) for r in cards])
        if loaded is None:
            loaded = ids
        else:
            np.testing.assert_array_equal(ids, loaded)
        forces.append([float(r[1]) for r in cards])
    forces = np.array(forces)
    spec = read(AUDIT / "whole_board_pull_inputs.json")[name]
    target = spec["endpoint_force_N"]
    assert len(loaded) == len(set(loaded)) == spec["mesh_load_nodes"]
    np.testing.assert_allclose(forces.sum(1), [1, target, 0], rtol=0, atol=1e-12)
    np.testing.assert_allclose(forces, np.outer([1, target, 0], forces[0]), rtol=1e-12, atol=1e-15)
    src = ROOT / ".runtime/post" / CAMPAIGN / name / "cell_load_nodes"
    request = read(src / "request.json")
    done = read(src / "done.json")
    binary = src / "displacements.bin"
    verified(binary, proof["source_DPF_sha256"])
    assert proof["rst_sha256"] == done["source_sha256"] == request["source_sha256"]
    nodes = np.array(request["nodes"])
    ix = positions(nodes, loaded)
    assert np.array_equal(request["sets"], [r["native_set"] for r in proof["states"]])
    u = (
        np.fromfile(binary, "<f8").reshape(len(request["sets"]), len(nodes), 3)[:, ix, 0]
        * {"m": 1e6, "mm": 1000}[done["unit"].lower()]
    )
    z = next(i for i, r in enumerate(proof["states"]) if r["time"] == 3.0)
    rows = proof["states"][z:]
    dx = u[z:] - u[z]
    centre = np.array([s["cell_centres_XYZ_um"][0][0] for s in rows])
    np.testing.assert_allclose(dx @ forces[0], centre, rtol=0, atol=1e-9)
    force = np.array([s["applied_X_N"] for s in rows])
    time = np.array([s["time"] for s in rows])
    # Independent interpolation of every original FX load card, including the ramp back to zero.
    applied = np.vstack([np.interp(time, [3, 4, 5, 6], [0, one, end, zero]) for one, end, zero in forces.T]).T
    np.testing.assert_allclose(applied.sum(1), force, atol=1e-12)
    work = np.einsum("ij,ij->i", 0.5 * (applied[1:] + applied[:-1]), np.diff(dx, axis=0))
    np.testing.assert_allclose(work, 0.5 * (force[1:] + force[:-1]) * np.diff(centre), rtol=0, atol=1e-9)
    total = np.r_[0, work.cumsum()]
    end = np.flatnonzero(time == 5.0).item()

    def decimated(start, stop):
        selected = np.unique(np.r_[np.arange(start, stop + 1, 2), stop])
        return float(np.trapezoid(force[selected], centre[selected]))

    out = {
        "case": name,
        "source_sha256": digest(proof_path),
        "input_sha256": proof["input_sha256"],
        "displacement_sha256": proof["source_DPF_sha256"],
        "load_nodes": len(loaded),
        "loading_work_uJ": float(total[end]),
        "returned_work_uJ": float(total[end] - total[-1]),
        "cycle_work_uJ": float(total[-1]),
        "alternate_station_loading_work_uJ": decimated(0, end),
        "alternate_station_cycle_work_uJ": decimated(0, end) + decimated(end, len(time) - 1),
        "states": [
            {"set": r["native_set"], "force_N": F, "left_centre_X_um": x, "cumulative_work_uJ": w}
            for r, F, x, w in zip(rows, force, centre, total, strict=True)
        ],
        "scope": "Trapezoidal work of the actual distributed FX load on the whole board, relative to the zero-added-load hold. "
        "The signed cycle integral includes numerical and finite load-increment effects. It does not identify dissipation in any component.",
    }
    assert out["loading_work_uJ"] > 0 and out["returned_work_uJ"] > 0
    write_json(AUDIT / (name + "_work.json"), out)
