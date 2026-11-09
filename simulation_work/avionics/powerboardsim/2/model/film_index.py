"""Publish an index of reviewed movie pairs. A visual review is tied to exact movie and evidence hashes."""
import argparse
from pathlib import Path
from film_campaign import ROOT,RT,SLOTS,catalog,decode,pair_check,read
from film_identity import digest,write_json

REVIEW=ROOT/'validation/film_visual_review.json'
LABEL={'normalized modal motion':'Normalized modes','camera motion over fixed RMS':'One-sigma displacement (camera orbit)',
       'seeded random motion':'Seeded time histories'}


def make(reviews):
    rows=catalog();known={r[g]:(r,g) for r in rows for g in SLOTS}
    record=read(REVIEW) if REVIEW.exists() else {}
    for item in reviews:
        path,sha=item.rsplit('=',1);r,g=known[path]
        proof=decode(r,g);assert proof['sha256']==sha
        record[path]=dict(sha256=sha,sidecar_sha256=proof['sidecar_sha256'],review_sheet_sha256=proof['sheet_sha256'],
                          native_reference_sha256=r['sha256'],frames_reviewed=proof['check_frames'])
    if reviews:write_json(REVIEW,record)
    ready={};pairs=0;lines=[]
    for r in rows:
        titles=[]
        for g,label in zip(SLOTS,['Bare','Four cases'],strict=True):
            name=r[g];mark=record.get(name)
            if not mark:titles.append('Pending');continue
            proof=decode(r,g)
            if proof['sha256']!=mark['sha256'] and g=='without_case' and (ROOT/'.runtime/films/baseline_history'/mark['sha256']/'metadata.json').exists():
                titles.append('New comparison scale awaiting visual review');continue
            assert proof['sha256']==mark['sha256'] and proof['sidecar_sha256']==mark['sidecar_sha256']
            assert proof['sheet_sha256']==mark['review_sheet_sha256'] and proof['reference_sha256']==mark['native_reference_sha256']
            path=Path(name).relative_to('output/videos');titles.append(f'[{label}]({path})')
            ready[name]=proof['sha256']
        if all(r[g] in ready for g in SLOTS):pair_check(r);pairs+=1
        lines.append((r,titles))
    out=['# Battery-board movies','',f'{len(ready)} of 44 movies have passed decoding and visual review; {pairs} of 22 subjects have both versions.','',
         'Each completed pair contains a bare-board movie and a four-panel comparison: flush nylon, flush aluminium, 3 mm stand-off nylon and 3 mm stand-off aluminium. All movies are 3840 × 2160 at 60 fps. A modal amplitude is normalized; an RMS camera orbit is not a vibration time history.','']
    for kind,label in LABEL.items():
        out+=['## '+label,'','| October subject | Without case | With case |','|---|---|---|']
        for r,titles in lines:
            if r['kind']==kind:out+=['| '+Path(r['file']).stem+' | '+' | '.join(titles)+' |']
        out+=['']
    (ROOT/'output/videos/README.md').write_text('\n'.join(out))
    print(len(ready),'reviewed movies;',pairs,'complete pairs')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',action='append',default=[],metavar='PATH=SHA256',
         help='Record a human/agent visual inspection of the three named decoded frames after viewing the matching sheet.')
    make(p.parse_args().review)
