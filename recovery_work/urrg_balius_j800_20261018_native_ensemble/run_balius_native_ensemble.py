"""Run the exact installed OpenRocket build's native mass/Cd ensemble mode."""
import hashlib,json,shutil,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np

HERE=Path(__file__).resolve().parent
OUT=HERE/'urrg_balius_j800_20261018_native_ensemble'
APP_JAR=Path('/Applications/OpenRocket_MIT.app/Contents/Resources/app/jar/OpenRocket-24.12.jar')
JAVA=Path('/Applications/OpenRocket_MIT.app/Contents/Resources/jre.bundle/Contents/Home/bin/java')
SEED=20261018

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(key,runs,mass_sigma,cd_sigma,control=False):
    folder=OUT/key/('zero_variation_control' if control else 'results');folder.mkdir(parents=True,exist_ok=True)
    cmd=[str(JAVA),'-Xmx3g','-Djava.awt.headless=true','-cp',f'{OUT}/build:{OUT}/engine.jar',
         'BaliusNativeEnsemble',str(OUT/key/f'balius-cdr-{key}.ork'),str(folder),str(runs),
         str(mass_sigma),str(cd_sigma),str(SEED),'2']
    with (folder/'engine.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=log,check=True)
    summary=json.loads((folder/'summary.json').read_text())
    assert summary['completed']==runs and summary['excluded']==0
    if control:
        band=np.genfromtxt(folder/'native_altitude_band.csv',delimiter=',',names=True)
        assert np.nanmax(np.abs(band['stdev_altitude_m']))<1e-9
        assert summary['apogee_stdev_m']<1e-9 and summary['apogee_time_stdev_s']<1e-9
    print(key,'zero-variation control passed' if control else '500 native ensemble members complete',flush=True)
    return summary

def main():
    if (OUT/'manifest.json').exists():raise RuntimeError('Study already prepared; preserve its recorded inputs.')
    OUT.mkdir(exist_ok=True)
    shutil.copy2(APP_JAR,OUT/'engine.jar')
    manifest={'app':'/Applications/OpenRocket_MIT.app','app_jar':str(APP_JAR),
              'app_jar_resolved':str(APP_JAR.resolve()),'app_jar_sha256':digest(APP_JAR),
              'runtime':str(JAVA),'runs_per_design':500,'seed':SEED,
              'mass_distribution':'Normal(mean=1, sigma=0.05), constant multiplier per flight',
              'cd_distribution':'Normal(mean=1, sigma=0.02), constant multiplier per flight',
              'other_ensemble_sigmas':0,'wind':'Source 2 m/s wind and 10% turbulence; fixed native realization across runs',
              'native_feature':'Simulation.simulate with enabled EnsembleSettings; no custom perturbation listener',
              'source_inputs':{}}
    assert manifest['app_jar_sha256']==digest(OUT/'engine.jar')
    for key in ['canards','co2']:
        src=Path('/Users/mdn/Downloads')/f'balius-cdr-{key}.ork'
        folder=OUT/key;folder.mkdir(exist_ok=True);shutil.copy2(src,folder/src.name)
        manifest['source_inputs'][key]={'path':str(src),'sha256':digest(src)}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for name in ['BaliusNativeEnsemble.java',Path(__file__).name]:shutil.copy2(HERE/name,OUT/name)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(run,k,2,0,0,True) for k in ['canards','co2']]:future.result()
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(run,k,500,.05,.02) for k in ['canards','co2']]:future.result()
    for info in manifest['source_inputs'].values():assert digest(info['path'])==info['sha256']
    print('Both native ensembles saved and source ORKs unchanged.',flush=True)

if __name__=='__main__':main()
