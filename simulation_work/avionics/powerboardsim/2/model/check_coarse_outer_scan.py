"""Reproduce the rejected faceted crossing and certify the quadratic faces are separated."""

import numpy as np

from basis_comparison import field_files
from case_stress import source
from early_cell_clearance import bezier, outer_faces, subdivision_weights
from film_cell_contact import TOL_MM, candidate_pairs, classify
from film_cell_timestep import refined_coordinates
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FS, participation
from snug_board_pull import AUDIT, ROOT, read
from snug_outer_onset import control
from snug_outer_witness import confirm


def run():
    branch = "snug125_nylon_mesh3"
    proof, folder, rst = source(branch + "_basis", "nov08_01")
    rejected_file = AUDIT / "coarse_outer_scan_initial_rejected.json"
    rejected = read(rejected_file)
    assert rejected["accepted"] is False
    scan = rejected["initial_scan"]
    assert scan["basis_rst_sha256"] == proof["rst_sha256"] and scan["base_axis"] == "X"
    candidate = scan["cells"]["left"]["first_intersecting_sample"]
    samples = np.array([candidate - 1, candidate, candidate + 8])
    load = ROOT / ".runtime/motion_loads/X.txt"
    verified(load, scan["input_sha256"])
    motion = read(ROOT / "validation/independent_motion" / (branch + "_motion_X.json"))
    listing = folder / "solve.out"
    verified(listing, motion["modal_listing_sha256"])
    forcing = np.loadtxt(load, skiprows=1, max_rows=int(samples[-1]) + 1)
    np.testing.assert_allclose(forcing[:, 0], np.arange(len(forcing)) / FS, atol=5.1e-13, rtol=0)
    q, _ = refined_coordinates("linear_input_exact", forcing[:, 1], samples, rst.time_values,
                               participation(listing.read_text(), "X"))
    faces = [outer_faces(rst, [m]) for m in (850, 176)]
    ids = np.unique(np.concatenate([f.ravel() for f in faces]))
    ix = np.searchsorted(rst.mesh.nnum, ids)
    np.testing.assert_array_equal(rst.mesh.nnum[ix], ids)
    xyz = 1000 * rst.mesh.nodes[ix]
    modes = 1000 * displacement_basis(rst, ids, field_files(branch + "_basis", "nov08_01", proof["rst_sha256"], rst.nsets))
    rows = []
    for sample, coord in zip(samples, q, strict=True):
        moved = xyz + (coord @ modes.reshape(len(modes), -1)).reshape(-1, 3)
        a, b = [bezier(moved[np.searchsorted(ids, f)]) for f in faces]
        ia, ib = candidate_pairs((a.min(1) - TOL_MM, a.max(1) + TOL_MM),
                                (b.min(1) - TOL_MM, b.max(1) + TOL_MM))
        old, _ = classify(a[ia], b[ib], subdivision_weights())
        deep, _ = classify(a[ia], b[ib], subdivision_weights(), crossing_depth=6)
        assert deep == "separated" and old == ("intersecting" if sample == candidate else "separated")
        assert confirm(a, b) is None
        rows.append(dict(sample=int(sample), time_ms=float(1000 * sample / FS),
                         original_scan=old, deeper_scan=deep, curved_witness_found=False))
    control()
    write_json(AUDIT / "coarse_outer_scan_rejection.json", dict(case=branch,
        basis_rst_sha256=proof["rst_sha256"], input_sha256=digest(load),
        initial_rejected_scan_sha256=digest(rejected_file), states=rows,
        plane_crossing_control_passed=True, geometry_tolerance_mm=TOL_MM,
        scope="Rejected shallow-facet candidate. Convex hull separation of subdivided quadratic patches "
              "proves clearance at these samples. Coarse-mesh onset requires a complete deeper scan "
              "and an independent curved-surface witness."))
    print(rows, flush=True)


if __name__ == "__main__":
    run()
