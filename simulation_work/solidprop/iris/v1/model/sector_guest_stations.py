"""Save warm and last-live input fields for the guest brick-assembly check.

The frames come from independent reference trajectories solely for verification.
The four production inputs always start at ignition.
"""
import fcntl
import json
import time

from continuous_heating_campaign import digest
from moving_surface_campaign import SHARED
from ops import ROOT,TMP,StorageLimitError,atomic,disks,host_check,stop_runs
from prepare_sector_exposures import PACKAGE,JOBS
from sector_exposure import pack
from sector_wall import Sector


def main():
    disks()
    reference=json.loads((ROOT/'validation/sector_exposure_reduction.json').read_text())
    frames={}
    last=0.
    for job in JOBS[2:]:
        p=PACKAGE/(job+'_settings.json')
        settings=json.loads(p.read_text())
        wall=Sector(settings['configuration'],settings['n'],settings['nc'])
        state=wall.initial()
        selected={}
        while len(state.virgin):
            host_check()
            if time.monotonic()-last>10:
                disks()
                last=time.monotonic()
            next_station=(int((state.time+1e-10)*2)+1)*.5
            dt=min(next_station-state.time,settings['dt_s'])
            new,_,_=wall.advance(state,dt)
            back=state.temperature[len(state.virgin)-1:]
            labels=[]
            if min(back)<660.55 and max(back)>660.05 and not wall.cf: labels.append('during_fusion')
            if max(back)>1000. and wall.cf: labels.append('after_1000_C')
            if 0<len(new.nodes)<len(state.nodes) and len(new.virgin): labels.append('first_merged_cell')
            if not len(new.virgin): labels.append('last_live_step')
            for label in labels:
                if label not in selected:
                    selected[label]=dict(state=pack(state),dt=dt,expected_time_s=new.time,
                                         expected_nodes=len(new.nodes),expected_hot_C=float(new.temperature[0]))
            state=new
        ref=reference['cases'][settings['case']]['runs'][0]['events']['exhaustion'][1]
        assert abs(state.time-ref)<1e-8 and len(selected)==3
        frames[job]=dict(settings_sha256=digest(p),frames=selected)
    path=TMP/'sector_reduction/guest_warm_states.json'
    atomic(path,dict(archive_sha256=digest(PACKAGE/'controller.zip'),cases=frames))
    print(digest(path))


if __name__=='__main__':
    try:
        with (SHARED/'worker.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            main()
    except StorageLimitError as exc:
        stop_runs(str(exc))
        raise
