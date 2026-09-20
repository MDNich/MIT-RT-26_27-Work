"""Hash-seal or verify the immutable input package, not runtime results."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parent
FILES=['config.json','build_iteration.py','coupler.py','model_base.inp','mesh_map.json',
       'material_iteration4.apdl','export_fields.mac','run_iteration4.inp','resume_iteration4.inp',
       'couple.cmd','preflight_no_solve.inp','launch_iteration4.ps1','request_pause.ps1',
       'package_check.py','verify_preflight.py','test_iteration4.py',
       'source/usermatth.F','source/usermatthLib.dll','source/simulation3_executed_ds.dat',
       'source/sector_mesh_template.wbpz','geometry/sector_0p10deg.step','geometry/sector_0p10deg.brep']


def hashes():
    return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--seal',action='store_true'); args=ap.parse_args()
    actual=hashes(); path=ROOT/'validation/input_manifest.json'
    if args.seal:
        if (ROOT/'state.json').exists(): raise RuntimeError('Cannot reseal a started calculation')
        path.write_text(json.dumps(actual,indent=2))
        print('INPUTS_SEALED_NO_SOLVE')
    else:
        expected=json.loads(path.read_text())
        assert expected==actual,'Input package modified: rebuild, rerun tests and preflight, then reseal before starting.'
        print('INPUT_PACKAGE_HASHES_MATCH_NO_SOLVE')


if __name__=='__main__': main()
