"""Resolve the two early contact transitions in the nylon side pull on the original load path."""

import json

from audit_local import read
from film_identity import digest, verified, write_json
from snug_directional_result import paired
from snug_local_checkpoint import CASE as PARENT
from snug_pull_energy import closed_series, report
from stage_local_jobs import seal
from stage_snug_fit import AUDIT, INPUTS

CASE = "snug125_nylon_lateral_friction_locked_steps_m15"
REGISTRY = AUDIT / "local_pull_step_input.json"
ENERGY = AUDIT / (PARENT + "_ls3_ss47_energy.json")
ORIGINAL = b"TIME,3\nNSUBST,100,4000,20\nD,2481,UX,0.5\nSOLVE\n"


def stage():
    source = read(ENERGY)
    cp = AUDIT / (PARENT + "_ls3_ss47_checkpoint.json")
    verified(cp, source["checkpoint_sha256"])
    proof = read(cp)
    parent = read(AUDIT / "local_inputs_m15.json")[PARENT]
    assert (
        source["cased"]["rst_sha256"] == proof["rst_sha256"]
        and proof["input_sha256"] == parent["input_sha256"]
    )
    incoming = INPUTS / PARENT
    config = incoming / "local_job.json"
    verified(config, parent["spec_sha256"])
    spec = read(config)
    assert spec["source"] == "lateral_friction_locked" and spec["cores"] == 4
    for name, h in spec["files"].items():
        verified(incoming / name, h)
    steps = []
    blocks = []
    for s in source["cased"]["history"]:
        n = s["native_set"]
        if n == 9:
            continue
        travel = round(s["travel_mm"], 9)
        assert s["within_parent_screens"]
        count = 4 if n in (13, 14) else 8 if n in (21, 22) else 1
        steps.append({"parent_native_set": n, "travel_mm": travel, "subdivisions": count})
        time = 2 + 2 * travel
        blocks.extend(
            [
                f"TIME,{time:.12g}",
                f"NSUBST,{count},{max(2 * count, 64)},{count}",
                f"D,2481,UX,{travel:.12g}",
                "SOLVE",
            ]
        )
        if n == 22:
            break
    assert len(steps) == 13 and steps[-1]["travel_mm"] == 0.219375
    assert steps[3]["travel_mm"] == 0.02875 and steps[-2]["travel_mm"] == 0.206875
    original = (incoming / "model.inp").read_bytes()
    assert original.count(ORIGINAL) == 1
    insert = ("\n".join(blocks) + "\n").encode()
    deck = original.replace(ORIGINAL, insert)
    assert deck.replace(insert, ORIGINAL) == original
    dst = INPUTS / CASE
    dst.mkdir(exist_ok=True)
    files = {"model.inp": seal(dst / "model.inp", deck)}
    for name in ("moving.inp", "local_post.inp"):
        files[name] = seal(dst / name, (incoming / name).read_bytes())
    job = dict(
        spec,
        case=CASE,
        files=files,
        snug_step_parent=PARENT,
        end_time=time,
        displacement_mm=steps[-1]["travel_mm"],
    )
    for key in ("supersedes", "previous_input_sha256"):
        job.pop(key, None)
    config_sha = seal(dst / "local_job.json", (json.dumps(job, indent=2) + "\n").encode())
    write_json(
        REGISTRY,
        {
            CASE: {
                "case": CASE,
                "parent": PARENT,
                "bare_reference": proof["bare_case"],
                "spec_sha256": config_sha,
                "input_sha256": files["model.inp"],
                "parent_input_sha256": parent["input_sha256"],
                "energy_sha256": digest(ENERGY),
                "steps": steps,
                "mesh_sha256": parent["mesh_sha256"],
                "target_sha256": parent["target_sha256"],
                "end_time": time,
                "displacement_mm": steps[-1]["travel_mm"],
                "scope": "Same displacement ramp and native stations through the first loaded middle-cell station. "
                "Only increments at the first moving-cell contact and the fixed-cell engagement are subdivided.",
            }
        },
    )


def compare_histories(original, refined, steps):
    output = []
    for step in steps:
        n = step["parent_native_set"]
        x = step["travel_mm"]
        parent = next(s for s in original if s["native_set"] == n)
        matches = [s for s in refined if abs(s["travel_mm"] - x) < 1e-8]
        if not matches and x > refined[-1]["travel_mm"] + 1e-8:
            break
        assert len(matches) == 1 and abs(parent["travel_mm"] - x) < 1e-8
        trial = matches[0]
        output.append(
            {
                "parent_set": n,
                "refined_set": trial["native_set"],
                "travel_mm": x,
                "force_N": [parent["cell_force_N"], trial["cell_force_N"]],
                "work_mJ": [parent["actuator_work_mJ"], trial["actuator_work_mJ"]],
                "group_work_mJ": {
                    k: [parent["work_by_group_mJ"][k], trial["work_by_group_mJ"][k]]
                    for k in parent["work_by_group_mJ"]
                },
                "both_within_parent_screens": parent["within_parent_screens"]
                and trial["within_parent_screens"],
            }
        )
    return output


def audit(case, campaign, verdict):
    spec = read(REGISTRY)[case]
    verified(ENERGY, spec["energy_sha256"])
    baseline = read(ENERGY)
    assert read(verdict)["solver_runtime"]["cores"] == 4
    comparison = paired(case, spec["bare_reference"], verdict)
    run = closed_series(case, campaign, verdict)
    assert run["rst_sha256"] == comparison["native_rst_sha256"] == read(verdict)["rst_sha256"]
    bare = closed_series(spec["bare_reference"], campaign)
    result = report(run, bare, comparison["equal_travel"]["cased"]["set"])
    common = compare_histories(baseline["cased"]["history"], run["history"], spec["steps"])
    if read(verdict)["full_requested_path"]:
        assert len(common) == len(spec["steps"])
        atlock = run["history"][0]["native_set"]
        for state, step in zip(common, spec["steps"], strict=True):
            assert state["refined_set"] - atlock >= step["subdivisions"]
            atlock = state["refined_set"]
    result.update(
        staged_input_sha256=spec["input_sha256"],
        reference_sha256=digest(ENERGY),
        matched_stations=common,
    )
    write_json(AUDIT / "nylon_local_step_comparison.json", result)


if __name__ == "__main__":
    stage()
