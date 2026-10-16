"""Reproduce the 1000 native trajectories with a late-descent virtual floor."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import montecarlo_recovery as mc
out=Path(__file__).resolve().parent
launch=json.loads((out.parent/'urrg_no_drogue_20261016_perimeter/summary.json').read_text())['launch_site']
args=SimpleNamespace(openrocket_jar=Path('/tmp/urrg-recovery-engine-20261016.jar'),java_home='/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home',ork=out/'20267.demonstrator.iteration3.URRG.ork',trials=500,seed=20261011,wind_speed=None,random_wind_max=5.,turbulence_min=.05,turbulence_max=.2,workers=4,output=out,perimeter_mgrs=out/'perimeter_mgrs.txt',trace_dir=out/'traces',virtual_floor_depth=20)
mc.run_engine(args,out/'cases.csv',out/'extended_runs.csv',launch)
print('Late-descent trajectory rerun complete',flush=True)
