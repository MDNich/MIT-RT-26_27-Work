"""Independent transient profiles versus accepted native seven-second states."""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,host_check,disks


def main():
    disks()
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        run=TMP/'runs'/f'{case}_baseline7_n20_dt0125'
        if not (run/'state.json').exists():continue
        terminal=json.loads((run/'state.json').read_text())
        if terminal['status']!='COMPLETED_HORIZON':continue
        cfg=json.loads((run/'config.json').read_text());model=RadialModel(cfg)
        _,history,snaps=model.run(7,dt=cfg['macro_dt_s'],targets=[.1,1,2,5,7],check=host_check)
        comparisons=[]
        plane=(cfg['geometry']['angular_divisions']+1)*(cfg['geometry']['axial_divisions']+1)
        for t in [.1,1,2,5,7]:
            index=round(t/cfg['macro_dt_s'])
            file=run/'checkpoints'/f'state_{index:06d}.json.gz'
            with gzip.open(file,'rt') as f:native=json.load(f)
            state=snaps[t]
            assert abs(native['time_s']-state.time)<1e-8
            nativeT=np.array([np.mean([native['temperatures'][str(1+j*plane+i)] for i in range(plane)]) for j in range(len(model.r))])
            delta=state.T-nativeT
            nfaces=cfg['geometry']['faces_per_row']
            na=np.array([np.mean([native['alpha'][str(1+j*nfaces+i)] for i in range(nfaces)]) for j in range(model.np)])
            da=np.mean(state.alpha,axis=1)-na
            comparison=dict(time_s=t,max_temperature_difference_K=float(np.max(np.abs(delta))),
                profile_rmse_K=float(np.sqrt(np.mean(delta**2))),hot_face_difference_K=float(delta[state.layer]),
                interface_difference_K=float(delta[model.np]),outer_difference_K=float(delta[-1]),max_conversion_difference=float(np.max(np.abs(da))),
                native_removed_rows=native['layer'],independent_removed_rows=state.layer,radius_m=model.r.tolist(),
                native_temperature_C=nativeT.tolist(),independent_temperature_C=state.T.tolist(),
                native_mean_conversion=na.tolist(),independent_mean_conversion=np.mean(state.alpha,axis=1).tolist(),
                native_state_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            comparisons.append(comparison)
        worstT=max(c['max_temperature_difference_K'] for c in comparisons)
        worstAlpha=max(c['max_conversion_difference'] for c in comparisons)
        passed=worstT<5 and worstAlpha<.02 and all(c['native_removed_rows']==c['independent_removed_rows'] for c in comparisons)
        out=dict(case=case,passed=passed,qualification='Numerical model comparison, not experimental material/recession validation',
                 temperature_target_K=5.,conversion_target=.02,max_temperature_difference_K=worstT,max_conversion_difference=worstAlpha,
                 independent_energy_error=model.max_energy_error,independent_mass_error=model.max_mass_error,comparisons=comparisons)
        atomic(ROOT/'validation'/f'native_radial_comparison_{case}.json',out)
        print(case,passed,worstT,worstAlpha)

if __name__=='__main__':main()
