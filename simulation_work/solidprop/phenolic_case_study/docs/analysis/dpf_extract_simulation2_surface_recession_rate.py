"""Extract the inner-surface recession-rate distribution from an ANSYS RTH.

For each time present in ``simulation2_history.csv``, this read-only DPF
post-processor obtains the nodal temperature on the complete currently exposed
inner cylindrical surface. It applies the same local energy-balance law as the
Simulation 2 controller,

    v_r = h * max(T_gas - T_surface, 0) / (rho_char * H_eff),

and writes the population mean and population standard deviation over all
surface nodes. The standard deviation therefore measures spatial nonuniformity
over the modeled hot surface; it is not a temporal uncertainty estimate.

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


T_GAS_C = 2230.85
RHO_CHAR_KG_M3 = 600.0
H_EFFECTIVE_J_KG = 35.0e6
SURFACE_RADIUS_TOLERANCE_M = 1.0e-7


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("history_csv", type=Path)
    parser.add_argument("result_files", nargs="+", type=Path)
    return parser.parse_args()


def read_history(path):
    """Read the whitespace-delimited controller history."""
    data = np.genfromtxt(path, names=True, dtype=float, encoding="utf-8")
    data = np.atleast_1d(data)
    required = (
        "time_s",
        "layer",
        "hot_radius_m",
        "alpha_avg",
        "h_W_m2_K",
        "Ts_max_C",
    )
    if any(name not in data.dtype.names for name in required):
        raise RuntimeError("The controller history has unexpected columns.")
    return data


def map_history_to_sets(model, history_times):
    """Match every synchronized history time to an RTH result set."""
    support = model.metadata.time_freq_support
    saved_times = np.asarray(support.time_frequencies.data, dtype=float)
    mappings = []
    for time_value in history_times:
        saved_index = int(np.argmin(np.abs(saved_times - time_value)))
        saved_time = float(saved_times[saved_index])
        if abs(saved_time - time_value) > 1.0e-7:
            raise RuntimeError(
                "No RTH set matches history time {:.12g} s; nearest is "
                "{:.12g} s.".format(time_value, saved_time)
            )
        mappings.append((saved_index + 1, saved_time))
    return mappings


def surface_node_ids(mesh, radius, allow_empty=False):
    """Return all mesh nodes on one cylindrical radius."""
    coordinate_field = mesh.nodes.coordinates_field
    node_ids = np.asarray(coordinate_field.scoping.ids, dtype=np.int64)
    coordinates = np.asarray(coordinate_field.data, dtype=float).reshape((-1, 3))
    radii = np.hypot(coordinates[:, 0], coordinates[:, 2])
    mask = np.abs(radii - radius) <= SURFACE_RADIUS_TOLERANCE_M
    selected = node_ids[mask]
    if selected.size == 0:
        if allow_empty:
            return selected
        raise RuntimeError(
            "No mesh node was found at hot radius {:.12g} m.".format(radius)
        )
    return selected


def scoped_temperature(model, set_id, node_ids):
    """Return nodal temperatures for precisely the requested surface nodes."""
    scoping = dpf.Scoping(
        ids=node_ids.tolist(),
        location=dpf.locations.nodal,
    )
    fields = model.results.temperature(
        time_scoping=set_id,
        mesh_scoping=scoping,
    ).eval()
    if len(fields) != 1:
        raise RuntimeError(
            "Expected one temperature field at set {}, found {}.".format(
                set_id,
                len(fields),
            )
        )
    field = fields[0]
    field_ids = np.asarray(field.scoping.ids, dtype=np.int64)
    values = np.asarray(field.data, dtype=float).reshape(-1)
    if field_ids.size != values.size:
        raise RuntimeError("Temperature scoping and data lengths differ.")

    ordering = np.argsort(field_ids)
    sorted_ids = field_ids[ordering]
    positions = np.searchsorted(sorted_ids, node_ids)
    if (
        np.any(positions >= sorted_ids.size)
        or np.any(sorted_ids[positions] != node_ids)
    ):
        missing = node_ids[
            (positions >= sorted_ids.size)
            | (sorted_ids[np.minimum(positions, sorted_ids.size - 1)] != node_ids)
        ]
        raise RuntimeError(
            "{} requested hot-surface nodes are absent from the temperature "
            "field.".format(missing.size)
        )
    return values[ordering[positions]], field.unit


def main():
    args = parse_args()
    history = read_history(args.history_csv)
    radii = np.unique(np.asarray(history["hot_radius_m"], dtype=float))
    if radii.size != 1:
        raise RuntimeError(
            "This extractor currently expects one exposed radius; history "
            "contains {} radii.".format(radii.size)
        )
    hot_radius = float(radii[0])

    models = []
    partition_node_ids = []
    for result_file in args.result_files:
        print("Opening {}".format(result_file))
        model = dpf.Model(str(result_file.resolve()))
        node_ids = surface_node_ids(
            model.metadata.meshed_region,
            hot_radius,
            allow_empty=True,
        )
        if node_ids.size == 0:
            print("  no hot-surface node in this partition")
            continue
        models.append(model)
        partition_node_ids.append(node_ids)
        print("  {} local hot-surface nodes".format(node_ids.size))

    time_mappings = map_history_to_sets(models[0], history["time_s"])
    for model in models[1:]:
        other_mappings = map_history_to_sets(model, history["time_s"])
        if other_mappings != time_mappings:
            raise RuntimeError("DMP partitions do not expose identical time sets.")

    global_node_ids = np.unique(np.concatenate(partition_node_ids))
    print(
        "Hot radius {:.12g} m: {} unique global surface nodes".format(
            hot_radius,
            global_node_ids.size,
        )
    )
    temperature_sums = np.zeros(
        (len(time_mappings), global_node_ids.size),
        dtype=float,
    )
    contribution_counts = np.zeros(global_node_ids.size, dtype=np.int64)
    temperature_unit = ""

    for partition_index, (model, local_node_ids) in enumerate(
        zip(models, partition_node_ids)
    ):
        positions = np.searchsorted(global_node_ids, local_node_ids)
        np.add.at(contribution_counts, positions, 1)
        for time_index, (set_id, saved_time) in enumerate(time_mappings):
            temperatures_c, temperature_unit = scoped_temperature(
                model,
                set_id,
                local_node_ids,
            )
            np.add.at(
                temperature_sums[time_index],
                positions,
                temperatures_c,
            )
        print(
            "Accumulated partition {}/{}".format(
                partition_index + 1,
                len(models),
            )
        )

    if np.any(contribution_counts == 0):
        raise RuntimeError("Some union surface nodes have no temperature value.")
    temperatures_by_time = (
        temperature_sums / contribution_counts.astype(float)[None, :]
    )

    rows = []
    for index, ((set_id, saved_time), history_row, temperatures_c) in enumerate(
        zip(time_mappings, history, temperatures_by_time)
    ):
        radius = float(history_row["hot_radius_m"])
        h_value = float(history_row["h_W_m2_K"])
        local_rate_um_s = (
            h_value
            * np.maximum(T_GAS_C - temperatures_c, 0.0)
            / (RHO_CHAR_KG_M3 * H_EFFECTIVE_J_KG)
            * 1.0e6
        )
        mean_rate = float(np.mean(local_rate_um_s))
        std_rate = float(np.std(local_rate_um_s, ddof=0))
        controller_rate = (
            h_value
            * max(T_GAS_C - float(history_row["Ts_max_C"]), 0.0)
            / (RHO_CHAR_KG_M3 * H_EFFECTIVE_J_KG)
            * 1.0e6
        )
        rows.append(
            (
                float(history_row["time_s"]),
                int(history_row["layer"]),
                radius,
                float(history_row["alpha_avg"]),
                set_id,
                saved_time,
                int(global_node_ids.size),
                h_value,
                float(np.mean(temperatures_c)),
                float(np.std(temperatures_c, ddof=0)),
                float(np.min(temperatures_c)),
                float(np.max(temperatures_c)),
                mean_rate,
                std_rate,
                float(np.min(local_rate_um_s)),
                float(np.max(local_rate_um_s)),
                controller_rate,
                temperature_unit,
            )
        )
        print(
            "[{}/{}] t={:.6g} s set={} mean={:.6g} um/s "
            "std={:.6g} um/s".format(
                index + 1,
                len(history),
                saved_time,
                set_id,
                mean_rate,
                std_rate,
            )
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "time_s",
                "layer",
                "hot_radius_m",
                "alpha_avg",
                "saved_set",
                "saved_time_s",
                "surface_node_count",
                "h_W_m2_K",
                "surface_temperature_mean_C",
                "surface_temperature_std_C",
                "surface_temperature_min_C",
                "surface_temperature_max_C",
                "recession_rate_mean_um_s",
                "recession_rate_std_um_s",
                "recession_rate_min_um_s",
                "recession_rate_max_um_s",
                "controller_rate_from_Ts_max_um_s",
                "temperature_unit",
            )
        )
        writer.writerows(rows)
    print("Wrote {}".format(args.output_csv))


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
