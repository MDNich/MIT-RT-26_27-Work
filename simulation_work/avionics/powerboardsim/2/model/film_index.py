"""Publish an index of reviewed movie pairs. A visual review is tied to exact movie and evidence hashes."""
import argparse
from pathlib import Path
from film_campaign import ROOT,RT,SLOTS,catalog,decode,pair_check,read
from film_identity import digest,write_json

REVIEW=ROOT/'validation/film_visual_review.json'
LABEL={'normalized modal motion':'Normalized modes','camera motion over fixed RMS':'One-sigma displacement (camera orbit)',
       'seeded random motion':'Seeded time histories'}


def subject(row):
    if row['kind']=='normalized modal motion':
        setup,mode,freq=(s.strip() for s in row['october_title'].split('|'))
        return f'{setup} · {mode} ({freq} bare)'
    if row['kind']=='camera motion over fixed RMS':
        return f'{row["view"]} · base {row["axis"]} · {row["response"]} displacement'
    view='Whole assembly' if row['scope']=='assembly' else 'PCB'
    quantity='von Mises stress' if row['component']=='stress' else row['component']+' displacement'
    return f'{view} · base {row["axis"]} · {quantity}'


def make(reviews):
    rows=catalog();known={r[g]:(r,g) for r in rows for g in SLOTS}
    record=read(REVIEW) if REVIEW.exists() else {}
    for item in reviews:
        path,sha=item.rsplit('=',1);r,g=known[path]
        proof=decode(r,g);assert proof['sha256']==sha
        record[path]=dict(sha256=sha,sidecar_sha256=proof['sidecar_sha256'],review_sheet_sha256=proof['sheet_sha256'],
                          native_reference_sha256=r['sha256'],frames_reviewed=proof['check_frames'])
    if reviews:write_json(REVIEW,record)
    ready={};pairs=0;raised_pairs=0;lines=[]
    for r in rows:
        titles=[]
        for g,label in zip(SLOTS,['Bare','Four cases'],strict=True):
            name=r[g];mark=record.get(name)
            if not mark:titles.append('Pending');continue
            proof=decode(r,g)
            if proof['sha256']!=mark['sha256'] and (ROOT/'.runtime/films/baseline_history'/mark['sha256']/'metadata.json').exists():
                titles.append('Updated comparison awaiting visual review');continue
            assert proof['sha256']==mark['sha256'] and proof['sidecar_sha256']==mark['sidecar_sha256']
            assert proof['sheet_sha256']==mark['review_sheet_sha256'] and proof['reference_sha256']==mark['native_reference_sha256']
            if g=='with_case' and proof.get('comparison_panels')==2:
                label='3 mm stand-off · nylon and aluminium'
            if proof.get('coordinate_method')=='native':
                label+=' · native motion'
            if proof.get('coordinate_method')=='independent':
                label+=' · independent motion'
            if proof.get('field_method')=='independent':
                label+=' · independent RMS'
            path=Path(name).relative_to('output/videos');titles.append(f'[{label}]({path})')
            ready[name]=proof['sha256']
        if all(r[g] in ready for g in SLOTS):
            pair_check(r)
            if decode(r,'with_case').get('comparison_panels')==2:raised_pairs+=1
            else:pairs+=1
        lines.append((r,titles))
    out=['# Battery-board movies','',
         f'{len(ready)} reviewed movies. {raised_pairs} subjects pair the bare board with the 3 mm nylon and aluminium mounts. '
         f'{pairs} of 22 subjects include both flush mounts as well.','',
         'The links open 3840 × 2160 movies at 60 fps. Paired views use the same displacement or stress scale. '
         'The mode movies show normalized motion. In the one-sigma movies the camera moves around a fixed RMS field. '
         'The seeded movies show successive instants of the original acceleration record.','',
         'Native motion uses coordinates from the MAPDL transient. Independent motion uses the same excitation and native mode shapes '
         'with independently integrated coordinates. Independent RMS uses frequency integration on the native modes.','']
    for kind,label in LABEL.items():
        out+=['## '+label,'','| October subject | Without case | With case |','|---|---|---|']
        for r,titles in lines:
            if r['kind']==kind:out+=['| '+subject(r)+' | '+' | '.join(titles)+' |']
        out+=['']
    (ROOT/'output/videos/README.md').write_text('\n'.join(out))
    print(len(ready),'reviewed movies;',pairs,'complete pairs;',raised_pairs,'raised-only pairs')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',action='append',default=[],metavar='PATH=SHA256',
         help='Record a human/agent visual inspection of the three named decoded frames after viewing the matching sheet.')
    make(p.parse_args().review)
