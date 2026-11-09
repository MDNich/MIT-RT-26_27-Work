"""Check bare lateral pull repeats against the nine original solved fixture histories."""
import re
import sys
from pathlib import Path

import numpy as np
from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json


def references(archive):
    manifest=read(ROOT/'validation/local_inputs.json')
    data={}
    for key,source in manifest.items():
        if not key.startswith('lateral_'):
            continue
        origin=archive/source['source_path']
        checked=ROOT.parent/'1'/source['source_path']/'history.csv'
        verified(origin/'run.dat',source['files']['run.dat'])
        sha=verified(checked,digest(origin/'history.csv'))
        rows=table(checked)
        config=read(ROOT/'.runtime/local_inputs'/key/'config.json')
        assert np.all(np.diff(rows['time'])>0) and np.isclose(rows['ux_mm'][-1],config['sign']*config['displacement_mm'],atol=1e-6)
        listing=(origin/'run.out').read_text(errors='replace')
        states=re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',listing)
        assert len(states)==len(rows) and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
        data[key]=dict(history=str(checked.relative_to(ROOT.parent/'1')),history_sha256=sha,
                       original_run_sha256=source['files']['run.dat'],converged_states=len(states),
                       original_listing_sha256=digest(origin/'run.out'),end_reaction_N=float(rows['fx_N'][-1]))
    assert len(data)==9
    write_json(ROOT/'validation/october_local_pull_references.json',data)


def compare(case,campaign):
    key=case.removeprefix('bare_')
    source=read(ROOT/'validation/october_local_pull_references.json')[key]
    old=ROOT.parent/'1'/source['history']
    verified(old,source['history_sha256'])
    root=ROOT/'.runtime'
    folder=root/'archive'/campaign/case
    ledger=read(root/'receipts'/campaign/case/'archived.json')
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    assert ledger['case']==case and ledger['campaign']==campaign and source['original_run_sha256']==hashes['model.inp']
    new=folder/'history.csv'
    verified(new,hashes['history.csv'])
    a,b=table(old),table(new)
    assert np.all(np.diff(b['time'])>0)
    start=read(root/'local_inputs'/key/'config.json').get('pull_start_time',0.)
    def curve(h):
        mask=h['time']>start+1e-9
        ux=abs(h['ux_mm'][mask])
        assert len(ux) and np.all(np.diff(ux)>0)
        atlock=np.flatnonzero(np.isclose(h['time'],start,atol=1e-9,rtol=0))
        pts={'fx_N':0.,'max_seqv_MPa':0.,'max_eppl':0.}
        for name in pts:
            first=h[name][atlock[0]] if len(atlock) else 0.
            pts[name]=np.r_[first,h[name][mask]]
        return np.r_[0.,ux],pts
    ax,ay=curve(a);bx,by=curve(b)
    end=min(ax[-1],bx[-1])
    x=np.unique(np.r_[ax[ax<=end],bx[bx<=end]])
    errors={}
    for name in ay:
        v=np.interp(x,ax,ay[name]);w=np.interp(x,bx,by[name])
        peak=max(abs(v))
        errors[name]=dict(max_abs_difference=float(max(abs(v-w))),difference_relative_to_reference_peak=
                          float(max(abs(v-w))/peak) if peak>0 else None,October_at_end=float(v[-1]),repeat_at_end=float(w[-1]))
    write_json(ROOT/'validation/pull_repeats'/(case+'.json'),dict(case=case,campaign=campaign,
        October_sha256=source['history_sha256'],repeat_sha256=hashes['history.csv'],rst_sha256=hashes['pull.rst'],
        October_states=len(a),repeat_states=len(b),same_time_grid=len(a)==len(b) and np.allclose(a['time'],b['time'],atol=1e-8,rtol=0),
        matched_pull_interval_mm=[0.,float(end)],errors=errors,scope='Like-for-like bare fixture. Signed reaction, '
        'strip stress and plastic strain at common displacement knots; piecewise linear interpolation where the '
        'two native histories used different converged increments.'))


if __name__=='__main__':
    if sys.argv[1]=='sources':
        references(Path(sys.argv[2]))
    else:
        compare(*sys.argv[1:])
