"""Repeat the paired J800T study from the corrected source ORKs; two maps only."""
import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import balius_recovery_study as study

study.OUTPUT=study.HERE/'urrg_balius_j800_20261018_corrected_parachutes'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['prepare','controls','run','analyze','all'],default='all')
    args=parser.parse_args()
    if args.stage in ['prepare','all']:
        if (study.OUTPUT/'study_inputs.json').exists():
            raise RuntimeError('Prepared study already exists; choose a later stage to preserve it.')
        launch,designs=study.prepare()
        for key,info in designs.items():
            assert np.isclose(info['main_diameter_m'],2.109216)
            assert info['main_cd_setting']=='0.68'
            assert study.mc.digest(Path(info['source_path']))==info['source_sha256']
            print(key,'updated main',info['main_diameter_m'],'m; Cd',info['main_cd_setting'],flush=True)
        source=study.OUTPUT/'source';source.mkdir(exist_ok=True)
        for name in ['balius_recovery_study.py','RecoveryBatch.java','montecarlo_recovery.py',
                     'recovery_terrain.py','recovery_perimeter.py','requirements-recovery.txt',Path(__file__).name]:
            shutil.copy2(study.HERE/name,source/name)
    else:
        launch=json.loads((study.OUTPUT/'study_inputs.json').read_text())['launch_site']
    if args.stage in ['controls','all']:
        for extended in [False,True]:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(study.run_one,key,launch,True,extended) for key,*_ in study.DESIGNS]
                for future in futures:future.result()
        for key,*_ in study.DESIGNS:
            study.validate_controls(key)
            info=json.loads((study.OUTPUT/key/'design.json').read_text())
            for folder in ['controls_flat','controls_extended']:
                study.read_recovery_audit(study.OUTPUT/key/folder,info)
    if args.stage in ['run','all']:
        for key,*_ in study.DESIGNS:
            assert json.loads((study.OUTPUT/key/'control_validation.json').read_text())['passed']
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(study.run_one,key,launch) for key,*_ in study.DESIGNS]
            for future in futures:future.result()
    if args.stage in ['analyze','all']:
        boundary=study.load_perimeter(study.OUTPUT/'earth_data/perimeter_mgrs.txt',launch)
        terrain=study.Terrain(study.OUTPUT/'earth_data/usgs_3dep_dem_2m.tif',boundary['crs'])
        texture=study.texture_data()
        results=[study.analyze_design(key,terrain,boundary) for key,*_ in study.DESIGNS]
        limit=float(max(300,50*np.ceil(1.18*max(s['radius_m']['max'] for s,*_ in results)/50)))
        left,right,bottom,top=texture[1]
        assert left<=-limit and right>=limit and bottom<=-limit and top>=limit,'Expand imagery coverage'
        for summary,landings,*_ in results:
            study.make_satellite(summary,landings,boundary,texture,limit)
        report={'map_half_width_m':limit,'same_weather_as_previous_study':True,
                'comparison':[s for s,*_ in results],
                'engine_jar_sha256':study.mc.digest(study.JAR),
                'source_orks_unchanged_by_run':all(study.mc.digest(src)==s['design']['source_sha256']
                    for (_,_,_,src),(s,*_) in zip(study.DESIGNS,results))}
        (study.OUTPUT/'comparison_summary.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Two satellite plots ready:',study.OUTPUT,flush=True)


if __name__=='__main__':
    main()
