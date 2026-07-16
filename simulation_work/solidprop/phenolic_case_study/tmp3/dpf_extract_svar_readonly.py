"""Read maxima of UserMatTh SVAR1/SVAR2 without modifying a solve."""

import sys
import traceback

import numpy as np

sys.path.insert(
    0,
    r"C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\Ansys\PyDPF",
)

from ansys.dpf import core as dpf


def maximum_in_field(field):
    best = (-float("inf"), None, None)
    ids = field.scoping.ids
    for entity_index, entity_id in enumerate(ids):
        values = np.asarray(field.get_entity_data(entity_index)).reshape(-1)
        if values.size == 0:
            continue
        local_index = int(np.nanargmax(values))
        value = float(values[local_index])
        if value > best[0]:
            best = (value, int(entity_id), local_index + 1)
    return best


def point_details(mesh, element_id, point_index):
    """Return the global node and coordinates for an elemental-nodal point."""
    element = mesh.elements.element_by_id(element_id)
    node_id = int(element.node_ids[point_index - 1])
    coordinates = np.asarray(
        mesh.nodes.node_by_id(node_id).coordinates,
        dtype=float,
    )
    radius = float(np.hypot(coordinates[0], coordinates[2]))
    return node_id, coordinates, radius


def write_temperature_stats(model, mesh, last_set, stream):
    """Write temperature extrema by radial material region."""
    temperature_fields = model.results.temperature(
        time_scoping=last_set
    ).eval()
    temperature_field = temperature_fields[0]
    temperature_data = np.asarray(
        temperature_field.data,
        dtype=float,
    ).reshape(-1)

    coordinate_field = mesh.nodes.coordinates_field
    coordinate_ids = np.asarray(
        coordinate_field.scoping.ids,
        dtype=np.int64,
    )
    coordinates = np.asarray(
        coordinate_field.data,
        dtype=float,
    ).reshape((-1, 3))
    temperature_ids = np.asarray(
        temperature_field.scoping.ids,
        dtype=np.int64,
    )
    ordering = np.argsort(coordinate_ids)
    positions = np.searchsorted(
        coordinate_ids[ordering],
        temperature_ids,
    )
    temperature_coordinates = coordinates[ordering[positions]]
    radii = np.hypot(
        temperature_coordinates[:, 0],
        temperature_coordinates[:, 2],
    )
    stream.write(
        "mesh_bounds: "
        f"x=[{coordinates[:, 0].min():.12g},"
        f"{coordinates[:, 0].max():.12g}] "
        f"y=[{coordinates[:, 1].min():.12g},"
        f"{coordinates[:, 1].max():.12g}] "
        f"z=[{coordinates[:, 2].min():.12g},"
        f"{coordinates[:, 2].max():.12g}]\n"
    )
    stream.write(f"temperature_unit={temperature_field.unit}\n")

    radial_regions = (
        ("phe0", 0.133350, 0.135890),
        ("epoxy", 0.135890, 0.136525),
        ("phe1", 0.136525, 0.142875),
        ("aluminium", 0.142875, 0.152400),
    )
    for name, lower, upper in radial_regions:
        mask = (radii >= lower - 1.0e-8) & (
            radii <= upper + 1.0e-8
        )
        values = temperature_data[mask]
        if values.size:
            stream.write(
                f"temperature_region: name={name} nodes={values.size} "
                f"min={values.min():.17g} max={values.max():.17g} "
                f"mean={values.mean():.17g}\n"
            )

    for name, radius in (
        ("hot_inner_face", 0.133350),
        ("outer_aluminium_face", 0.152400),
    ):
        mask = np.abs(radii - radius) <= 1.0e-7
        values = temperature_data[mask]
        if values.size:
            stream.write(
                f"temperature_surface: name={name} nodes={values.size} "
                f"min={values.min():.17g} max={values.max():.17g} "
                f"mean={values.mean():.17g}\n"
            )
    return temperature_field


result_file, output_file = sys.argv[1:3]
with open(output_file, "w", encoding="utf-8") as stream:
    try:
        model = dpf.Model(result_file)
        mesh = model.metadata.meshed_region
        support = model.metadata.time_freq_support
        number_sets = support.n_sets
        last_set = number_sets
        last_time = float(support.time_frequencies.data[-1])
        stream.write(f"file={result_file}\nsets={number_sets}\n")
        stream.write(f"last_set={last_set}\nlast_time={last_time:.12g}\n")

        maxima = {}
        fields = None
        try:
            result = model.results.state_variable(time_scoping=last_set)
        except AttributeError:
            stream.write("state_variable: unavailable in this partition\n")
        else:
            fields = result.eval()
            stream.write(
                f"state_variable: fields={len(fields)} "
                f"labels={fields.labels}\n"
            )
            for field_index, field in enumerate(fields):
                value, element_id, point_index = maximum_in_field(field)
                label_space = fields.get_label_space(field_index)
                svar_index = int(label_space["SVAR"])
                node_id, coordinates, radius = point_details(
                    mesh,
                    element_id,
                    point_index,
                )
                maxima[svar_index] = (
                    value,
                    element_id,
                    point_index,
                    node_id,
                )
                stream.write(
                    f"  field={field_index} label_space={label_space} "
                    f"location={field.location} "
                    f"entities={field.scoping.size} "
                    f"components={field.component_count} "
                    f"max={value:.17g} "
                    f"element={element_id} point={point_index} "
                    f"node={node_id} "
                    f"x={coordinates[0]:.12g} "
                    f"y={coordinates[1]:.12g} "
                    f"z={coordinates[2]:.12g} radius={radius:.12g}\n"
                )

        temperature_field = write_temperature_stats(
            model,
            mesh,
            last_set,
            stream,
        )

        if fields is not None and 1 in maxima and 2 in maxima:
            _, rate_element, rate_point, rate_node = maxima[2]
            alpha_field = next(
                field
                for index, field in enumerate(fields)
                if int(fields.get_label_space(index)["SVAR"]) == 1
            )
            alpha_values = np.asarray(
                alpha_field.get_entity_data_by_id(rate_element)
            ).reshape(-1)
            alpha_at_rate_max = float(alpha_values[rate_point - 1])

            temperature_at_rate_max = float(
                np.asarray(
                    temperature_field.get_entity_data_by_id(rate_node)
                ).reshape(-1)[0]
            )
            stream.write(
                f"rate_max_context: alpha={alpha_at_rate_max:.17g} "
                f"temperature={temperature_at_rate_max:.17g} "
                f"temperature_unit={temperature_field.unit}\n"
            )
    except BaseException:
        traceback.print_exc(file=stream)
