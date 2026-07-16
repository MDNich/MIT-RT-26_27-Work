"""Extract radial and axial SVAR1/SVAR2 envelopes from DMP RTH files.

The script is read-only with respect to the ANSYS result files. For the saved
state nearest each integer second from 1 s through 6 s, it:

1. reads elemental-nodal SVAR1 and SVAR2 from every DMP partition;
2. averages all elemental contributions sharing the same global node ID;
3. computes a maximum envelope in 100 radial bands through ``phe0``;
4. computes a maximum envelope in 100 axial bands measured from the lower
   cut plane of the 50 mm Mechanical slice; and
5. writes separate long-form CSV files for the radial and axial profiles.

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
AXIAL_ORIGIN_M = 0.914400
AXIAL_LENGTH_M = 0.050000
TARGET_TIMES_S = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
SVAR_INDICES = (1, 2)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("radial_output_csv", type=Path)
    parser.add_argument("axial_output_csv", type=Path)
    parser.add_argument("result_files", nargs="+", type=Path)
    return parser.parse_args()


def state_variable_fields(model, set_id):
    """Return SVAR1 and SVAR2 fields for one result set."""
    try:
        fields = model.results.state_variable(time_scoping=set_id).eval()
    except (AttributeError, RuntimeError):
        return {}

    selected = {}
    for field_index, field in enumerate(fields):
        label_space = fields.get_label_space(field_index)
        svar_index = int(label_space.get("SVAR", -1))
        if svar_index in SVAR_INDICES:
            selected[svar_index] = field
    return selected


def nearest_sets(model):
    """Map requested integer seconds to their closest saved result sets."""
    support = model.metadata.time_freq_support
    saved_times = np.asarray(support.time_frequencies.data, dtype=float)
    mappings = []
    used_sets = set()
    for target_time in TARGET_TIMES_S:
        saved_index = int(np.argmin(np.abs(saved_times - target_time)))
        set_id = saved_index + 1
        if set_id in used_sets:
            raise RuntimeError(
                "Two requested times map to result set {}.".format(set_id)
            )
        used_sets.add(set_id)
        mappings.append((target_time, set_id, float(saved_times[saved_index])))
    return mappings


def ensure_capacity(array, required_size, fill_value):
    """Grow a one-dimensional or row-major NumPy array."""
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
                "Element {} has {} state values but only {} nodes.".format(
                    element_id,
                    values.size,
                    node_ids.size,
                )
            )
        chunks.append(node_ids[: values.size])
        expected_values += values.size

    flattened = (
        np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int64)
    )
    field_values = np.asarray(field.data).reshape(-1)
    if flattened.size != expected_values or flattened.size != field_values.size:
        raise RuntimeError(
            "Elemental-nodal ordering mismatch: {} node IDs versus {} values."
            .format(flattened.size, field_values.size)
        )
    return flattened


def interpolate_profile(raw):
    """Fill empty one-percent bands by linear interpolation."""
    centers = np.arange(100, dtype=float) + 0.5
    sampled = np.isfinite(raw)
    if not np.any(sampled):
        raise RuntimeError("No sampled profile band was found.")
    return np.interp(centers, centers[sampled], raw[sampled])


def profile_rows(
    time_mappings,
    coordinate_by_node,
    coordinate_origin,
    coordinate_extent,
    value_sums,
    contribution_counts,
):
    """Yield one hundred profile rows for each time and state variable."""
    node_ids = np.flatnonzero(
        (contribution_counts > 0) & np.isfinite(coordinate_by_node)
    )
    coordinate_fraction = (
        (coordinate_by_node[node_ids] - coordinate_origin) / coordinate_extent
    )
    in_interval = (
        (coordinate_fraction >= -1.0e-5)
        & (coordinate_fraction <= 1.0 + 1.0e-5)
    )
    node_ids = node_ids[in_interval]
    coordinate_fraction = np.clip(
        coordinate_fraction[in_interval],
        0.0,
        1.0,
    )
    bin_indices = np.minimum(
        np.floor(100.0 * coordinate_fraction).astype(int),
        99,
    )
    counts = np.bincount(bin_indices, minlength=100)

    for svar_offset, svar_index in enumerate(SVAR_INDICES):
        for time_offset, (
            target_time,
            set_id,
            saved_time,
        ) in enumerate(time_mappings):
            nodal_values = (
                value_sums[svar_offset, time_offset, node_ids]
                / contribution_counts[node_ids].astype(float)
            )
            finite = np.isfinite(nodal_values)
            raw = np.full(100, -np.inf, dtype=float)
            np.maximum.at(
                raw,
                bin_indices[finite],
                nodal_values[finite],
            )
            raw[~np.isfinite(raw)] = np.nan
            plotted = interpolate_profile(raw)

            for bin_index in range(100):
                raw_text = (
                    ""
                    if not np.isfinite(raw[bin_index])
                    else "{:.17g}".format(raw[bin_index])
                )
                yield (
                    "{:.6g}".format(target_time),
                    set_id,
                    "{:.17g}".format(saved_time),
                    svar_index,
                    bin_index + 1,
                    bin_index,
                    bin_index + 1,
                    "{:.6f}".format(
                        1000.0
                        * coordinate_extent
                        * bin_index
                        / 100.0
                    ),
                    "{:.6f}".format(
                        1000.0
                        * coordinate_extent
                        * (bin_index + 1)
                        / 100.0
                    ),
                    raw_text,
                    "{:.17g}".format(plotted[bin_index]),
                    int(not np.isfinite(raw[bin_index])),
                    int(counts[bin_index]),
                )


def write_output(
    path,
    axis_name,
    time_mappings,
    coordinate_by_node,
    coordinate_origin,
    coordinate_extent,
    value_sums,
    contribution_counts,
):
    """Write a long-form CSV for one spatial direction."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "target_time_s",
                "saved_set",
                "saved_time_s",
                "svar_index",
                "bin_index",
                "{}_percent_start".format(axis_name),
                "{}_percent_end".format(axis_name),
                "{}_mm_start".format(axis_name),
                "{}_mm_end".format(axis_name),
                "raw_max_value",
                "plotted_max_value",
                "interpolated",
                "nodal_sample_count",
            )
        )
        writer.writerows(
            profile_rows(
                time_mappings,
                coordinate_by_node,
                coordinate_origin,
                coordinate_extent,
                value_sums,
                contribution_counts,
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
    axial_coordinate_by_node = np.full(1, np.nan, dtype=float)
    contribution_counts = np.zeros(1, dtype=np.int64)
    value_sums = np.zeros(
        (len(SVAR_INDICES), len(time_mappings), 1),
        dtype=float,
    )
    contributing_partitions = 0

    for result_file in result_files:
        print("Reading {}".format(result_file))
        model = dpf.Model(str(result_file))
        mesh = model.metadata.meshed_region

        saved_times = np.asarray(
            model.metadata.time_freq_support.time_frequencies.data,
            dtype=float,
        )
        for _, set_id, expected_time in time_mappings:
            actual_time = float(saved_times[set_id - 1])
            if abs(actual_time - expected_time) > 1.0e-9:
                raise RuntimeError(
                    "Time support differs in {} at set {}.".format(
                        result_file,
                        set_id,
                    )
                )

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
        axial_coordinate_by_node = ensure_capacity(
            axial_coordinate_by_node,
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
        axial_coordinate_by_node[coordinate_ids] = coordinates[:, 1]

        first_fields = state_variable_fields(model, time_mappings[0][1])
        if not first_fields:
            print("  no state-variable field in this partition")
            continue
        missing = set(SVAR_INDICES) - set(first_fields)
        if missing:
            raise RuntimeError(
                "Missing state variables {} in {}.".format(
                    sorted(missing),
                    result_file,
                )
            )

        contributing_partitions += 1
        flat_node_ids = elemental_node_ids(mesh, first_fields[1])
        np.add.at(contribution_counts, flat_node_ids, 1)
        print(
            "  node IDs: coordinates=[{}, {}], state variables=[{}, {}]"
            .format(
                int(coordinate_ids.min()),
                int(coordinate_ids.max()),
                int(flat_node_ids.min()),
                int(flat_node_ids.max()),
            )
        )

        for time_offset, (_, set_id, saved_time) in enumerate(time_mappings):
            fields = (
                first_fields
                if time_offset == 0
                else state_variable_fields(model, set_id)
            )
            for svar_offset, svar_index in enumerate(SVAR_INDICES):
                field = fields.get(svar_index)
                if field is None:
                    raise RuntimeError(
                        "SVAR{} is missing from {} at set {}.".format(
                            svar_index,
                            result_file,
                            set_id,
                        )
                    )
                values = np.asarray(field.data, dtype=float).reshape(-1)
                if values.size != flat_node_ids.size:
                    raise RuntimeError(
                        "SVAR{} topology changed in {} at set {}.".format(
                            svar_index,
                            result_file,
                            set_id,
                        )
                    )
                np.add.at(
                    value_sums[svar_offset, time_offset],
                    flat_node_ids,
                    values,
                )
            print(
                "  set {} at {:.12g} s: {} elemental-nodal values per SVAR"
                .format(set_id, saved_time, flat_node_ids.size)
            )

    if contributing_partitions == 0:
        raise RuntimeError("No partition contained SVAR1/SVAR2 fields.")

    write_output(
        args.radial_output_csv.resolve(),
        "radial_depth",
        time_mappings,
        radius_by_node,
        PHE0_INNER_RADIUS_M,
        PHE0_THICKNESS_M,
        value_sums,
        contribution_counts,
    )
    write_output(
        args.axial_output_csv.resolve(),
        "axial_distance",
        time_mappings,
        axial_coordinate_by_node,
        AXIAL_ORIGIN_M,
        AXIAL_LENGTH_M,
        value_sums,
        contribution_counts,
    )
    print(
        "Wrote {} and {} using {} contributing partitions.".format(
            args.radial_output_csv.resolve(),
            args.axial_output_csv.resolve(),
            contributing_partitions,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
