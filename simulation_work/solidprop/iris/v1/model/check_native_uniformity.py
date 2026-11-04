"""Measure axial/angular variation hidden by radial averages, from accepted data."""
import gzip
import hashlib
import json
from ops import ROOT,TMP,atomic,disks


def main():
    disks();records=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        name=f'{case}_pulse7_n80_midpoint_tight'
        accepted_path=ROOT/'validation'/f'accepted_{name}.json'
        if not accepted_path.exists():continue
        accepted=json.loads(accepted_path.read_text());assert accepted['passed']
        runtime=TMP/'runs'/name;cfg=json.loads((runtime/'config.json').read_text());g=cfg['geometry']
        assert hashlib.sha256((runtime/'config.json').read_bytes()).hexdigest()==accepted['config_sha256']
        nph=g['phenolic_radial_rows'];nc=g['aluminium_radial_rows']
        plane=(g['angular_divisions']+1)*(g['axial_divisions']+1)
        maxima={k:dict(range_K=0.) for k in ['live_phenolic','casing']}
        digest=hashlib.sha256()
        for index in range(1,accepted['accepted_steps']+1):
            audit=json.loads((runtime/'checkpoints'/f'audit_{index:06d}.json').read_text())
            path=runtime/'checkpoints'/f'state_{index:06d}.json.gz';blob=path.read_bytes()
            digest.update(index.to_bytes(8,'big'));digest.update(hashlib.sha256(blob).digest())
            state=json.loads(gzip.decompress(blob))
            for j in range(audit['rows_removed'],nph+nc+1):
                values=[state['temperatures'][str(1+j*plane+k)] for k in range(plane)]
                span=max(values)-min(values);region='live_phenolic' if j<nph else 'casing'
                if span>maxima[region]['range_K']:
                    maxima[region]=dict(range_K=span,index=index,time_s=audit['time_s'],
                        radial_station=j,min_C=min(values),max_C=max(values))
        records.append(dict(case=case,runtime=name,through_s=accepted['time_s'],
            config_sha256=accepted['config_sha256'],
            accepted_record_sha256=hashlib.sha256(accepted_path.read_bytes()).hexdigest(),
            ordered_checkpoint_hash_digest=digest.hexdigest(),maximum_same_radius_ranges=maxima))
        print(case,maxima,flush=True)
    atomic(ROOT/'validation/native_uniformity.json',dict(records=records,
        qualification='Observed axial/angular variation in accepted uniform-sector models. This measures the information suppressed by radial averaging; it does not validate uniformity in a real full-length motor or bound unmodelled end effects.'))


if __name__=='__main__':
    main()
