"""Bound the global minimum distance between two deformed quadratic surface meshes, in mm."""

import numpy as np
from early_cell_clearance import subdivision_weights, unresolved
from film_cell_contact import TOL_MM, candidate_pairs
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from snug_pocket_depth import surface_at, surface_gradient


def pair_upper(a, b):
    def delta(x):
        return surface_at(a, x[:2]) - surface_at(b, x[2:])

    def jac(x):
        return np.vstack((surface_gradient(a, x[:2]), -surface_gradient(b, x[2:]))) @ delta(x)

    x = np.full(4, 1 / 3)
    opt = minimize(
        lambda p: 0.5 * np.sum(delta(p) ** 2),
        x,
        jac=jac,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * 4,
        constraints=[
            {
                "type": "ineq",
                "fun": lambda p: 1 - np.array([p[:2].sum(), p[2:].sum()]),
                "jac": lambda p: np.array([[-1, -1, 0, 0], [0, 0, -1, -1]]),
            }
        ],
        options={"ftol": 1e-17, "maxiter": 60},
    )
    # Even an unfinished minimization yields an upper bound after projecting its parameters onto each triangle.
    q = np.clip(opt.x.reshape(2, 2), 0.0, 1.0)
    q /= np.maximum(1.0, q.sum(1, keepdims=True))
    value = float(np.linalg.norm(delta(q.ravel())))
    return value, q.tolist()


def edge_bounds(a, b, limit):
    """Use vertex--edge directions for nearly tangent separated triangle boundaries."""
    keep = np.arange(len(a))
    for reverse in (False, True):
        for i in range(3):
            for j in range(3):
                if not len(keep):
                    return keep
                first, second = (b[keep], a[keep]) if reverse else (a[keep], b[keep])
                edge = second[:, (j + 1) % 3] - second[:, j]
                v = first[:, i] - second[:, j]
                frac = np.einsum("ij,ij->i", v, edge) / np.maximum(
                    np.einsum("ij,ij->i", edge, edge), 1e-50
                )
                axis = v - edge * np.clip(frac, 0.0, 1.0)[:, None]
                axis /= np.maximum(np.linalg.norm(axis, axis=1)[:, None], 1e-30)
                ref = second[:, j, None, :]
                fa = np.einsum("nij,nj->ni", first - ref, axis)
                fb = np.einsum("nij,nj->ni", second - ref, axis)
                gaps = np.maximum(fa.min(1) - fb.max(1), fb.min(1) - fa.max(1))
                keep = keep[gaps <= limit]
    return keep


def surface_distance(a, b, tolerance_mm=0.0001):
    margin = TOL_MM
    distances, neighbours = cKDTree(a[:, :3].reshape(-1, 3)).query(b[:, :3].reshape(-1, 3), k=1)
    j = int(distances.argmin())
    i = int(neighbours[j])
    upper = float(distances[j]) + margin
    witness = {"case_face": i // 3, "cell_face": j // 3, "source": "two triangle vertices"}
    ia, ib = candidate_pairs((a.min(1) - upper, a.max(1) + upper), (b.min(1), b.max(1)))
    x, y = a[ia], b[ib]
    weights = subdivision_weights()
    counts = []
    tested = set()
    for depth in range(12):
        keep = unresolved(x, y, max(0, upper - tolerance_mm) + margin)
        if depth >= 2 and len(keep):
            keep = keep[edge_bounds(x[keep], y[keep], max(0, upper - tolerance_mm) + margin)]
        if len(keep) == 0 or upper <= tolerance_mm:
            return {
                "lower_mm": max(0, upper - tolerance_mm),
                "upper_mm": upper,
                "witness": witness,
                "surviving_pairs": counts + [len(keep)],
            }
        x, y, ia, ib = (z[keep] for z in (x, y, ia, ib))
        counts.append(len(x))
        assert len(x) < 160000
        sq = np.full(len(x), np.inf)
        for ii in range(3):
            for jj in range(3):
                v = x[:, ii] - y[:, jj]
                sq = np.minimum(sq, np.einsum("ij,ij->i", v, v))
        best = int(np.argmin(sq))
        if np.sqrt(sq[best]) + margin < upper:
            upper = float(np.sqrt(sq[best]) + margin)
            witness = {
                "case_face": int(ia[best]),
                "cell_face": int(ib[best]),
                "source": f"two subdivision-{depth} vertices",
            }
        for ii in np.argsort(sq)[:16]:
            pair = (int(ia[ii]), int(ib[ii]))
            if pair in tested:
                continue
            tested.add(pair)
            value, uv = pair_upper(a[pair[0]], b[pair[1]])
            if value + margin < upper:
                upper = value + margin
                witness = {
                    "case_face": pair[0],
                    "cell_face": pair[1],
                    "source": "evaluated quadratic surfaces",
                    "uv": uv,
                }
        x = np.repeat(weights @ x[:, None], 4, axis=1).reshape(-1, 6, 3)
        y = np.tile(weights @ y[:, None], (1, 4, 1, 1)).reshape(-1, 6, 3)
        ia = np.repeat(ia, 16)
        ib = np.repeat(ib, 16)
    raise ValueError(f"Distance bounds failed to close within {tolerance_mm} mm: {counts}")


if __name__ == "__main__":
    v = np.array([[0.0, 0, 0], [1.0, 0, 0], [0.0, 1, 0]])
    tri = np.concatenate([v, (v + np.roll(v, -1, axis=0)) / 2])[None]
    patches = np.concatenate((tri, tri + np.array([1.5, 0, -0.002])))
    other = tri + np.array([0.04, 0.05, 0.01234])
    bracket = surface_distance(patches, other)
    assert bracket["lower_mm"] <= 0.01234 <= bracket["upper_mm"]
    print(bracket)
