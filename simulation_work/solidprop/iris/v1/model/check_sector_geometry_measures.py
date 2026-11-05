"""Audit controller geometry measures against the actual straight-sided mesh.

Read-only geometry integration and a separately labelled reduced-model
perturbation. No sealed package, native state or acceptance gate is changed.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from ops import ROOT, TMP, atomic, disks, host_check, utc
from radial_model import RadialModel


def geometry_audit(run):
    cfg = json.loads((run/'config.json').read_text())
    mesh = json.loads((run/'mesh_map.json').read_text())
    nodes = {}
    for line in (run/'model_base.inp').read_text().splitlines():
        if line.startswith('N,'):
            p = line.split(',')
            nodes[int(p[1])] = np.array([float(x) for x in p[2:5]])
    assert len(nodes) == cfg['expected_nodes']
    face_ratios = []
    for face in [f for row in mesh['rows'] for f in row] + mesh['outer']:
        x = np.array([nodes[n] for n in face['nodes']])
        area = .5*(np.linalg.norm(np.cross(x[1]-x[0], x[2]-x[0]))
                   + np.linalg.norm(np.cross(x[2]-x[0], x[3]-x[0])))
        face_ratios.append(float(area/face['area']))
    signs = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
                      [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])
    volume_ratios = []
    for element in mesh['elements'].values():
        x = np.array([nodes[n] for n in element['nodes']])
        volume = 0.
        for q in signs/math.sqrt(3):
            derivatives = np.empty((8,3))
            for axis in range(3):
                other = [k for k in range(3) if k != axis]
                derivatives[:,axis] = signs[:,axis]*np.prod(1+signs[:,other]*q[other],axis=1)/8
            volume += abs(np.linalg.det(x.T @ derivatives))
        volume_ratios.append(float(volume/element['volume']))
    angle = math.radians(cfg['geometry']['angle_deg'])/cfg['geometry']['angular_divisions']
    face_ratio = 2*math.sin(angle/2)/angle
    volume_ratio = math.sin(angle)/angle
    assert max(abs(r-face_ratio) for r in face_ratios) < 1e-10
    assert max(abs(r-volume_ratio) for r in volume_ratios) < 1e-9
    terminal = json.loads((run/'state.json').read_text())
    residuals = []
    for index in range(1,terminal['index']+1):
        audit = json.loads((run/'checkpoints'/f'audit_{index:06d}.json').read_text())
        if audit.get('exposure_on') and abs(audit['hot_power_expected_W']) > 1e-8:
            residuals.append(audit['hot_power_actual_W']/audit['hot_power_expected_W']-face_ratio)
    assert residuals
    return dict(runtime=run.name, native_index=terminal['index'],
        model_sha256=hashlib.sha256((run/'model_base.inp').read_bytes()).hexdigest(),
        mesh_map_sha256=hashlib.sha256((run/'mesh_map.json').read_bytes()).hexdigest(),
        face_count=len(face_ratios), element_count=len(volume_ratios),
        angular_cell_width_rad=angle,
        exact_polygon_to_controller_area_ratio=face_ratio,
        integrated_area_ratio_range=[min(face_ratios),max(face_ratios)],
        exact_polygon_to_controller_volume_ratio=volume_ratio,
        integrated_volume_ratio_range=[min(volume_ratios),max(volume_ratios)],
        native_hot_power_ratio_minus_polygon_area_ratio=dict(
            samples=len(residuals),mean=float(np.mean(residuals)),max_abs=float(np.max(np.abs(residuals)))),
        interpretation='Controller areas/volumes use cylindrical arcs. The straight-sided SOLID278 coordinates define chord faces and polygonal volumes. The actual native convection ratio agrees with the chord-area ratio to the recorded export precision. A passing loose heat-power audit does not remove this geometric discrepancy.')


def isolated_convection_test(run):
    cfg = json.loads((run/'config.json').read_text())
    g = cfg['geometry']
    angle = math.radians(g['angle_deg'])/g['angular_divisions']
    area_ratio = 2*math.sin(angle/2)/angle

    class FaceAreaOnly(RadialModel):
        def boundary(self, state, dt):
            h, temperature, flux, radiation, outer = super().boundary(state,dt)
            # Retain the original arc-based removal sink; reduce only the
            # convection assembled by the thermal solve, as with chord faces.
            return h*area_ratio,temperature,flux,radiation,outer

    indices = [1114,1600,2093,2094,2240]
    states = {}
    for index in indices:
        with gzip.open(run/'checkpoints'/f'state_{index:06d}.json.gz','rt') as stream:
            states[index] = json.load(stream)
    targets = [states[i]['time_s'] for i in indices]
    plane = (g['angular_divisions']+1)*(g['axial_divisions']+1)
    variants = []
    for label,kind in [('unchanged_cylindrical_reference',RadialModel),('convection_face_area_only',FaceAreaOnly)]:
        model = kind(cfg)
        _, history, snapshots = model.run(targets[-1],dt=cfg['macro_dt_s'],targets=targets,check=host_check)
        events = [dict(time_s=r['time_s'],rows_removed=r['layer']) for j,r in enumerate(history)
                  if j and r['layer']>history[j-1]['layer']]
        comparisons = []
        for index in indices:
            native = states[index]
            state = snapshots[native['time_s']]
            temperature = np.array([np.mean([native['temperatures'][str(1+j*plane+k)] for k in range(plane)])
                                    for j in range(len(model.r))])
            common = max(native['layer'],state.layer)
            comparisons.append(dict(index=index,time_s=state.time,native_layer=native['layer'],
                independent_diagnostic_layer=state.layer,
                max_live_profile_difference_K=float(np.max(abs(state.T[common:]-temperature[common:])))))
        variants.append(dict(variant=label,removal_events=events,comparisons=comparisons,
                             energy_error=model.max_energy_error,mass_error=model.max_mass_error))
    return dict(variants=variants, qualification='Isolated diagnostic only. It changes only the reduced thermal convection area, not all 3-D geometry operators, and is not an accepted correction or replacement independent reference. No material or reaction parameter is fitted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime',default='sustainer_al_pulse7_midpoint_space160_smp10')
    args = parser.parse_args()
    disks()
    run = TMP/'runs'/args.runtime
    result = dict(checked_utc=utc(),geometry=geometry_audit(run),
        isolated_diagnostic=isolated_convection_test(run),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        conclusion='A sub-ppm face-area discrepancy can shift the discrete second-row event by one interval in this lagged energy-capped model. Geometry consistency must be tested separately from nonlinear convergence. This does not establish a complete cause or validate a motor lifetime.')
    atomic(ROOT/'validation/sector_geometry_measure_diagnosis.json',result)
    print(json.dumps(result['geometry'],indent=2))
    print('Diagnostic second events:',[(r['variant'],r['removal_events'][-1]) for r in result['isolated_diagnostic']['variants']])
