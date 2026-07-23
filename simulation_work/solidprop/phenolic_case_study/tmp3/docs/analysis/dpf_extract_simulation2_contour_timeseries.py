"""Extract an exact Simulation 2 pyrolysis-contour time series.

This read-only DPF post-processor evaluates the elemental-nodal SVAR1 field at
every synchronized time in ``simulation2_history.csv``. Contributions sharing
the same global node ID are averaged across elements and DMP partitions before
the radial maximum envelope is formed in 100 one-percent bands through
``phe0``. The deepest crossings of alpha = 0.99, 0.95, and 0.90 are then
reported together with their signed distance from the virtual-recession
coordinate.

Run with the ANSYS 2026 R1 CPython interpreter on Windows.
"""

import argparse
import csv
import math
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dpf_extract_svar_spatiotemporal_profiles as base  # noqa: E402


THRESHOLDS = (0.99, 0.95, 0.90)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("history_csv", type=Path)
    parser.add_argument("result_files", nargs="+", type=Path)
    parser.add_argument(
        "--max-time",
        type=float,
        default=None,
        help="Optional upper time bound used for a short validation run.",
    )
    return parser.parse_args()


def read_history(path, max_time=None):
    data = np.genfromtxt(path, names=True, dtype=float, encoding="utf-8")
    data = np.atleast_1d(data)
    required = {"time_s", "recession_m"}
    if not required.issubset(data.dtype.names or ()):
        raise RuntimeError("Unexpected Simulation 2 history columns.")
    if max_time is not None:
        data = data[data["time_s"] <= max_time + 1.0e-10]
    if data.size == 0:
        raise RuntimeError("No history row remains after time selection.")
    return data


def map_history_to_sets(model, history_times):
    saved_times = np.asarray(
        model.metadata.time_freq_support.time_frequencies.data,
        dtype=float,
    )
    mappings = []
    for history_time in history_times:
        saved_index = int(np.argmin(np.abs(saved_times - history_time)))
        saved_time = float(saved_times[saved_index])
        if abs(saved_time - history_time) > 1.0e-7:
            raise RuntimeError(
                "No RTH set matches history time {:.12g} s; nearest is "
                "{:.12g} s.".format(history_time, saved_time)
            )
        mappings.append((saved_index + 1, saved_time))
    if len({set_id for set_id, _ in mappings}) != len(mappings):
        raise RuntimeError("History times do not map to unique RTH sets.")
    return mappings


def svar1_fields(model, set_ids):
    try:
        fields = model.results.state_variable(time_scoping=set_ids).eval()
    except (AttributeError, RuntimeError):
        return []

    selected = []
    for field_index, field in enumerate(fields):
        label_space = fields.get_label_space(field_index)
        if int(label_space.get("SVAR", -1)) == 1:
            selected.append(
                (
                    int(label_space.get("time", field_index)),
                    field,
                    label_space,
                )
            )
    if not selected:
        return []
    if len(selected) != len(set_ids):
        raise RuntimeError(
            "Expected {} SVAR1 fields, found {}.".format(
                len(set_ids),
                len(selected),
            )
        )
    selected.sort(key=lambda item: item[0])
    return [field for _, field, _ in selected]


def interpolate_profile(raw):
    centers = np.arange(100, dtype=float) + 0.5
    sampled = np.isfinite(raw)
    if not np.any(sampled):
        raise RuntimeError("No sampled radial band was found.")
    return np.interp(centers, centers[sampled], raw[sampled])


def contour_depth_mm(profile, threshold):
    centers_mm = (
        (np.arange(100, dtype=float) + 0.5)
        * base.PHE0_THICKNESS_M
        * 10.0
    )
    above = np.flatnonzero(profile >= threshold)
    if above.size == 0:
        return math.nan
    last = int(above[-1])
    if last == profile.size - 1:
        return float(centers_mm[last])
    x0, x1 = float(centers_mm[last]), float(centers_mm[last + 1])
    y0, y1 = float(profile[last]), float(profile[last + 1])
    if y1 == y0:
        return x0
    return x0 + (threshold - y0) * (x1 - x0) / (y1 - y0)


