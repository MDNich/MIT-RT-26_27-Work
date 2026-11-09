"""Publish an index of reviewed movie pairs. A visual review is tied to exact movie and evidence hashes."""
import argparse
import os
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


def make(reviews, *, snug_fit=False):
    rows=catalog(snug_fit=snug_fit)
    dest=ROOT/'output/videos'
    registration=REVIEW
    if snug_fit:
        dest=dest/'snug125'
        registration=ROOT/'validation/snug125/film_visual_review.json'
    known={r[g]:(r,g) for r in rows for g in SLOTS}
    record=read(registration) if registration.exists() else {}
    for item in reviews:
        path,sha=item.rsplit('=',1);r,g=known[path]
        proof=decode(r,g);assert proof['sha256']==sha
        record[path]=dict(sha256=sha,sidecar_sha256=proof['sidecar_sha256'],review_sheet_sha256=proof['sheet_sha256'],
                          native_reference_sha256=r['sha256'],frames_reviewed=proof['check_frames'])
    if reviews:write_json(registration,record)
    ready={};pairs=0;raised_pairs=0;lines=[]
    motion_methods=set();rms_methods=set();native_seeded=0
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
                label=('1.25 mm Balius' if snug_fit else '3 mm stand-off')+' · nylon and aluminium'
            if proof.get('coordinate_method')=='native':
                label+=' · native motion'
            if proof.get('coordinate_method')=='independent':
                label+=' · independent motion'
            if proof.get('field_method')=='independent':
                label+=' · independent RMS'
            path=os.path.relpath(ROOT/name,dest);titles.append(f'[{label}]({path})')
            ready[name]=proof
            if r['kind']=='seeded random motion':
                motion_methods.add(proof['coordinate_method'])
            elif r['kind']=='camera motion over fixed RMS':
                rms_methods.add(proof.get('field_method') or 'native')
        if all(r[g] in ready for g in SLOTS):
            pair_check(r)
            if r['kind']=='seeded random motion' and all(ready[r[side]]['coordinate_method']=='native' for side in SLOTS):
                native_seeded+=1
            if ready[r['with_case']].get('comparison_panels')==2:raised_pairs+=1
            else:pairs+=1
        lines.append((r,titles))
    out=['# Battery-board movies','',
         f'{len(ready)} reviewed movies. {raised_pairs} subjects pair the bare board with the 3 mm nylon and aluminium mounts. '
         f'{pairs} of 22 subjects include both flush mounts as well.','',
         'The links open 3840 × 2160 movies at 60 fps. Paired views use the same displacement or stress scale. '
         'The mode movies show normalized motion. In the one-sigma movies the camera moves around a fixed RMS field. '
         'The seeded movies show successive instants of the original acceleration record.','']
    if snug_fit:
        out[:3]=['# Snug Balius comparison movies','',
                 f'{raised_pairs} of 22 subjects have reviewed pairs for the bare board and both 1.250 mm mounts.']
    if motion_methods:
        count='All seven' if native_seeded==7 else f'{native_seeded} of seven'
        detail=[f'{count} seeded movie pairs use native MAPDL time histories for every displayed panel.']
        if 'independent' in motion_methods:
            detail.append('Panels labelled independent use the same excitation and native mode shapes with independently integrated coordinates.')
        out+=[' '.join(detail),'']
    if 'independent' in rms_methods:
        out+=['RMS panels labelled independent use frequency integration on the native modes.','']
    endpoints=ROOT/'validation/installation_comparisons/flush_endpoints.json'
    if not snug_fit and raised_pairs and endpoints.is_file():
        checked=read(endpoints)['cases']
        assert set(checked)=={'nylon','aluminium'}
        if all(v['physical_vibration_state_established'] is False for v in checked.values()):
            out.extend(['In both flush installation trials the printed PLA exceeded its tensile reference before the tabs '
                        'touched the board. The raised mounts supply the cased vibration fields. '
                        '[Flush mounting results, page 19](../pdf/prior-fit-report.pdf#page=19)',''])
    for kind,label in LABEL.items():
        out+=['## '+label,'','| October subject | Without case | With case |','|---|---|---|']
        for r,titles in lines:
            if r['kind']==kind:out+=['| '+subject(r)+' | '+' | '.join(titles)+' |']
        out+=['']
    dest.mkdir(parents=True,exist_ok=True);(dest/'README.md').write_text('\n'.join(out))
    if snug_fit:
        print(len(ready),'reviewed movies;',raised_pairs,'snug-fit pairs')
    else:
        print(len(ready),'reviewed movies;',pairs,'complete pairs;',raised_pairs,'raised-only pairs')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',action='append',default=[],metavar='PATH=SHA256',
         help='Record a human/agent visual inspection of the three named decoded frames after viewing the matching sheet.')
    p.add_argument('--snug-fit',action='store_true');args=p.parse_args()
    make(args.review,snug_fit=args.snug_fit)
