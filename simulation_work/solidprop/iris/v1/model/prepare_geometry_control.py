"""Prepare one fresh geometry-consistency control without launching ANSYS."""
import hashlib
import json
import subprocess
import sys

from check_sector_geometry_measures import geometry_audit
from ops import ROOT, TMP, atomic, disks, utc
from prepare_model import create_mesh


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    disks()
    # The opt-in geometry correction must leave archived configurations
    # reproducible. These dictionaries are the exact controller inputs.
    legacy = []
    for case in ['sustainer_al', 'sustainer_cf', 'booster_al', 'booster_cf']:
        old = TMP/'runs'/f'{case}_pulse7_n80_midpoint_tight'
        cfg = json.loads((old/'config.json').read_text())
        actual = json.loads((old/'mesh_map.json').read_text())
        generated, _, _ = create_mesh(cfg)
        for key in ['elements', 'rows', 'outer']:
            assert actual[key] == generated[key], (case, key)
        legacy.append(dict(runtime=old.name, mesh_map_sha256=sha(old/'mesh_map.json'),unchanged=True))
    parent_name = 'sustainer_al_pulse7_midpoint_space160_tol1e7_smp10'
    name = 'sustainer_al_pulse7_midpoint_space160_geom005_smp10'
    parent = TMP/'runs'/parent_name
    target = TMP/'runs'/name
    config_path = ROOT/'configs'/f'{name}.json'
    assert not target.exists() and not config_path.exists(), 'Preserve sealed packages'
    cfg = json.loads((parent/'config.json').read_text())
    cfg.update(windows_root='C:\\IrisStudy\\runs\\'+name,
               host_runtime='I:\\ansystmp\\runs\\'+name,
               mesh_measure_convention='straight_sided_hex',
               campaign_role='native_geometry_consistency_control',
               resolution_level='space160_geometry_control')
    old_angle = cfg['geometry']['angle_deg']
    cfg['geometry']['angle_deg'] = 0.05
    cfg['geometry']['full_ring_scale_factor'] = 360/cfg['geometry']['angle_deg']
    cfg['provenance']['geometry_consistency_parent'] = dict(
        runtime=parent_name, config_sha256=sha(parent/'config.json'),
        parent_angle_deg=old_angle,
        change='Exact chord areas and polygonal element volumes; total sector angle 0.5 to 0.05 degrees. Same radial/axial grid, time increments, tighter solver tolerance and physical laws.',
        qualification='Joint geometry-consistency/angular refinement control; it cannot separately attribute the effect of these two geometric changes. No inherited native solution, threshold tuning, or physical calibration.')
    atomic(config_path,cfg)
    subprocess.run([sys.executable,str(ROOT/'model/prepare_model.py'),
                    '--config',str(config_path),'--output',str(target)],check=True,stdout=subprocess.DEVNULL)
    unchanged = {}
    for filename in ['material_v0.apdl','export_fields.mac','coupler.py','usermatth.F','usermatthLib.dll']:
        assert sha(parent/filename)==sha(target/filename),filename
        unchanged[filename] = sha(target/filename)
    for filename in ['run_v0.inp','resume_v0.inp']:
        assert (parent/filename).read_text().replace(parent_name,name)==(target/filename).read_text(),filename
    checked = geometry_audit(target)
    assert checked['mesh_measure_convention']=='straight_sided_hex'
    assert checked['native_index']==0
    atomic(ROOT/'validation/native_geometry_control_plan.json', dict(
        prepared_utc=utc(),runtime=name,parent_runtime=parent_name,status='PREPARED_NOT_STARTED',
        config_sha256=sha(target/'config.json'),unchanged_input_sha256=unchanged,
        preserved_legacy_maps=legacy,geometry_integration=checked,
        ranks=cfg['ranks'],parallel_mode=cfg['parallel_mode'],
        heat_flow_tolerance=cfg['numerics']['native_heat_flow_tolerance'],
        geometry_changes=cfg['provenance']['geometry_consistency_parent'],
        planned_gates='Preflight, native audits, one substep per interval, persistent topology, exact two-event agreement with unchanged cylindrical equations, cooling transition, terminal and restart audits. No relaxation.',
        dispatch='One diagnostic only, after the precision parent is cleanly paused and no solver remains. Main campaign remains held pending review.'))
    print('Prepared and geometrically verified',name)


if __name__=='__main__':
    main()