def write_output(path, history, mappings, rows):
    fieldnames = [
        "saved_time_s",
        "saved_set",
        "recession_depth_mm",
        "contour_099_depth_mm",
        "signed_distance_099_mm",
        "contour_095_depth_mm",
        "signed_distance_095_mm",
        "contour_090_depth_mm",
        "signed_distance_090_mm",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=path.parent,
        prefix=".{}_".format(path.name),
        suffix=".tmp",
        delete=False,
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for history_row, (set_id, saved_time), contour_row in zip(
            history,
            mappings,
            rows,
        ):
            recession_mm = 1000.0 * float(history_row["recession_m"])
            output_row = {
                "saved_time_s": "{:.12g}".format(saved_time),
                "saved_set": set_id,
                "recession_depth_mm": "{:.12g}".format(recession_mm),
            }
            for threshold, depth in zip(THRESHOLDS, contour_row):
                key = "{:03d}".format(round(100.0 * threshold))
                if math.isfinite(depth):
                    output_row["contour_{}_depth_mm".format(key)] = (
                        "{:.12g}".format(depth)
                    )
                    output_row["signed_distance_{}_mm".format(key)] = (
                        "{:.12g}".format(depth - recession_mm)
                    )
                else:
                    output_row["contour_{}_depth_mm".format(key)] = ""
                    output_row["signed_distance_{}_mm".format(key)] = ""
            writer.writerow(output_row)
        temporary_path = Path(stream.name)
    temporary_path.replace(path)


def main():
    args = parse_args()
    history = read_history(args.history_csv, args.max_time)
    result_files = [path.resolve() for path in args.result_files]
    if not result_files:
        raise RuntimeError("No result file was provided.")

    models = [base.dpf.Model(str(path)) for path in result_files]
    mappings = map_history_to_sets(models[0], history["time_s"])
    for model in models[1:]:
        if map_history_to_sets(model, history["time_s"]) != mappings:
            raise RuntimeError("DMP partitions expose different time supports.")
    set_ids = [set_id for set_id, _ in mappings]
    print(
        "Selected {} exact sets from {:.6g} to {:.6g} s.".format(
            len(mappings),
            mappings[0][1],
            mappings[-1][1],
        )
    )

    maximum_node_id = 0
    radius_by_node = np.full(1, np.nan, dtype=float)
    for model in models:
        coordinate_field = model.metadata.meshed_region.nodes.coordinates_field
        node_ids = np.asarray(coordinate_field.scoping.ids, dtype=np.int64)
        coordinates = np.asarray(
            coordinate_field.data,
            dtype=float,
        ).reshape((-1, 3))
        maximum_node_id = max(maximum_node_id, int(node_ids.max()))
        if radius_by_node.size <= maximum_node_id:
            grown = np.full(maximum_node_id + 1, np.nan, dtype=float)
            grown[: radius_by_node.size] = radius_by_node
            radius_by_node = grown
        radii = np.hypot(coordinates[:, 0], coordinates[:, 2])
        existing = np.isfinite(radius_by_node[node_ids])
        if np.any(existing):
            differences = np.abs(radius_by_node[node_ids[existing]] - radii[existing])
            if np.any(differences > 1.0e-10):
                raise RuntimeError("DMP node radii are inconsistent.")
        radius_by_node[node_ids] = radii

    value_sums = np.zeros(
        (len(mappings), maximum_node_id + 1),
        dtype=np.float32,
    )
    contribution_counts = np.zeros(maximum_node_id + 1, dtype=np.int32)
    contributing_partitions = 0

    for partition_index, (result_file, model) in enumerate(
        zip(result_files, models),
        start=1,
    ):
        print(
            "[{}/{}] Reading all SVAR1 states from {}".format(
                partition_index,
                len(models),
                result_file,
            )
        )
        fields = svar1_fields(model, set_ids)
        if not fields:
            print("  no SVAR1 field in this partition")
            continue
        flat_node_ids = base.elemental_node_ids(
            model.metadata.meshed_region,
            fields[0],
        )
        np.add.at(contribution_counts, flat_node_ids, 1)
        for time_index, field in enumerate(fields):
            values = np.asarray(field.data, dtype=np.float32).reshape(-1)
            if values.size != flat_node_ids.size:
                raise RuntimeError(
                    "SVAR1 topology changed in {} at set {}.".format(
                        result_file,
                        set_ids[time_index],
                    )
                )
            np.add.at(value_sums[time_index], flat_node_ids, values)
        contributing_partitions += 1
        print(
            "  accumulated {} states and {} elemental-nodal values per state"
            .format(len(fields), flat_node_ids.size)
        )
        del fields

    if contributing_partitions == 0:
        raise RuntimeError("No partition contained SVAR1.")

    node_ids = np.flatnonzero(
        (contribution_counts > 0) & np.isfinite(radius_by_node)
    )
    depths = radius_by_node[node_ids] - base.PHE0_INNER_RADIUS_M
    in_layer = (
        (depths >= -1.0e-8)
        & (depths <= base.PHE0_THICKNESS_M + 1.0e-8)
    )
    node_ids = node_ids[in_layer]
    depths = np.clip(depths[in_layer], 0.0, base.PHE0_THICKNESS_M)
    bin_indices = np.minimum(
        np.floor(100.0 * depths / base.PHE0_THICKNESS_M).astype(int),
        99,
    )
    if node_ids.size == 0:
        raise RuntimeError("No phe0 node was selected.")
    print("Selected {} phe0 nodes.".format(node_ids.size))

    contour_rows = []
    denominators = contribution_counts[node_ids].astype(np.float32)
    for time_index, (_, saved_time) in enumerate(mappings):
        nodal_values = value_sums[time_index, node_ids] / denominators
        raw = np.full(100, -np.inf, dtype=float)
        np.maximum.at(raw, bin_indices, nodal_values)
        raw[~np.isfinite(raw)] = np.nan
        plotted = interpolate_profile(raw)
        contour_rows.append(
            [contour_depth_mm(plotted, threshold) for threshold in THRESHOLDS]
        )
        print(
            "[{}/{}] t={:.6g} s contours={}".format(
                time_index + 1,
                len(mappings),
                saved_time,
                ", ".join(
                    "nan" if not math.isfinite(value) else "{:.6g}".format(value)
                    for value in contour_rows[-1]
                ),
            )
        )

    write_output(args.output_csv.resolve(), history, mappings, contour_rows)
    print(
        "Wrote {} using {} contributing partitions.".format(
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
