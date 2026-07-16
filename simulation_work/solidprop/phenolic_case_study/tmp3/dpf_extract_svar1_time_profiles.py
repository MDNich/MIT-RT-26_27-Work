"""Extract radial SVAR1 envelopes at integer seconds from DMP RTH files.

The script is intentionally read-only with respect to the ANSYS result files.
For every requested time, it:

1. reads the elemental-nodal SVAR1 field from every DMP partition;
2. averages all elemental contributions sharing the same global node ID;
3. groups the resulting nodal values into one-percent radial bands of phe0;
4. writes both the sampled maxima and the linearly interpolated plotting values.

The DMP result files retain global node IDs. Contributions at partition
interfaces are therefore combined before the radial maxima are evaluated.

Run with the ANSYS 2026 R1 CPython interpreter on Windows.
"""

import argparse
import csv
import sys
import traceback
from pathlib import Path

import numpy as np


sys.path.insert(
    0,
    r"C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\Ansys\PyDPF",
)

from ansys.dpf import core as dpf


PHE0_INNER_RADIUS_M = 0.133350
PHE0_THICKNESS_M = 0.002540
TARGET_TIMES_S = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("result_files", nargs="+", type=Path)
    return parser.parse_args()


def svar1_field(model, set_id):
    """Return the SVAR1 field for one result set, or None if unavailable."""
    try:
        fields = model.results.state_variable(time_scoping=set_id).eval()
    except (AttributeError, RuntimeError):
        return None
    for field_index, field in enumerate(fields):
        label_space = fields.get_label_space(field_index)
        if int(label_space.get("SVAR", -1)) == 1:
            return field
    return None


def nearest_sets(model):
    """Map the requested integer seconds to their nearest saved result sets."""
    support = model.metadata.time_freq_support
    saved_times = np.asarray(support.time_frequencies.data, dtype=float)
    mappings = []
    used_sets = set()
    for target_time in TARGET_TIMES_S:
        saved_index = int(np.argmin(np.abs(saved_times - target_time)))
        set_id = saved_index + 1
        if set_id in used_sets:
            raise RuntimeError(
                "Two requested times map to the same result set: {}".format(set_id)
            )
        used_sets.add(set_id)
        mappings.append((target_time, set_id, float(saved_times[saved_index])))
    return mappings


def ensure_capacity(array, required_size, fill_value):
    """Grow a one-dimensional or row-major two-dimensional NumPy array."""
    if array.shape[-1] >= required_size:
        return array
    new_shape = array.shape[:-1] + (required_size,)
    grown = np.full(new_shape, fill_value, dtype=array.dtype)
    grown[..., : array.shape[-1]] = array
    return grown


def elemental_node_ids(mesh, field):
    """Return node IDs in the exact flattened ordering of field.data."""
    chunks = []
    expected_values = 0
    for element_index, element_id in enumerate(field.scoping.ids):
        values = np.asarray(field.get_entity_data(element_index)).reshape(-1)
        node_ids = np.asarray(
            mesh.elements.element_by_id(int(element_id)).node_ids,
            dtype=np.int64,
        )
        if values.size > node_ids.size:
            raise RuntimeError(
                "Element {} has {} SVAR values but only {} nodes.".format(
                    element_id,
                    values.size,
                    node_ids.size,
                )
            )
        chunks.append(node_ids[: values.size])
        expected_values += values.size
    flattened = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int64)
    field_values = np.asarray(field.data).reshape(-1)
    if flattened.size != expected_values or flattened.size != field_values.size:
        raise RuntimeError(
            "Elemental-nodal ordering mismatch: {} node IDs versus {} values.".format(
                flattened.size,
                field_values.size,
            )
        )
    return flattened


def interpolate_profile(raw):
    """Fill empty radial bands by linear interpolation."""
    centers = np.arange(100, dtype=float) + 0.5
    sampled = np.isfinite(raw)
    if not np.any(sampled):
        raise RuntimeError("No sampled radial band was found.")
    return np.interp(centers, centers[sampled], raw[sampled])


def contour_depth_percent(profile, threshold):
    """Return the deepest crossing of a threshold in a radial envelope."""
    centers = np.arange(100, dtype=float) + 0.5
    above = profile >= threshold
    if not np.any(above):
        return float("nan")
    last_above = int(np.flatnonzero(above)[-1])
    if last_above == 99:
        return 100.0
    left_x = centers[last_above]
    right_x = centers[last_above + 1]
    left_y = profile[last_above]
    right_y = profile[last_above + 1]
    if right_y == left_y:
        return right_x
    crossing = left_x + (threshold - left_y) * (right_x - left_x) / (
        right_y - left_y
    )
    return float(np.clip(crossing, 0.0, 100.0))


