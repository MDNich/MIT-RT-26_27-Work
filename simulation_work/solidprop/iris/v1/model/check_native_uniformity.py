"""Measure axial/angular variation hidden by radial averages, from accepted data."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from ops import ROOT,TMP,atomic,disks,host_check


def check_runtime(name):
    assert name not in ('', '.', '..') and Path(name).name == name
    accepted_path=ROOT/'validation'/f'accepted_{name}.json'
    accepted=json.loads(accepted_path.read_text());assert accepted['passed']
    runtime=TMP/'runs'/name;cfg=json.loads((runtime/'config.json').read_text());g=cfg['geometry']
    assert hashlib.sha256((runtime/'config.json').read_bytes()).hexdigest()==accepted['config_sha256']
    manifest=json.loads((runtime/'input_manifest.json').read_text())
    for filename,want in manifest.items():
        assert hashlib.sha256((runtime/filename).read_bytes()).hexdigest()==want,filename
    assert accepted['status'] in ['COMPLETED_HORIZON','CASE_PROPERTY_LIMIT_REACHED','PHENOLIC_CONSUMED']
    nph=g['phenolic_radial_rows'];nc=g['aluminium_radial_rows']
    plane=(g['angular_divisions']+1)*(g['axial_divisions']+1)
    maxima={k:dict(range_K=0.) for k in ['live_phenolic','casing']}
    digest=hashlib.sha256()
    for index in range(1,accepted['accepted_steps']+1):
        if index % 250 == 1:host_check()
        audit=json.loads((runtime/'checkpoints'/f'audit_{index:06d}.json').read_text())
        path=runtime/'checkpoints'/f'state_{index:06d}.json.gz';blob=path.read_bytes()
        digest.update(index.to_bytes(8,'big'));digest.update(hashlib.sha256(blob).digest())
        state=json.loads(gzip.decompress(blob))
        assert state['index']==index and abs(state['time_s']-audit['time_s'])<1e-8
        for j in range(audit['rows_removed'],nph+nc+1):
            values=[state['temperatures'][str(1+j*plane+k)] for k in range(plane)]
            span=max(values)-min(values);region='live_phenolic' if j<nph else 'casing'
            if span>maxima[region]['range_K']:
                maxima[region]=dict(range_K=span,index=index,time_s=audit['time_s'],
                    radial_station=j,min_C=min(values),max_C=max(values))
    return dict(case=cfg['case_id'],runtime=name,through_s=accepted['time_s'],
        config_sha256=accepted['config_sha256'],
        accepted_record_sha256=hashlib.sha256(accepted_path.read_bytes()).hexdigest(),
        ordered_checkpoint_hash_digest=digest.hexdigest(),maximum_same_radius_ranges=maxima)


QUALIFICATION = ('Observed axial/angular variation in accepted uniform-sector models. '
                 'This measures the information suppressed by radial averaging; it does not '
                 'validate uniformity in a real full-length motor or bound unmodelled end effects.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime', help='Check one terminal accepted runtime and write its own record; preserve the primary four-case record.')
    args=parser.parse_args()
    disks()
    if args.runtime:
        names=[args.runtime]
        target=ROOT/'validation'/f'native_uniformity_{args.runtime}.json'
    else:
        names=[f'{case}_pulse7_n80_midpoint_tight' for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']]
        names=[name for name in names if (ROOT/'validation'/f'accepted_{name}.json').exists()]
        target=ROOT/'validation/native_uniformity.json'
    records=[]
    for name in names:
        record=check_runtime(name)
        records.append(record)
        print(name,record['maximum_same_radius_ranges'],flush=True)
    atomic(target,dict(records=records,qualification=QUALIFICATION))


if __name__=='__main__':
    main()
