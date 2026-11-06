"""Check physical sector proportions and final-step placement using independent warm states."""
import json
import math
import time
from pathlib import Path

import numpy as np

from continuous_heating_campaign import digest
from ops import ROOT, TMP, atomic, disks, host_check
from prepare_sector_exposures import PACKAGE
from sector_exposure import balances, pack, unpack
from sector_wall import Sector, banded
from sector_terminal_step import end_step


def edge_ratio(radii, g):
    radial = np.diff(radii)
    # Inner and outer chord lengths differ slightly on a wedge.
    chord = 2*radii*math.sin(math.radians(g['angle_deg'])/(2*g['angular_divisions']))
    axial = g['length_m']/g['axial_divisions']
    longest = np.maximum(np.maximum(radial,chord[1:]),axial)
    shortest = np.minimum(np.minimum(radial,chord[:-1]),axial)
    return float(max(longest/shortest))


def main():
    disks()
    frames = TMP/'sector_reduction/guest_warm_states.json'
    donor = json.loads(frames.read_text())
    proof = json.loads((ROOT/'validation/sector_guest_preflight.json').read_text())
    assert digest(frames)==proof['warm_source_sha256'] and donor['archive_sha256']==digest(PACKAGE/'controller.zip')
    results = {}
    guard_at = time.monotonic()
    for job, data in donor['cases'].items():
        path = PACKAGE/(job+'_settings.json')
        assert digest(path)==data['settings_sha256']
        settings = json.loads(path.read_text())
        cfg = settings['configuration']
        wall = Sector(cfg,settings['n'],settings['nc'])
        g = cfg['geometry']
        old = unpack(data['frames']['last_live_step']['state'])
        old_ratio = edge_ratio(np.r_[old.nodes,wall.case[1:]],g)
        # This diagnostic changes the representative sector dimensions only.
        # The physical radii, constitutive laws, radial inventory, thermal
        # boundaries and time-step ceiling retain their configured values.
        g['angle_deg'] = .03
        g['length_m'] = g['axial_divisions']*wall.interface*math.radians(g['angle_deg'])/g['angular_divisions']
        wall = Sector(cfg,settings['n'],settings['nc'])
        state = wall.initial()
        peak = 0.
        edits = []
        sums = {}
        steps = 0
        reference_end = data['frames']['last_live_step']['expected_time_s']
        warm = None
        ceiling = settings['dt_s']
        while len(state.virgin):
            host_check()
            if time.monotonic()-guard_at>15:
                disks()
                guard_at=time.monotonic()
            station = (int(math.floor((state.time+1e-10)*2))+1)*.5
            requested = min(ceiling,station-state.time)
            dt = end_step(wall,state,requested,ceiling)
            if dt<requested:
                edits.append([state.time,requested,dt])
            if warm is None and state.time>=reference_end-.20:
                warm=dict(state=pack(state),steps=steps,sums=sums.copy())
            def solve(block):
                nonlocal peak
                peak = max(peak,edge_ratio(block.radii,g))
                return banded(block)
            before = state.time
            state, ledger, _ = wall.advance(state,dt,solve)
            assert 0<state.time-before<=ceiling+1e-11
            steps+=1
            for key,value in ledger.items():
                sums[key]=sums.get(key,0.)+float(value)
        errors=balances(settings,dict(state=pack(state),stats=dict(sums=sums)))
        assert warm and len(edits)>0 and peak<20. and max(map(abs,errors.values()))<1e-7
        assert abs(state.time-reference_end)<.01
        results[job] = dict(original_final_edge_ratio=old_ratio,steps=steps,balance_errors=errors,
                            candidate_peak_edge_ratio=peak,reference_end_s=reference_end,
                            candidate_end_s=state.time,shortened_steps=edits,geometry=g,
                            warm_station=warm)
    result=dict(scope='Independent physical-mesh diagnostic from initial temperature to exhaustion. Edge lengths only; no native shape or motor result.',
                step_sha256=digest(ROOT/'model/sector_terminal_step.py'),
                source_sha256=digest(Path(__file__)),donor_sha256=digest(frames),cases=results)
    atomic(ROOT/'validation/terminal_brick_geometry.json',result)
    for job,row in results.items():
        print(job, row['original_final_edge_ratio'],row['candidate_peak_edge_ratio'],
              row['candidate_end_s']-row['reference_end_s'],len(row['shortened_steps']))


if __name__=='__main__':
    main()