def write_output(
    path,
    time_mappings,
    radius_by_node,
    value_sums,
    contribution_counts,
):
    """Write a long-form CSV with one hundred bands for every saved time."""
    node_ids = np.flatnonzero(
        (contribution_counts > 0) & np.isfinite(radius_by_node)
    )
    radii = radius_by_node[node_ids]
    depth_percent = (
        100.0 * (radii - PHE0_INNER_RADIUS_M) / PHE0_THICKNESS_M
    )
    in_layer = (depth_percent >= -1.0e-5) & (depth_percent <= 100.0 + 1.0e-5)
    node_ids = node_ids[in_layer]
    depth_percent = np.clip(depth_percent[in_layer], 0.0, 100.0)
    bin_indices = np.minimum(np.floor(depth_percent).astype(int), 99)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "target_time_s",
                "saved_set",
                "saved_time_s",
                "bin_index",
                "depth_percent_start",
                "depth_percent_end",
                "depth_mm_start",
                "depth_mm_end",
                "raw_max_svar1",
                "plotted_max_svar1",
                "interpolated",
                "nodal_sample_count",
                "contour_080_depth_mm",
                "contour_090_depth_mm",
                "contour_095_depth_mm",
            )
        )

        for time_index, (target_time, set_id, saved_time) in enumerate(time_mappings):
            nodal_values = (
                value_sums[time_index, node_ids]
                / contribution_counts[node_ids].astype(float)
            )
            raw = np.full(100, -np.inf, dtype=float)
            np.maximum.at(raw, bin_indices, nodal_values)
            raw[~np.isfinite(raw)] = np.nan
            counts = np.bincount(bin_indices, minlength=100)
            plotted = interpolate_profile(raw)
            contour_depths_mm = [
                contour_depth_percent(plotted, threshold)
                * PHE0_THICKNESS_M
                * 10.0
                for threshold in (0.80, 0.90, 0.95)
            ]

            for bin_index in range(100):
                raw_text = (
                    ""
                    if not np.isfinite(raw[bin_index])
                    else "{:.17g}".format(raw[bin_index])
                )
                writer.writerow(
                    (
                        "{:.6g}".format(target_time),
                        set_id,
                        "{:.17g}".format(saved_time),
                        bin_index + 1,
                        bin_index,
                        bin_index + 1,
                        "{:.6f}".format(
                            bin_index * PHE0_THICKNESS_M * 10.0
                        ),
                        "{:.6f}".format(
                            (bin_index + 1) * PHE0_THICKNESS_M * 10.0
                        ),
                        raw_text,
                        "{:.17g}".format(plotted[bin_index]),
                        int(not np.isfinite(raw[bin_index])),
                        int(counts[bin_index]),
                        "{:.8f}".format(contour_depths_mm[0]),
                        "{:.8f}".format(contour_depths_mm[1]),
                        "{:.8f}".format(contour_depths_mm[2]),
                    )
                )


def main():
    args = parse_args()
    result_files = [path.resolve() for path in args.result_files]
    if not result_files:
        raise RuntimeError("No result file was provided.")

    probe_model = dpf.Model(str(result_files[0]))
    time_mappings = nearest_sets(probe_model)
    del probe_model
    print(
        "Selected sets: {}".format(
            ", ".join(
                "{} s -> set {} at {:.12g} s".format(*mapping)
                for mapping in time_mappings
            )
        )
    )

    radius_by_node = np.full(1, np.nan, dtype=float)
    contribution_counts = np.zeros(1, dtype=np.int64)
    value_sums = np.zeros((len(time_mappings), 1), dtype=float)
    contributing_partitions = 0

    for result_file in result_files:
        print("Reading {}".format(result_file))
        model = dpf.Model(str(result_file))
        mesh = model.metadata.meshed_region
        coordinate_field = mesh.nodes.coordinates_field
        coordinate_ids = np.asarray(
            coordinate_field.scoping.ids,
            dtype=np.int64,
        )
        coordinates = np.asarray(
            coordinate_field.data,
            dtype=float,
        ).reshape((-1, 3))
        required_size = int(coordinate_ids.max()) + 1
        radius_by_node = ensure_capacity(
            radius_by_node,
            required_size,
            np.nan,
        )
        contribution_counts = ensure_capacity(
            contribution_counts,
            required_size,
            0,
        )
        value_sums = ensure_capacity(
            value_sums,
            required_size,
            0.0,
        )
        radius_by_node[coordinate_ids] = np.hypot(
            coordinates[:, 0],
            coordinates[:, 2],
        )

        first_field = svar1_field(model, time_mappings[0][1])
        if first_field is None:
            print("  no SVAR1 field in this partition")
            continue
        contributing_partitions += 1
        flat_node_ids = elemental_node_ids(mesh, first_field)
        np.add.at(contribution_counts, flat_node_ids, 1)
        print(
            "  node IDs: coordinates=[{}, {}], SVAR=[{}, {}]".format(
                int(coordinate_ids.min()),
                int(coordinate_ids.max()),
                int(flat_node_ids.min()),
                int(flat_node_ids.max()),
            )
        )

        for time_index, (_, set_id, saved_time) in enumerate(time_mappings):
            field = first_field if time_index == 0 else svar1_field(model, set_id)
            if field is None:
                raise RuntimeError(
                    "SVAR1 is missing from {} at set {}.".format(
                        result_file,
                        set_id,
                    )
                )
            values = np.asarray(field.data, dtype=float).reshape(-1)
            if values.size != flat_node_ids.size:
                raise RuntimeError(
                    "SVAR1 topology changed in {} at set {}.".format(
                        result_file,
                        set_id,
                    )
                )
            np.add.at(value_sums[time_index], flat_node_ids, values)
            print(
                "  set {} at {:.12g} s: {} elemental-nodal values".format(
                    set_id,
                    saved_time,
                    values.size,
                )
            )

    if contributing_partitions == 0:
        raise RuntimeError("No partition contained an SVAR1 field.")

    write_output(
        args.output_csv.resolve(),
        time_mappings,
        radius_by_node,
        value_sums,
        contribution_counts,
    )
    print(
        "Wrote {} using {} SVAR1 partitions.".format(
            args.output_csv.resolve(),
            contributing_partitions,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
